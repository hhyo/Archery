try:
    from itertools import zip_longest
except ImportError:
    from itertools import izip_longest as zip_longest
import django
from django.db.models.sql import compiler
from django.db.models.fields.json import KeyTransform, KeyTransformExact, KeyTransformIsNull
from django.db.models.fields.json import HasAnyKeys, HasKey, HasKeys
from django.db.models.expressions import Exists
from django.db.models.lookups import Exact

from django.core.exceptions import EmptyResultSet, FieldError
from django.db import DatabaseError, NotSupportedError
from django.db.models.expressions import F, OrderBy, RawSQL, Ref, Value
if django.VERSION>=(3,2):
    from django.db.models.functions.math import Random
if django.VERSION<(3,2):
    from django.db.models.expressions import Random
from django.db.models.functions import Cast

from django.db.models.sql.constants import ORDER_DIR
from django.db.models.sql.query import get_order_dir
from django.utils.hashable import make_hashable

class SQLCompiler(compiler.SQLCompiler):
    def compile(self, node, select_format=False):
        vendor_impl = getattr(node, 'as_' + self.connection.vendor, None)
        
        if vendor_impl:
            sql, params = vendor_impl(self, self.connection)
        elif isinstance(node, KeyTransform):
            sql, params = node.as_oracle(self, self.connection)
        elif isinstance(node, KeyTransformExact):
            sql, params = node.as_sql(self, self.connection)
        elif isinstance(node, KeyTransformIsNull):
            sql, params = HasKey(
                node.lhs.lhs,
                node.lhs.key_name,
            ).as_sql(self, self.connection, template='JSON_QUERY(%s, %%s WITH WRAPPER) IS NOT NULL')
            if not node.rhs:
                return sql, params
            lhs, lhs_params, _ = node.lhs.preprocess_lhs(self, self.connection)
            return '(NOT %s OR %s IS NULL)' % (sql, lhs), tuple(params) + tuple(lhs_params)            
        elif isinstance(node, HasAnyKeys):
            sql, params = node.as_sql(self, self.connection, template='JSON_VALUE(%s, %%s) IS NOT NULL')
        elif isinstance(node, HasKey) or isinstance(node, HasKeys):
            sql, params = node.as_sql(self, self.connection, template='JSON_QUERY(%s, %%s WITH WRAPPER) IS NOT NULL')
        elif isinstance(node, OrderBy):
            sql, params = node.as_oracle(self, self.connection)
        elif isinstance(node, Exact) and isinstance(node.lhs, Exists) and isinstance(node.rhs, Exists):
            sql, params = self.as_sql_for_Exact(node)
        else:
            sql, params = node.as_sql(self, self.connection)
            
        if select_format and not self.query.subquery:
            return node.output_field.select_format(self, sql, params)

        return sql, params
    
    def as_sql_for_Exact(self, node):
        lhs_sql, params = node.process_lhs(self, self.connection)
        rhs_sql, rhs_params = node.process_rhs(self, self.connection)
        params.extend(rhs_params)
        rhs_sql = 'AND %s' % rhs_sql
        return '%s %s' % (lhs_sql, rhs_sql), params
    
    def get_order_by(self):
        """
        Return a list of 2-tuples of form (expr, (sql, params, is_ref)) for the
        ORDER BY clause.

        The order_by clause can alter the select clause (for example it
        can add aliases to clauses that do not yet have one, or it can
        add totally new select clauses).
        """
        if self.query.extra_order_by:
            ordering = self.query.extra_order_by
        elif not self.query.default_ordering:
            ordering = self.query.order_by
        elif self.query.order_by:
            ordering = self.query.order_by
        elif self.query.get_meta().ordering:
            ordering = self.query.get_meta().ordering
            self._meta_ordering = ordering
        else:
            ordering = []
        if self.query.standard_ordering:
            asc, desc = ORDER_DIR['ASC']
        else:
            asc, desc = ORDER_DIR['DESC']

        order_by = []
        for field in ordering:
            if hasattr(field, 'resolve_expression'):
                if isinstance(field, Value):
                    # output_field must be resolved for constants.
                    field = Cast(field, field.output_field)
                if not isinstance(field, OrderBy):
                    field = field.asc()
                if not self.query.standard_ordering:
                    field = field.copy()
                    field.reverse_ordering()
                order_by.append((field, False))
                continue
            if field == '?':  # random
                order_by.append((OrderBy(Random()), False))
                continue

            col, order = get_order_dir(field, asc)
            descending = order == 'DESC'

            if col in self.query.annotation_select:
                # Reference to expression in SELECT clause
                order_by.append((
                    OrderBy(Ref(col, self.query.annotation_select[col]), descending=descending),
                    True))
                continue
            if col in self.query.annotations:
                # References to an expression which is masked out of the SELECT
                # clause.
                expr = self.query.annotations[col]
                if isinstance(expr, Value):
                    # output_field must be resolved for constants.
                    expr = Cast(expr, expr.output_field)
                order_by.append((OrderBy(expr, descending=descending), False))
                continue

            if '.' in field:
                # This came in through an extra(order_by=...) addition. Pass it
                # on verbatim.
                table, col = col.split('.', 1)
                order_by.append((
                    OrderBy(
                        RawSQL('%s.%s' % (self.quote_name_unless_alias(table), self.quote_name_unless_alias(col)), []),
                        descending=descending
                    ), False))
                continue

            if not self.query.extra or col not in self.query.extra:
                # 'col' is of the form 'field' or 'field1__field2' or
                # '-field1__field2__field', etc.
                order_by.extend(self.find_ordering_name(
                    field, self.query.get_meta(), default_order=asc))
            else:
                if col not in self.query.extra_select:
                    order_by.append((
                        OrderBy(RawSQL(*self.query.extra[col]), descending=descending),
                        False))
                else:
                    order_by.append((
                        OrderBy(Ref(col, RawSQL(*self.query.extra[col])), descending=descending),
                        True))
        result = []
        seen = set()

        for expr, is_ref in order_by:
            resolved = expr.resolve_expression(self.query, allow_joins=True, reuse=None)
            if self.query.combinator:
                src = resolved.get_source_expressions()[0]
                expr_src = expr.get_source_expressions()[0]
                # Relabel order by columns to raw numbers if this is a combined
                # query; necessary since the columns can't be referenced by the
                # fully qualified name and the simple column names may collide.
                for idx, (sel_expr, _, col_alias) in enumerate(self.select):
                    if is_ref and col_alias == src.refs:
                        src = src.source
                    elif col_alias and not (
                        isinstance(expr_src, F) and col_alias == expr_src.name
                    ):
                        continue
                    if src == sel_expr:
                        resolved.set_source_expressions([RawSQL('%d' % (idx + 1), ())])
                        break
                else:
                    if col_alias:
                        raise DatabaseError('ORDER BY term does not match any column in the result set.')
                    # Add column used in ORDER BY clause without an alias to
                    # the selected columns.
                    self.query.add_select_col(src)
                    resolved.set_source_expressions([RawSQL('%d' % len(self.query.select), ())])
            sql, params = self.compile(resolved)
            # Don't add the same column twice, but the order direction is
            # not taken into account so we strip it. When this entire method
            # is refactored into expressions, then we can check each part as we
            # generate it.
            without_ordering = self.ordering_parts.search(sql)[1]
            params_hash = make_hashable(params)
            if (without_ordering, params_hash) in seen:
                continue
            seen.add((without_ordering, params_hash))
            result.append((resolved, (sql, params, is_ref)))
        return result
    
class SQLInsertCompiler(compiler.SQLInsertCompiler, SQLCompiler):
    def __init__(self, *args, **kwargs):
        self.return_id = False
        super(SQLInsertCompiler, self).__init__(*args, **kwargs)

    def field_as_sql(self, field, val):
        """
        Take a field and a value intended to be saved on that field, and
        return placeholder SQL and accompanying params. Checks for raw values,
        expressions and fields with get_placeholder() defined in that order.

        When field is None, the value is considered raw and is used as the
        placeholder, with no corresponding parameters returned.
        """
        if field is None:
            # A field value of None means the value is raw.
            sql, params = val, []
        elif hasattr(val, 'as_sql'):
            # This is an expression, let's compile it.
            sql, params = self.compile(val)
        elif hasattr(field, 'get_placeholder'):
            # Some fields (e.g. geo fields) need special munging before
            # they can be inserted.
            sql, params = field.get_placeholder(val, self, self.connection), [val]
        else:
            # Return the common case for the placeholder
            sql, params = '?', [val]

        params = self.connection.ops.modify_insert_params(sql, params)

        return sql, params

class SQLDeleteCompiler(compiler.SQLDeleteCompiler, SQLCompiler):
    pass

class SQLUpdateCompiler(compiler.SQLUpdateCompiler, SQLCompiler):
    def as_sql(self):
        """
        Create the SQL for this query. Return the SQL string and list of
        parameters.
        """
        self.pre_sql_setup()
        if not self.query.values:
            return '', ()
        qn = self.quote_name_unless_alias
        values, update_params = [], []
        for field, model, val in self.query.values:
            if hasattr(val, 'resolve_expression'):
                val = val.resolve_expression(self.query, allow_joins=False, for_save=True)
                if val.contains_aggregate:
                    raise FieldError(
                        'Aggregate functions are not allowed in this query '
                        '(%s=%r).' % (field.name, val)
                    )
                if val.contains_over_clause:
                    raise FieldError(
                        'Window expressions are not allowed in this query '
                        '(%s=%r).' % (field.name, val)
                    )
            elif hasattr(val, 'prepare_database_save'):
                if field.remote_field:
                    val = field.get_db_prep_save(
                        val.prepare_database_save(field),
                        connection=self.connection,
                    )
                else:
                    raise TypeError(
                        "Tried to update field %s with a model instance, %r. "
                        "Use a value compatible with %s."
                        % (field, val, field.__class__.__name__)
                    )
            else:
                val = field.get_db_prep_save(val, connection=self.connection)

            # Getting the placeholder for the field.
            if hasattr(field, 'get_placeholder'):
                placeholder = field.get_placeholder(val, self, self.connection)
            else:
                placeholder = '%s'
            name = field.column
            if hasattr(val, 'as_sql'):
                sql, params = self.compile(val)
                placeholder = '%s'
                values.append('%s = %s' % (qn(name), placeholder % sql))
                update_params.extend(params)
            elif val is not None:
                values.append('%s = %s' % (qn(name), placeholder))
                update_params.append(val)
            else:
                values.append('%s = NULL' % qn(name))
        table = self.query.base_table
        result = [
            'UPDATE %s SET' % qn(table),
            ', '.join(values),
        ]
        where, params = self.compile(self.query.where)
        if where:
            result.append('WHERE %s' % where)
        return ' '.join(result), tuple(update_params + params)    

class SQLAggregateCompiler(compiler.SQLAggregateCompiler, SQLCompiler):
    pass
