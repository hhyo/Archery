import django

try:
    from itertools import zip_longest
except ImportError:
    from itertools import izip_longest as zip_longest

from django.db.models.sql import compiler
from django.db.models.fields import BinaryField

class SQLCompiler(compiler.SQLCompiler):
    def compile(self, node, select_format=False):
        vendor_impl = getattr(node, 'as_' + self.connection.vendor, None)
        
        if vendor_impl:
            sql, params = vendor_impl(self, self.connection)
        else:
            sql, params = node.as_sql(self, self.connection)

        if django.VERSION<(1, 11):
            if select_format and not self.subquery:
                return node.output_field.select_format(self, sql, params)
        if django.VERSION>=(1, 11):
            if select_format and not self.query.subquery:
                return node.output_field.select_format(self, sql, params)
        
        if hasattr(node, 'lookup_name'):
            sql = sql.replace('%s','?')
        
        return sql, params

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
        self.pre_sql_setup()
        if not self.query.values:
            return '', ()
        qn = self.quote_name_unless_alias
        values, update_params = [], []
        for field, model, val in self.query.values:
            if hasattr(val, 'resolve_expression'):
                val = val.resolve_expression(self.query, allow_joins=False, for_save=True)
                if val.contains_aggregate:
                    raise FieldError("Aggregate functions are not allowed in this query")
                if val.contains_over_clause:
                    raise FieldError('Window expressions are not allowed in this query.')
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
                if isinstance(field, BinaryField):
                    val = bytes(val)
                else:
                    val = field.get_db_prep_save(val, connection=self.connection)                

            # Getting the placeholder for the field.
            if hasattr(field, 'get_placeholder'):
                placeholder = field.get_placeholder(val, self, self.connection)
            else:
                placeholder = '?'
            name = field.column
            if hasattr(val, 'as_sql'):
                sql, params = self.compile(val)
                values.append('%s = %s' % (qn(name), placeholder % sql))
                update_params.extend(params)
            elif val is not None:
                values.append('%s = %s' % (qn(name), placeholder))
                update_params.append(val)
            else:
                values.append('%s = NULL' % qn(name))
        if django.VERSION>=(2,0):
            table=self.query.base_table
        if django.VERSION<(2,0):
            table = self.query.tables[0]
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
