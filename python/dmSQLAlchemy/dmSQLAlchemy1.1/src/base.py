import re

from sqlalchemy import util, sql
from sqlalchemy.engine import default, reflection
from sqlalchemy.sql import compiler, visitors, expression, util as sql_util
from sqlalchemy.sql import operators as sql_operators
from sqlalchemy.sql.elements import quoted_name
from sqlalchemy import types as sqltypes, schema as sa_schema
from sqlalchemy.types import VARCHAR, NVARCHAR, CHAR, \
    BLOB, CLOB, TIME, TIMESTAMP, FLOAT, BIGINT, INTEGER
from .types import NUMBER,_DMNumeric
from .types import colspecs, ischema_names
import sqlalchemy.sql.elements
from datetime import datetime

RESERVED_WORDS = \
    set('IFNULL ABSOLUTE ADD ALL ALTER AND ANY ARRAYLEN AS ASC ASSIGN AUDIT BEGIN BETWEEN '
        'BIGDATEDIFF BOOL BOTH BSTRING BY BYTE CALL CASE CAST TREAT CHAR CHECK CLUSTER FOR '
        'COLUMN COMMIT COMMITWORK COMMENT CONNECT CONNECT_BY_ROOT CONSTRAINT CONTAINS GOTO '
        'CONTEXT CONVERT CORRESPONDING CREATE CRYPTO CURRENT CURSOR DATEADD DATEDIFF IN IF '
        'DATEPART DECIMAL DECLARE DECODE DEFAULT DELETE DESC DISTINCT DISTRIBUTED DOUBLE IS '
        'DROP ELSE ELSEIF END EXECUTE EXISTS EXIT EXPLAIN EXTRACT FETCH FINAL FIRST FLOAT '
        'FOREIGN FROM FULLY FUNCTION GRANT GROUP HAVING IDENTITY IMMEDIATE INDEX INSERT INT '
        'INTERVAL INTO  LEAD LIKE LOGIN LOOP MEMBER NEW NEXT NOT NULL OBJECT OF ON OR ORDER '
        'OUT PARTITION PENDANT PERCENT PRIMARY PRINT PRIOR PRIVILEGES PROCEDURE PUBLIC RAISE '
        'RECORD REF REFERENCES REFERENCE REFERENCING RELATIVE REPEAT RETURN REVERSE REVOKE '
        'ROLLBACK ROW ROWNUM ROWS SAVEPOINT SCHEMA SELECT SET SOME SUBPARTITION SWITCH SYNONYM '
        'TABLE TIMESTAMPADD TIMESTAMPDIFF TO TOP TRAIL TRIGGER TRIM TRUNCATE UNION UNIQUE UNTIL '
        'UPDATE USER USING VALUES VARRAY VIEW WHEN WHENEVER WHILE WITH DISKSPACE RETURNING '
        'SBYTE SHORT USHORT UINT ULONG VOID CONST DO BREAK CONTINUE THROW FINALLY TRY CATCH '
        'PROTECTED PRIVATE ABSTRACT SEALED STATIC VIRTUAL OVERRIDE EXTERN CLASS STRUCT GET '
        'SIZEOF TYPEOF ADMIN REPLICATE VERIFY EQU EXCHANGE CLUSTERBTR LIST ARRAY ROLLUP CUBE '
        'GROUPING OVER SECTION SETS DOMAIN COLLATION OVERLAY EVERY KEEP WITHIN LNNVL NOCOPY '
        'INLINE TYPEDEF XMLTABLE XMLNAMESPACES XMLPARSE XMLAGG AUTO_INCREMENT BINARY XMLELEMENT '
        'XMLATTRIBUTES XMLSERIALIZE XMLQUERY LEXER FLASHBACK NOCYCLE NOSORT OPTIMIZE VERSIONS '
        'LARGE WITHOUT PIPE XML JSON_TABLE LESS THAN MODEL DIMENSION XMLCAST SQL_CALC_FOUND_ROWS'
        'YEAR PCTFREE UID MODE WHERE DATETIME DATE LOCK SHARE NOCOMPRESS VALUE LIMIT NOWAIT RAW '
        'VARCHAR LEVEL EXCLUSIVE THEN INTEGER IDENTIFIED SMALLINT LONG START RENAME VARCHAR2 '
        'MINUS INTERSECT OPTION SIZE RESOURCE NUMBER COMPRESS'.split())

NO_ARG_FNS = set('UID CURRENT_DATE SYSDATE USER '
                 'CURRENT_TIME CURRENT_TIMESTAMP'.split())

class DMTypeCompiler(compiler.GenericTypeCompiler):
    def visit_datetime(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_datetime', type_, **kw)
        return self.visit_DATETIME(type_, **kw)

    def visit_float(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_float', type_, **kw)
        return self.visit_FLOAT(type_, **kw)

    def visit_TINYINT(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_TINYINT', type_, **kw)
        return "TINYINT"

    def visit_BIT(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_BIT', type_, **kw)
        return "BIT"

    def visit_unicode(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_unicode', type_, **kw)

        if self.dialect._supports_nchar:
            return self.visit_NVARCHAR2(type_, **kw)
        else:
            return self.visit_VARCHAR2(type_, **kw)

    def visit_INTERVAL(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_INTERVAL', type_, **kw)

        # INTERVAL YEAR
        if type_.year_precision is not None and type_.to_month:
            return "INTERVAL YEAR(%d) TO MONTH" % (type_.year_precision)
        elif type_.year_precision is not None and not type_.to_month:
            return "INTERVAL YEAR(%d)" % (type_.year_precision)

        # INTERVAL MONTH
        elif type_.month_precision:
            return "INTERVAL MONTH(%d)" % (type_.month_precision)

        # INTERVAL DAY
        elif type_.day_precision is not None and type_.to_hour:
            return "INTERVAL DAY(%d) TO HOUR" % (type_.day_precision)
        elif type_.day_precision is not None and type_.to_minute:
            return "INTERVAL DAY(%d) TO MINUTE" % (type_.day_precision)
        elif type_.day_precision is not None and type_.second_precision is not None:
            return "INTERVAL DAY(%d) TO SECOND(%d)" % (type_.day_precision, type_.second_precision)
        elif type_.day_precision is not None:
            return "INTERVAL DAY(%d)" % (type_.day_precision)

        # INTERVAL HOUR
        elif type_.hour_precision is not None and type_.to_minute:
            return "INTERVAL HOUR(%d) TO MINUTE" % (type_.hour_precision)
        elif type_.hour_precision is not None and type_.second_precision is not None:
            return "INTERVAL HOUR(%d) TO SECOND(%d)" % (type_.hour_precision, type_.second_precision)
        elif type_.hour_precision is not None:
            return "INTERVAL HOUR(%d)" % (type_.hour_precision)

        # INTERVAL MINUTE
        elif type_.minute_precision is not None and type_.second_precision is not None:
            return "INTERVAL MINUTE(%d) TO SECOND(%d)" % (type_.minute_precision, type_.second_precision)
        elif type_.minute_precision is not None:
            return "INTERVAL MINUTE(%d)" % (type_.minute_precision)

        # INTERVAL SECOND
        elif type_.second_precision is not None:
            return "INTERVAL SECOND(%d)" % (type_.second_precision)
        else:
            return "INTERVAL DAY(2) TO SECOND(6)"   

    def visit_LONGVARCHAR(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_LONGVARCHAR', type_, **kw)
        return "LONGVARCHAR"

    def visit_TIMESTAMP(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_TIMESTAMP', type_, **kw)
        
        if type_.timezone:
            return "TIMESTAMP WITH TIME ZONE"
        else:
            return "TIMESTAMP"

    def visit_DMTIMESTAMP(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_DMTIMESTAMP', type_, **kw)

        if type_.timezone:
            return "TIMESTAMP WITH TIME ZONE"
        elif type_.local_timezone:
            return "TIMESTAMP WITH LOCAL TIME ZONE"
        else:
            return "TIMESTAMP"

    def visit_TIME(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_TIME', type_, **kw)

        if type_.timezone:
            return "TIME WITH TIME ZONE"
        else:
            return "TIME"

    def visit_IMAGE(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_IMAGE', type_, **kw)
        return "IMAGE"

    def visit_DOUBLE_PRECISION(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_DOUBLE_PRECISION', type_, **kw)
        return self._generate_numeric(type_, "DOUBLE", **kw)

    def visit_NUMBER(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_NUMBER', type_, **kw)
        return self._generate_numeric(type_, "NUMBER", **kw)

    def _generate_numeric(self, type_, name, precision=None, scale=None, **kw):
        self.dialect.trace_process('DMTypeCompiler', '_generate_numeric', type_, name, precision=None, scale=None, **kw)

        if precision is None:
            precision = type_.precision

        if scale is None:
            scale = getattr(type_, 'scale', None)

        if precision is None:
            return name
        elif scale is None:
            n = "%(name)s(%(precision)s)"
            return n % {'name': name, 'precision': precision}
        else:
            n = "%(name)s(%(precision)s, %(scale)s)"
            return n % {'name': name, 'precision': precision, 'scale': scale}

    def visit_string(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_string', type_, **kw)
        return self.visit_VARCHAR2(type_, **kw)

    def visit_VARCHAR2(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_VARCHAR2', type_, **kw)
        return self._visit_varchar(type_, '', '2')

    def visit_NVARCHAR2(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_NVARCHAR2', type_, **kw)
        return self._visit_varchar(type_, 'N', '2')

    visit_NVARCHAR = visit_NVARCHAR2

    def visit_VARCHAR(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_VARCHAR', type_, **kw)
        return self._visit_varchar(type_, '', '')

    def visit_LongVarBinary(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_LongVarBinary', type_, **kw)
        return "LONGVARBINARY"

    def _visit_varchar(self, type_, n, num):
        self.dialect.trace_process('DMTypeCompiler', '_visit_varchar', type_, n, num)
        if not type_.length:
            return "%(n)sVARCHAR%(two)s" % {'two': num, 'n': n}
        elif not n and self.dialect._supports_char_length:
            varchar = "VARCHAR%(two)s(%(length)s CHAR)"
            return varchar % {'length': type_.length, 'two': num}
        else:
            varchar = "%(n)sVARCHAR%(two)s(%(length)s)"
            return varchar % {'length': type_.length, 'two': num, 'n': n}

    def visit_text(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_text', type_, **kw)
        return "TEXT"

    def visit_unicode_text(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_unicode_text', type_, **kw)

        if self.dialect._supports_nchar:
            return self.visit_NCLOB(type_, **kw)
        else:
            return self.visit_CLOB(type_, **kw)

    def visit_large_binary(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_large_binary', type_, **kw)
        return self.visit_BLOB(type_, **kw)

    def visit_big_integer(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_big_integer', type_, **kw)
        return self.visit_NUMBER(type_, precision=19, **kw)

    def visit_boolean(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_boolean', type_, **kw)
        return "SMALLINT"

    def visit_ROWID(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_ROWID', type_, **kw)
        return "ROWID"

    # for trace only
    def visit_BIGINT(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_BIGINT', type_, **kw)
        return super(DMTypeCompiler, self).visit_BIGINT(type_, **kw)

    def visit_BINARY(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_BINARY', type_, **kw)
        return super(DMTypeCompiler, self).visit_BINARY(type_, **kw)

    def visit_BLOB(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_BLOB', type_, **kw)
        return super(DMTypeCompiler, self).visit_BLOB(type_, **kw)

    def visit_BOOLEAN(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_BOOLEAN', type_, **kw)
        return super(DMTypeCompiler, self).visit_BOOLEAN(type_, **kw)

    def visit_CHAR(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_CHAR', type_, **kw)
        return super(DMTypeCompiler, self).visit_CHAR(type_, **kw)

    def visit_CLOB(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_CLOB', type_, **kw)
        return super(DMTypeCompiler, self).visit_CLOB(type_, **kw)

    def visit_DATE(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_DATE', type_, **kw)
        return super(DMTypeCompiler, self).visit_DATE(type_, **kw)

    def visit_date(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_date', type_, **kw)
        return super(DMTypeCompiler, self).visit_date(type_, **kw)

    def visit_DATETIME(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_DATETIME', type_, **kw)
        return super(DMTypeCompiler, self).visit_DATETIME(type_, **kw)
        
    def visit_DECIMAL(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_DECIMAL', type_, **kw)
        return super(DMTypeCompiler, self).visit_DECIMAL(type_, **kw)
        
    def visit_enum(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_enum', type_, **kw)
        return super(DMTypeCompiler, self).visit_enum(type_, **kw)
        
    def visit_FLOAT(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_FLOAT', type_, **kw)
        return super(DMTypeCompiler, self).visit_FLOAT(type_, **kw)
        
    def visit_INTEGER(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_INTEGER', type_, **kw)
        return super(DMTypeCompiler, self).visit_INTEGER(type_, **kw)
        
    def visit_integer(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_integer', type_, **kw)
        return super(DMTypeCompiler, self).visit_integer(type_, **kw)
        
    def visit_NCHAR(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_NCHAR', type_, **kw)
        return super(DMTypeCompiler, self).visit_NCHAR(type_, **kw)
        
    def visit_NCLOB(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_NCLOB', type_, **kw)
        return super(DMTypeCompiler, self).visit_NCLOB(type_, **kw)
        
    def visit_null(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_null', type_, **kw)
        return super(DMTypeCompiler, self).visit_null(type_, **kw)
        
    def visit_NUMERIC(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_NUMERIC', type_, **kw)
        return super(DMTypeCompiler, self).visit_NUMERIC(type_, **kw)
        
    def visit_numeric(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_numeric', type_, **kw)
        return super(DMTypeCompiler, self).visit_numeric(type_, **kw)
        
    def visit_NVARCHAR(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_NVARCHAR', type_, **kw)
        return super(DMTypeCompiler, self).visit_NVARCHAR(type_, **kw)
        
    def visit_REAL(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_REAL', type_, **kw)
        return super(DMTypeCompiler, self).visit_REAL(type_, **kw)

    def visit_JSON(self,type_,**kw):
        return "JSON"

    def visit_real(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_real', type_, **kw)
        return super(DMTypeCompiler, self).visit_real(type_, **kw)
        
    def visit_SMALLINT(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_SMALLINT', type_, **kw)
        return super(DMTypeCompiler, self).visit_SMALLINT(type_, **kw)
        
    def visit_small_integer(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_small_integer', type_, **kw)
        return super(DMTypeCompiler, self).visit_small_integer(type_, **kw)
        
    def visit_TEXT(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_TEXT', type_, **kw)
        return super(DMTypeCompiler, self).visit_TEXT(type_, **kw)
        
    def visit_time(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_time', type_, **kw)
        return super(DMTypeCompiler, self).visit_time(type_, **kw)
        
    def visit_type_decorator(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_type_decorator', type_, **kw)
        return super(DMTypeCompiler, self).visit_type_decorator(type_, **kw)
        
    def visit_user_defined(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_user_defined', type_, **kw)
        return super(DMTypeCompiler, self).visit_user_defined(type_, **kw)
        
    def visit_VARBINARY(self, type_, **kw):
        self.dialect.trace_process('DMTypeCompiler', 'visit_VARBINARY', type_, **kw)
        return super(DMTypeCompiler, self).visit_VARBINARY(type_, **kw)


class DMCompiler(compiler.SQLCompiler):
    compound_keywords = util.update_copy(
        compiler.SQLCompiler.compound_keywords,
        {
            expression.CompoundSelect.EXCEPT: 'MINUS'
        }
    )

    def __init__(self, *args, **kwargs):
        self.__wheres = {}
        self._quoted_bind_names = {}
        super(DMCompiler, self).__init__(*args, **kwargs)

    def visit_mod_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_mod_binary', binary, operator, **kw)
        return "mod(%s, %s)" % (self.process(binary.left, **kw),
                                self.process(binary.right, **kw))

    def visit_now_func(self, fn, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_now_func', fn, **kw)
        return "CURRENT_TIMESTAMP"

    def visit_char_length_func(self, fn, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_char_length_func', fn, **kw)
        return "LENGTH" + self.function_argspec(fn, **kw)

    def visit_match_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_match_op_binary', binary, operator, **kw)
        return "CONTAINS (%s, %s)" % (self.process(binary.left),
                                      self.process(binary.right))

    def visit_true(self, expr, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_true', expr, **kw)
        return '1'

    def visit_false(self, expr, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_false', expr, **kw)
        return '0'

    def get_cte_preamble(self, recursive):
        self.dialect.trace_process('DMCompiler', 'get_cte_preamble', recursive)
        return "WITH"

    def get_select_hint_text(self, byfroms):
        self.dialect.trace_process('DMCompiler', 'get_select_hint_text', byfroms)
        return " ".join(
            "/*+ %s */" % text for table, text in byfroms.items()
        )

    def function_argspec(self, fn, **kw):
        self.dialect.trace_process('DMCompiler', 'function_argspec', fn, **kw)
        if len(fn.clauses) > 0 or fn.name.upper() not in NO_ARG_FNS:
            return compiler.SQLCompiler.function_argspec(self, fn, **kw)
        else:
            return ""

    def default_from(self):
        self.dialect.trace_process('DMCompiler', 'default_from')
        return " FROM DUAL"
    
    def _generate_generic_unary_operator(self, unary, opstring, **kw):
        self.dialect.trace_process('DMCompiler', '_generate_generic_unary_operator', unary, opstring, **kw)
        if opstring == 'EXISTS ':
            rs = 'SELECT COUNT(*) FROM ' + unary.element._compiler_dispatch(self, **kw)
            return 'CASE WHEN (' + rs + ' AS R_EXISTS) > 0 THEN 1 ELSE 0 END '
        return opstring + unary.element._compiler_dispatch(self, **kw)    

    def visit_join(self, join, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_join', join, **kwargs)
        if self.dialect.use_ansi:
            return compiler.SQLCompiler.visit_join(self, join, **kwargs)
        else:
            kwargs['asfrom'] = True
            if isinstance(join.right, expression.FromGrouping):
                right = join.right.element
            else:
                right = join.right
            return self.process(join.left, **kwargs) + \
                ", " + self.process(right, **kwargs)

    def _get_nonansi_join_whereclause(self, froms):
        self.dialect.trace_process('DMCompiler', '_get_nonansi_join_whereclause', froms)
        clauses = []

        def visit_join(join):
            self.dialect.trace_process('DMCompiler', '_get_nonansi_join_whereclause:visit_join', join)
            if join.isouter:
                def visit_binary(binary):
                    self.dialect.trace_process('DMCompiler', '_get_nonansi_join_whereclause:visit_join:visit_binary', binary)
                    if binary.operator == sql_operators.eq:
                        if join.right.is_derived_from(binary.left.table):
                            binary.left = _OuterJoinColumn(binary.left)
                        elif join.right.is_derived_from(binary.right.table):
                            binary.right = _OuterJoinColumn(binary.right)
                clauses.append(visitors.cloned_traverse(
                    join.onclause, {}, {'binary': visit_binary}))
            else:
                clauses.append(join.onclause)

            for j in join.left, join.right:
                if isinstance(j, expression.Join):
                    visit_join(j)
                elif isinstance(j, expression.FromGrouping):
                    visit_join(j.element)

        for f in froms:
            if isinstance(f, expression.Join):
                visit_join(f)

        if not clauses:
            return None
        else:
            return sql.and_(*clauses)

    def visit_outer_join_column(self, vc, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_outer_join_column', vc, **kw)
        return self.process(vc.column, **kw) + "(+)"

    def visit_sequence(self, seq):
        self.dialect.trace_process('DMCompiler', 'visit_sequence', seq)
        return (self.dialect.identifier_preparer.format_sequence(seq) +
                ".nextval")

    def get_render_as_alias_suffix(self, alias_name_text):
        self.dialect.trace_process('DMCompiler', 'get_render_as_alias_suffix', alias_name_text)
        return " " + alias_name_text

    def returning_clause(self, stmt, returning_cols):
        self.dialect.trace_process('DMCompiler', 'returning_clause', stmt, returning_cols)
        columns = []
        binds = []
        for i, column in enumerate(
                expression._select_iterables(returning_cols)):
            if column.type._has_column_expression:
                col_expr = column.type.column_expression(column)
            else:
                col_expr = column
            columns.append(self.process(col_expr, within_columns_clause = False))
            outparam = sql.outparam("ret_%d" % i, type_=column.type)
            self.binds[outparam.key] = outparam
            binds.append(
                self.bindparam_string(self._truncate_bindparam(outparam)))

            self._add_to_result_map(
                outparam.key, outparam.key,
                (column, getattr(column, 'name', None),
                 getattr(column, 'key', None)),
                column.type
            )

        return 'RETURNING ' + ', '.join(columns) + " INTO " + ", ".join(binds)

    def _TODO_visit_compound_select(self, select):

        pass

    def visit_select(self, select, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_select', select, **kwargs)
        """Look for ``LIMIT`` and OFFSET in a select statement, and if
        so tries to wrap it in a subquery with ``rownum`` criterion.
        """

        if not getattr(select, '_dm_visit', None):
            if not self.dialect.use_ansi:
                froms = self._display_froms_for_select(
                    select, kwargs.get('asfrom', False))
                whereclause = self._get_nonansi_join_whereclause(froms)
                if whereclause is not None:
                    select = select.where(whereclause)
                    select._dm_visit = True

            limit_clause = select._limit_clause
            offset_clause = select._offset_clause
            if limit_clause is not None or offset_clause is not None:
                kwargs['select_wraps_for'] = select
                select = select._generate()
                select._dm_visit = True

                # Wrap the middle select and add the hint
                limitselect = sql.select([c for c in select.c])
                if limit_clause is not None and \
                    self.dialect.optimize_limits and \
                        select._simple_int_limit:
                    limitselect = limitselect.prefix_with(
                        "/*+ FIRST_ROWS(%d) */" %
                        select._limit)

                limitselect._dm_visit = True
                limitselect._is_wrapper = True

                # add expressions to accommodate FOR UPDATE OF
                for_update = select._for_update_arg
                if for_update is not None and for_update.of:
                    for_update = for_update._clone()
                    for_update._copy_internals()

                    for elem in for_update.of:
                        select.append_column(elem)

                    adapter = sql_util.ClauseAdapter(select)
                    for_update.of = [
                        adapter.traverse(elem)
                        for elem in for_update.of]

                # If needed, add the limiting clause
                if limit_clause is not None:
                    if not self.dialect.use_binds_for_limits:
                        # use simple int limits, will raise an exception
                        # if the limit isn't specified this way
                        max_row = select._limit

                        if offset_clause is not None:
                            max_row += select._offset
                        max_row = sql.literal_column("%d" % max_row)
                    else:
                        max_row = limit_clause
                        if offset_clause is not None:
                            max_row = max_row + offset_clause
                    limitselect.append_whereclause(
                        sql.literal_column("ROWNUM") <= max_row)

                # If needed, add the ora_rn, and wrap again with offset.
                if offset_clause is None:
                    limitselect._for_update_arg = for_update
                    select = limitselect
                else:
                    limitselect = limitselect.column(
                        sql.literal_column("ROWNUM").label("ora_rn"))
                    limitselect._dm_visit = True
                    limitselect._is_wrapper = True

                    offsetselect = sql.select(
                        [c for c in limitselect.c if c.key != 'ora_rn'])
                    offsetselect._dm_visit = True
                    offsetselect._is_wrapper = True

                    if for_update is not None and for_update.of:
                        for elem in for_update.of:
                            if limitselect.corresponding_column(elem) is None:
                                limitselect.append_column(elem)

                    if not self.dialect.use_binds_for_limits:
                        offset_clause = sql.literal_column(
                            "%d" % select._offset)
                    offsetselect.append_whereclause(
                        sql.literal_column("ora_rn") > offset_clause)

                    offsetselect._for_update_arg = for_update
                    select = offsetselect

        return compiler.SQLCompiler.visit_select(self, select, **kwargs)

    def limit_clause(self, select, **kw):
        text = ""
        if select._limit_clause is not None:
            text += "\n LIMIT " + self.process(select._limit_clause, **kw)
        if select._offset_clause is not None:
            if select._limit_clause is None:
                text += " LIMIT 1 "
            text += " OFFSET " + self.process(select._offset_clause, **kw)
        if select._offset_clause is not None:
            text += "\n OFFSET %s ROWS" % self.process(
                select._offset_clause, **kw
            )
        if select._fetch_clause is not None:
            text += "\n FETCH FIRST %s%s ROWS %s" % (
                self.process(select._fetch_clause, **kw),
                " PERCENT" if select._fetch_clause_options["percent"] else "",
                "WITH TIES"
                if select._fetch_clause_options["with_ties"]
                else "ONLY",
            )
        return text

    def for_update_clause(self, select, **kw):
        self.dialect.trace_process('DMCompiler', 'for_update_clause', select, **kw)
        if self.is_subquery():
            return ""

        tmp = ' FOR UPDATE'

        if select._for_update_arg.of:
            tmp += ' OF ' + ', '.join(
                self.process(elem, **kw) for elem in
                select._for_update_arg.of
            )

        if select._for_update_arg.nowait:
            tmp += " NOWAIT"
        if select._for_update_arg.skip_locked:
            tmp += " SKIP LOCKED"

        return tmp
    
    # for trace only
    def escape_literal_column(self, text):
        self.dialect.trace_process('DMCompiler', 'escape_literal_column', text)
        return super(DMCompiler, self).escape_literal_column(text)
        
    def format_from_hint_text(self, sqltext, table, hint, iscrud):
        self.dialect.trace_process('DMCompiler', 'format_from_hint_text', sqltext, table, hint, iscrud)
        return super(DMCompiler, self).format_from_hint_text(sqltext, table, hint, iscrud)
        
    def get_crud_hint_text(self, table, text):
        self.dialect.trace_process('DMCompiler', 'get_crud_hint_text', table, text)
        return super(DMCompiler, self).get_crud_hint_text(table, text)
        
    def get_from_hint_text(self, table, text):
        self.dialect.trace_process('DMCompiler', 'get_from_hint_text', table, text)
        return super(DMCompiler, self).get_from_hint_text(table, text)
        
    def get_select_precolumns(self, select, **kw):
        self.dialect.trace_process('DMCompiler', 'get_select_precolumns', select, **kw)
        return super(DMCompiler, self).get_select_precolumns(select, **kw)
        
    def get_statement_hint_text(self, hint_texts):
        self.dialect.trace_process('DMCompiler', 'get_statement_hint_text', hint_texts)
        return super(DMCompiler, self).get_statement_hint_text(hint_texts)
        
    def is_subquery(self):
        self.dialect.trace_process('DMCompiler', 'is_subquery')
        return super(DMCompiler, self).is_subquery()
        
    def order_by_clause(self, select, **kw):
        self.dialect.trace_process('DMCompiler', 'order_by_clause', select, **kw)
        return super(DMCompiler, self).order_by_clause(select, **kw)
        
    def post_process_text(self, text):
        self.dialect.trace_process('DMCompiler', 'post_process_text', text)
        return super(DMCompiler, self).post_process_text(text)
        
    def render_literal_bindparam(self, bindparam, **kw):
        self.dialect.trace_process('DMCompiler', 'render_literal_bindparam', bindparam, **kw)
        return super(DMCompiler, self).render_literal_bindparam(bindparam, **kw)
        
    def render_literal_value(self, value, type_):
        self.dialect.trace_process('DMCompiler', 'render_literal_value', value, type_)
        return super(DMCompiler, self).render_literal_value(value, type_)
        
    def update_from_clause(self, update_stmt,
                           from_table, extra_froms,
                           from_hints,
                           **kw):
        self.dialect.trace_process('DMCompiler', 'update_from_clause', 
                                   update_stmt, from_table, 
                                   extra_froms, from_hints, 
                                   **kw)
        return super(DMCompiler, self).update_from_clause(update_stmt,
                                                          from_table, extra_froms,
                                                          from_hints,
                                                          **kw)
    def update_limit_clause(self, update_stmt):
        self.dialect.trace_process('DMCompiler', 'update_limit_clause', update_stmt)
        return super(DMCompiler, self).update_limit_clause(update_stmt)
        
    def update_tables_clause(self, update_stmt, from_table,
                             extra_froms, **kw):
        self.dialect.trace_process('DMCompiler', 'update_tables_clause',
                                   update_stmt, from_table,
                                   extra_froms, **kw)
        return super(DMCompiler, self).update_tables_clause(update_stmt, from_table,
                                                            extra_froms, **kw)
        
    def visit_alias(self, alias, asfrom=False, ashint=False,
                    iscrud=False,
                    fromhints=None, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_alias',
                                   alias, asfrom, ashint,
                                   iscrud, fromhints, **kwargs)
        return super(DMCompiler, self).visit_alias(alias, asfrom, ashint,
                                                   iscrud, fromhints, **kwargs)
        
    def visit_between_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_between_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_between_op_binary(binary, operator, **kw)
        
    def visit_binary(self, binary, override_operator=None,
                     eager_grouping=False, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_binary', 
                                   binary, override_operator, 
                                   eager_grouping, **kw)
        return super(DMCompiler, self).visit_binary(binary, override_operator,
                                                    eager_grouping, **kw)
        
    def visit_bindparam(self, bindparam, within_columns_clause=False,
                        literal_binds=False,
                        skip_bind_expression=False,
                        **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_bindparam', 
                                   bindparam, within_columns_clause,
                                   literal_binds, skip_bind_expression, **kwargs)
        return super(DMCompiler, self).visit_bindparam(bindparam, within_columns_clause,
                                                       literal_binds, skip_bind_expression,
                                                       **kwargs)
        
    def visit_case(self, clause, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_case', clause, **kwargs)
        return super(DMCompiler, self).visit_case(clause, **kwargs)
        
    def visit_cast(self, cast, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_cast', cast, **kwargs)
        return super(DMCompiler, self).visit_cast(cast, **kwargs)
        
    def visit_clauselist(self, clauselist, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_clauselist', clauselist, **kw)
        return super(DMCompiler, self).visit_clauselist(clauselist, **kw)
        
    def visit_column(self, column, add_to_result_map=None,
                     include_table=True, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_column', 
                                   column, add_to_result_map,
                                   include_table, **kwargs)
        return super(DMCompiler, self).visit_column(column, add_to_result_map,
                                                    include_table, **kwargs)
        
    def visit_compound_select(self, cs, asfrom=False,
                              parens=True, compound_index=0, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_compound_select', 
                                   cs, asfrom,
                                   parens, compound_index, **kwargs)
        return super(DMCompiler, self).visit_compound_select(cs, asfrom,
                                                             parens, compound_index, **kwargs)
        
    def visit_contains_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_contains_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_contains_op_binary(binary, operator, **kw)
        
    def visit_cte(self, cte, asfrom=False, ashint=False,
                  fromhints=None,
                  **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_cte', 
                                   cte, asfrom, ashint,
                                   fromhints, **kwargs)
        return super(DMCompiler, self).visit_cte(cte, asfrom, ashint, fromhints, **kwargs)
        
    def visit_custom_op_binary(self, element, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_custom_op_binary', element, operator, **kw)
        return super(DMCompiler, self).visit_custom_op_binary(element, operator, **kw)
        
    def visit_custom_op_unary_modifier(self, element, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_custom_op_unary_modifier', element, operator, **kw)
        return super(DMCompiler, self).visit_custom_op_unary_modifier(element, operator, **kw)
        
    def visit_custom_op_unary_operator(self, element, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_custom_op_unary_operator', element, operator, **kw)
        return super(DMCompiler, self).visit_custom_op_unary_operator(element, operator, **kw)
        
    def visit_delete(self, delete_stmt, asfrom=False, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_delete', delete_stmt, asfrom, **kw)
        return super(DMCompiler, self).visit_delete(delete_stmt, asfrom, **kw)
        
    def visit_endswith_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_endswith_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_endswith_op_binary(binary, operator, **kw)
        
    def visit_extract(self, extract, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_extract', extract, **kwargs)
        super(DMCompiler, self).visit_extract(extract, **kwargs)
        
    def visit_fromclause(self, fromclause, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_fromclause', fromclause, **kwargs)
        return super(DMCompiler, self).visit_fromclause(fromclause, **kwargs)
        
    def visit_funcfilter(self, funcfilter, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_funcfilter', funcfilter, **kwargs)
        super(DMCompiler, self).visit_funcfilter(funcfilter, **kwargs)
        
    def visit_function(self, func, add_to_result_map=None, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_function', func, add_to_result_map, **kwargs)
        return super(DMCompiler, self).visit_function(func, add_to_result_map, **kwargs)
        
    def visit_grouping(self, grouping, asfrom=False, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_grouping', grouping, asfrom, **kwargs)
        return super(DMCompiler, self).visit_grouping(grouping, asfrom, **kwargs)
        
    def visit_ilike_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_ilike_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_ilike_op_binary(binary, operator, **kw)
        
    def visit_index(self, index, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_index', index, **kwargs)
        return super(DMCompiler, self).visit_index(index, **kwargs)
        
    def visit_insert(self, insert_stmt, asfrom=False, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_insert', insert_stmt, asfrom, **kw)
        return super(DMCompiler, self).visit_insert(insert_stmt, asfrom, **kw)
        
    def visit_isfalse_unary_operator(self, element, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_isfalse_unary_operator', element, operator, **kw)
        return super(DMCompiler, self).visit_isfalse_unary_operator(element, operator, **kw)
        
    def visit_istrue_unary_operator(self, element, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_istrue_unary_operator', element, operator, **kw)
        return super(DMCompiler, self).visit_istrue_unary_operator(element, operator, **kw)
        
    def visit_label(self, label,
                    add_to_result_map=None,
                    within_label_clause=False,
                    within_columns_clause=False,
                    render_label_as_label=None,
                    **kw):
        self.dialect.trace_process('DMCompiler', 'visit_label', 
                                   label, add_to_result_map,
                                   within_label_clause, within_columns_clause,
                                   render_label_as_label, **kw)
        return super(DMCompiler, self).visit_label(label, add_to_result_map,
                                                   within_label_clause, within_columns_clause,
                                                   render_label_as_label, **kw)
        
    def visit_label_reference(self, element, within_columns_clause=False, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_label_reference', element, within_columns_clause, **kwargs)
        return super(DMCompiler, self).visit_label_reference(element, within_columns_clause, **kwargs)
        
    def visit_lateral(self, lateral, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_lateral', lateral, **kw)
        return super(DMCompiler, self).visit_lateral(lateral, **kw)
        
    def visit_like_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_like_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_like_op_binary(binary, operator, **kw)
        
    def visit_next_value_func(self, next_value, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_next_value_func', next_value, **kw)
        return super(DMCompiler, self).visit_next_value_func(next_value, **kw)
        
    def visit_notbetween_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_notbetween_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_notbetween_op_binary(binary, operator, **kw)
        
    def visit_notcontains_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_notcontains_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_notcontains_op_binary(binary, operator, **kw)
        
    def visit_notendswith_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_notendswith_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_notendswith_op_binary(binary, operator, **kw)
        
    def visit_notilike_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_notilike_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_notilike_op_binary(binary, operator, **kw)
        
    def visit_notlike_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_notlike_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_notlike_op_binary(binary, operator, **kw)
        
    def visit_notmatch_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_notmatch_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_notmatch_op_binary(binary, operator, **kw)
        
    def visit_notstartswith_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_notstartswith_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_notstartswith_op_binary(binary, operator, **kw)
        
    def visit_null(self, expr, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_null', expr, **kw)
        return super(DMCompiler, self).visit_null(expr, **kw)
        
    def visit_over(self, over, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_over', over, **kwargs)
        return super(DMCompiler, self).visit_over(over, **kwargs)
        
    def visit_release_savepoint(self, savepoint_stmt):
        self.dialect.trace_process('DMCompiler', 'visit_release_savepoint', savepoint_stmt)
        return super(DMCompiler, self).visit_release_savepoint(savepoint_stmt)
        
    def visit_rollback_to_savepoint(self, savepoint_stmt):
        self.dialect.trace_process('DMCompiler', 'visit_rollback_to_savepoint', savepoint_stmt)
        return super(DMCompiler, self).visit_rollback_to_savepoint(savepoint_stmt)
        
    def visit_savepoint(self, savepoint_stmt):
        self.dialect.trace_process('DMCompiler', 'visit_savepoint', savepoint_stmt)
        return super(DMCompiler, self).visit_savepoint(savepoint_stmt)
        
    def visit_select(self, select, asfrom=False, parens=True,
                     fromhints=None,
                     compound_index=0,
                     nested_join_translation=False,
                     select_wraps_for=None,
                     lateral=False,
                     **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_select', 
                                   select, asfrom, parens,
                                   fromhints, compound_index,
                                   nested_join_translation, select_wraps_for,
                                   lateral, **kwargs)
        return super(DMCompiler, self).visit_select(select, asfrom, parens,
                                                    fromhints, compound_index,
                                                    nested_join_translation, select_wraps_for,
                                                    lateral, **kwargs)
        
    def visit_startswith_op_binary(self, binary, operator, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_startswith_op_binary', binary, operator, **kw)
        return super(DMCompiler, self).visit_startswith_op_binary(binary, operator, **kw)
        
    def visit_table(self, table, asfrom=False, iscrud=False, ashint=False,
                    fromhints=None, use_schema=True, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_table', 
                                   table, asfrom, iscrud, ashint,
                                   fromhints, use_schema, **kwargs)
        return super(DMCompiler, self).visit_table(table, asfrom, iscrud, ashint,
                                                   fromhints, use_schema, **kwargs)
        
    def visit_tablesample(self, tablesample, asfrom=False, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_tablesample', tablesample, asfrom, **kw)
        return super(DMCompiler, self).visit_tablesample(tablesample, asfrom, **kw)
        
    def visit_textclause(self, textclause, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_textclause', textclause, **kw)
        return super(DMCompiler, self).visit_textclause(textclause, **kw)
        
    def visit_textual_label_reference(self, element, within_columns_clause=False, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_textual_label_reference', 
                                   element, within_columns_clause, **kwargs)
        return super(DMCompiler, self).visit_textual_label_reference(element, within_columns_clause, **kwargs)
        
    def visit_text_as_from(self, taf,
                           compound_index=None,
                           asfrom=False,
                           parens=True, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_text_as_from',
                                   taf, compound_index,
                                   asfrom, parens, **kw)
        return super(DMCompiler, self).visit_text_as_from(taf, compound_index, asfrom, parens, **kw)
        
    def visit_typeclause(self, typeclause, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_typeclause', typeclause, **kw)
        return super(DMCompiler, self).visit_typeclause(typeclause, **kw)
        
    def visit_type_coerce(self, type_coerce, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_type_coerce', type_coerce, **kw)
        return super(DMCompiler, self).visit_type_coerce(type_coerce, **kw)
        
    def visit_unary(self, unary, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_unary', unary, **kw)
        return super(DMCompiler, self).visit_unary(unary, **kw)
        
    def visit_update(self, update_stmt, asfrom=False, **kw):
        self.dialect.trace_process('DMCompiler', 'visit_update', update_stmt, asfrom, **kw)
        return super(DMCompiler, self).visit_update(update_stmt, asfrom, **kw)
        
    def visit_withingroup(self, withingroup, **kwargs):
        self.dialect.trace_process('DMCompiler', 'visit_withingroup', withingroup, **kwargs)
        return super(DMCompiler, self).visit_withingroup(withingroup, **kwargs)
        
    def _add_to_result_map(self, keyname, name, objects, type_):
        self.dialect.trace_process('DMCompiler', '_add_to_result_map', keyname, name, objects, type_)
        super(DMCompiler, self)._add_to_result_map(keyname, name, objects, type_)
        
    def _anonymize(self, name):
        self.dialect.trace_process('DMCompiler', '_anonymize', name)
        return super(DMCompiler, self)._anonymize(name)
        
    def _process_anon(self, key):
        self.dialect.trace_process('DMCompiler', '_process_anon', key)
        return super(DMCompiler, self)._process_anon(key)
        
    def _render_cte_clause(self):
        self.dialect.trace_process('DMCompiler', '_render_cte_clause')
        return super(DMCompiler, self)._render_cte_clause()
        
    def _setup_crud_hints(self, stmt, table_text):
        self.dialect.trace_process('DMCompiler', '_setup_crud_hints', stmt, table_text)
        return super(DMCompiler, self)._setup_crud_hints(stmt, table_text)
        
    def _setup_select_hints(self, select):
        self.dialect.trace_process('DMCompiler', '_setup_select_hints', select)
        return super(DMCompiler, self)._setup_select_hints(select)
        
    def _setup_select_stack(self, select, entry, asfrom, lateral):
        self.dialect.trace_process('DMCompiler', '_setup_select_stack', select, entry, asfrom, lateral)
        return super(DMCompiler, self)._setup_select_stack(select, entry, asfrom, lateral)
        
    def _transform_result_map_for_nested_joins(self, select, transformed_select):
        self.dialect.trace_process('DMCompiler', '_transform_result_map_for_nested_joins', 
                                   select, transformed_select)
        super(DMCompiler, self)._transform_result_map_for_nested_joins(select, transformed_select)
        
    def _transform_select_for_nested_joins(self, select):
        self.dialect.trace_process('DMCompiler', '_transform_select_for_nested_joins', select)
        return super(DMCompiler, self)._transform_select_for_nested_joins(select)
        
    def _truncated_identifier(self, ident_class, name):
        self.dialect.trace_process('DMCompiler', '_truncated_identifier', ident_class, name)
        return super(DMCompiler, self)._truncated_identifier(ident_class, name)
        
    def _truncate_bindparam(self, bindparam):
        self.dialect.trace_process('DMCompiler', '_truncate_bindparam', bindparam)
        return super(DMCompiler, self)._truncate_bindparam(bindparam)

    def _render_json_extract_from_binary(self, binary, operator, **kw):
        # note we are intentionally calling upon the process() calls in the
        # order in which they appear in the SQL String as this is used
        # by positional parameter rendering

        # if binary.type._type_affinity is sqltypes.JSON:
        return "json_value(%s, %s)" % (
            self.process(binary.left, **kw),
            self.process(binary.right, **kw),
        )

    def visit_json_getitem_op_binary(self, binary, operator, **kw):
        return self._render_json_extract_from_binary(binary, operator, **kw)

    def visit_json_path_getitem_op_binary(self, binary, operator, **kw):
        return self._render_json_extract_from_binary(binary, operator, **kw)

class DMDDLCompiler(compiler.DDLCompiler):
    
    def get_column_specification(self, column, **kwargs):
        self.dialect.trace_process('DMDDLCompiler', 'get_column_specification', column, **kwargs)
        
        colspec = self.preparer.format_column(column) + " " + \
            self.dialect.type_compiler.process(
                column.type, type_expression=column)
        default = self.get_column_default_string(column)
        if default is not None:
            colspec += " DEFAULT " + default

        if not column.nullable:
            colspec += " NOT NULL"
            
        if column.autoincrement == True:
            colspec += " IDENTITY(1, 1)"
            
        return colspec        

    def define_constraint_cascades(self, constraint):
        self.dialect.trace_process('DMDDLCompiler', 'define_constraint_cascades', constraint)
        
        text = ""
        if constraint.ondelete is not None:
            text += " ON DELETE %s" % constraint.ondelete

        if constraint.onupdate is not None:
            text += " ON UPDATE %s" % constraint.onupdate        

        return text
    
    def visit_unique_constraint(self, constraint):
        self.dialect.trace_process('DMDDLCompiler', 'visit_unique_constraint', constraint)
        
        if len(constraint) == 0:
            return ''
        text = ""
        if constraint.name is not None:
            formatted_name = self.preparer.format_constraint(constraint)
            text += "CONSTRAINT %s " % formatted_name
        else:
            formatted_name = "".join("%s_%s_" % (c.table,c.name)
                                     for c in constraint)
            formatted_name += "key"
            text += "CONSTRAINT %s " % formatted_name
            
        text += "UNIQUE (%s)" % (
                ', '.join(self.preparer.quote(c.name)
                              for c in constraint))
        text += self.define_constraint_deferrability(constraint)
        return text    

    def visit_create_index(self, create):
        self.dialect.trace_process('DMDDLCompiler', 'visit_create_index', create)
        
        index = create.element
        self._verify_index_table(index)
        preparer = self.preparer
        text = "CREATE "
        if index.unique:
            text += "UNIQUE "
        if index.dialect_options['dm']['bitmap']:
            text += "BITMAP "
        text += "INDEX %s ON %s (%s)" % (
            self._prepared_index_name(index, include_schema=True),
            preparer.format_table(index.table, use_schema=True),
            ', '.join(
                self.sql_compiler.process(
                    expr,
                    include_table=False, literal_binds=True)
                for expr in index.expressions)
        )
        if index.dialect_options['dm']['compress'] is not False:
            if index.dialect_options['dm']['compress'] is True:
                text += " COMPRESS"
            else:
                text += " COMPRESS %d" % (
                    index.dialect_options['dm']['compress']
                )
        return text

    def post_create_table(self, table):
        self.dialect.trace_process('DMDDLCompiler', 'post_create_table', table)
        
        table_opts = []
        opts = table.dialect_options['dm']

        if opts['on_commit']:
            on_commit_options = opts['on_commit'].replace("_", " ").upper()
            table_opts.append('\n ON COMMIT %s' % on_commit_options)

        if opts['compress']:
            if opts['compress'] is True:
                table_opts.append("\n COMPRESS")
            else:
                table_opts.append("\n COMPRESS FOR %s" % (
                    opts['compress']
                ))

        return ''.join(table_opts)
    
    # for trace only
    def construct_params(self, params=None):
        self.dialect.trace_process('DMDDLCompiler', 'construct_params', params)
        return super(DMDDLCompiler, self).construct_params(params)
        
    def create_table_constraints(self, table, _include_foreign_key_constraints=None):
        self.dialect.trace_process('DMDDLCompiler', 'create_table_constraints', 
                                   table, _include_foreign_key_constraints)
        return super(DMDDLCompiler, self).create_table_constraints(table, _include_foreign_key_constraints)
        
    def create_table_suffix(self, table):
        self.dialect.trace_process('DMDDLCompiler', 'create_table_suffix', table)
        return super(DMDDLCompiler, self).create_table_suffix(table)
        
    def define_constraint_deferrability(self, constraint):
        self.dialect.trace_process('DMDDLCompiler', 'define_constraint_deferrability', constraint)
        return super(DMDDLCompiler, self).define_constraint_deferrability(constraint)
        
    def define_constraint_match(self, constraint):
        self.dialect.trace_process('DMDDLCompiler', 'define_constraint_match', constraint)
        return super(DMDDLCompiler, self).define_constraint_match(constraint)
        
    def define_constraint_remote_table(self, constraint, table, preparer):
        self.dialect.trace_process('DMDDLCompiler', 'define_constraint_remote_table', constraint, table, preparer)
        return super(DMDDLCompiler, self).define_constraint_remote_table(constraint, table, preparer)
        
    def get_column_default_string(self, column):
        self.dialect.trace_process('DMDDLCompiler', 'get_column_default_string', column)
        return super(DMDDLCompiler, self).get_column_default_string(column)
        
    def visit_add_constraint(self, create):
        self.dialect.trace_process('DMDDLCompiler', 'visit_add_constraint', create)
        return super(DMDDLCompiler, self).visit_add_constraint(create)
        
    def visit_check_constraint(self, constraint):
        self.dialect.trace_process('DMDDLCompiler', 'visit_check_constraint', constraint)
        return super(DMDDLCompiler, self).visit_check_constraint(constraint)
        
    def visit_column_check_constraint(self, constraint):
        self.dialect.trace_process('DMDDLCompiler', 'visit_column_check_constraint', constraint)
        return super(DMDDLCompiler, self).visit_column_check_constraint(constraint)
        
    def visit_create_schema(self, create):
        self.dialect.trace_process('DMDDLCompiler', 'visit_create_schema', create)
        return super(DMDDLCompiler, self).visit_create_schema(create)
        
    def visit_create_sequence(self, create):
        self.dialect.trace_process('DMDDLCompiler', 'visit_create_sequence', create)
        return super(DMDDLCompiler, self).visit_create_sequence(create)
        
    def visit_create_table(self, create):
        self.dialect.trace_process('DMDDLCompiler', 'visit_create_table', create)
        return super(DMDDLCompiler, self).visit_create_table(create)
        
    def visit_ddl(self, ddl, **kwargs):
        self.dialect.trace_process('DMDDLCompiler', 'visit_ddl', ddl, **kwargs)
        return super(DMDDLCompiler, self).visit_ddl(ddl, **kwargs)
        
    def visit_drop_index(self, drop):
        self.dialect.trace_process('DMDDLCompiler', 'visit_drop_index', drop)
        return super(DMDDLCompiler, self).visit_drop_index(drop)
        
    def visit_drop_schema(self, drop):
        self.dialect.trace_process('DMDDLCompiler', 'visit_drop_schema', drop)
        return super(DMDDLCompiler, self).visit_drop_schema(drop)
        
    def visit_drop_sequence(self, drop):
        self.dialect.trace_process('DMDDLCompiler', 'visit_drop_sequence', drop)
        return super(DMDDLCompiler, self).visit_drop_sequence(drop)
        
    def visit_drop_table(self, drop):
        self.dialect.trace_process('DMDDLCompiler', 'visit_drop_table', drop)
        return super(DMDDLCompiler, self).visit_drop_table(drop)
        
    def visit_drop_view(self, drop):
        self.dialect.trace_process('DMDDLCompiler', 'visit_drop_view', drop)
        return super(DMDDLCompiler, self).visit_drop_view(drop)
        
    def visit_foreign_key_constraint(self, constraint):
        self.dialect.trace_process('DMDDLCompiler', 'visit_foreign_key_constraint', constraint)
        return super(DMDDLCompiler, self).visit_foreign_key_constraint(constraint)
        
    def visit_primary_key_constraint(self, constraint):
        self.dialect.trace_process('DMDDLCompiler', 'visit_primary_key_constraint', constraint)
        return super(DMDDLCompiler, self).visit_primary_key_constraint(constraint)
        
    def _prepared_index_name(self, index, include_schema=False):
        self.dialect.trace_process('DMDDLCompiler', '_prepared_index_name', index, include_schema)
        return super(DMDDLCompiler, self)._prepared_index_name(index, include_schema)
        
    def _verify_index_table(self, index):
        self.dialect.trace_process('DMDDLCompiler', '_verify_index_table', index)
        return super(DMDDLCompiler, self)._verify_index_table(index)
        

class DMIdentifierPreparer(compiler.IdentifierPreparer):

    reserved_words = set([x.lower() for x in RESERVED_WORDS])
    illegal_initial_characters = set(
        (str(dig) for dig in range(0, 10))).union(["_", "$"])

    def _bindparam_requires_quotes(self, value):
        self.dialect.trace_process('DMIdentifierPreparer', '_bindparam_requires_quotes', value)
        
        """Return True if the given identifier requires quoting."""
        lc_value = value.lower()
        return (lc_value in self.reserved_words
                or value[0] in self.illegal_initial_characters
                or not self.legal_characters.match(util.text_type(value))
                )

    def format_savepoint(self, savepoint):
        self.dialect.trace_process('DMIdentifierPreparer', '_bindparam_requires_quotes', savepoint)
        
        name = savepoint.ident.lstrip('_')
        return super(
            DMIdentifierPreparer, self).format_savepoint(savepoint, name)
    
    def _quote_free_identifiers(self, *ids):
        self.dialect.trace_process('DMIdentifierPreparer', '_bindparam_requires_quotes', *ids)
        
        """Unilaterally identifier-quote any number of strings."""
    
        return tuple([self.quote_identifier(i) for i in ids if i is not None])
    
    # for trace only
    def format_alias(self, alias, name=None):
        self.dialect.trace_process('DMIdentifierPreparer', 'format_alias', alias, name)
        return super(DMIdentifierPreparer, self).format_alias(alias, name)
        
    def format_label(self, label, name=None):
        self.dialect.trace_process('DMIdentifierPreparer', 'format_label', label, name)
        return super(DMIdentifierPreparer, self).format_label(label, name)
        
    def format_schema(self, name, quote=None):
        self.dialect.trace_process('DMIdentifierPreparer', 'format_schema', name, quote)
        return super(DMIdentifierPreparer, self).format_schema(name, quote)
        
    def format_sequence(self, sequence, use_schema=True):
        self.dialect.trace_process('DMIdentifierPreparer', 'format_sequence', sequence, use_schema)
        return super(DMIdentifierPreparer, self).format_sequence(sequence, use_schema)
        
    def format_table(self, table, use_schema=True, name=None):
        self.dialect.trace_process('DMIdentifierPreparer', 'format_table', table, use_schema, name)
        return super(DMIdentifierPreparer, self).format_table(table, use_schema, name)
        
    def format_table_seq(self, table, use_schema=True):
        self.dialect.trace_process('DMIdentifierPreparer', 'format_table_seq', table, use_schema)
        return super(DMIdentifierPreparer, self).format_table_seq(table, use_schema)
        

class DMExecutionContext(default.DefaultExecutionContext):
    def fire_sequence(self, seq, type_):
        self.dialect.trace_process('DMExecutionContext', 'fire_sequence', seq, type_)
        
        return self._execute_scalar(
            "SELECT " +
            self.dialect.identifier_preparer.format_sequence(seq) +
            ".nextval FROM DUAL", type_)
        
    # for trace only
    def get_insert_default(self, column):
        self.dialect.trace_process('DMExecutionContext', 'get_insert_default', column)
        return super(DMExecutionContext, self).get_insert_default(column)
        
    def get_lastrowid(self):
        self.dialect.trace_process('DMExecutionContext', 'get_lastrowid')
        return super(DMExecutionContext, self).get_lastrowid()
        
    def get_result_processor(self, type_, colname, coltype):
        self.dialect.trace_process('DMExecutionContext', 'get_result_processor', type_, colname, coltype)
        return super(DMExecutionContext, self).get_result_processor(type_, colname, coltype)
        
    def get_update_default(self, column):
        self.dialect.trace_process('DMExecutionContext', 'get_update_default', column)
        return super(DMExecutionContext, self).get_update_default(column)
        
    def lastrow_has_defaults(self):
        self.dialect.trace_process('DMExecutionContext', 'lastrow_has_defaults')
        return super(DMExecutionContext, self).lastrow_has_defaults()
        
    def set_input_sizes(self, translate=None, exclude_types=None):
        self.dialect.trace_process('DMExecutionContext', 'set_input_sizes', translate, exclude_types)
        super(DMExecutionContext, self).set_input_sizes(translate, exclude_types)
        
    def supports_sane_multi_rowcount(self):
        self.dialect.trace_process('DMExecutionContext', 'supports_sane_multi_rowcount')
        return super(DMExecutionContext, self).supports_sane_multi_rowcount()
        
    def supports_sane_rowcount(self):
        self.dialect.trace_process('DMExecutionContext', 'supports_sane_rowcount')
        return super(DMExecutionContext, self).supports_sane_rowcount()
        
    def _execute_scalar(self, stmt, type_):
        self.dialect.trace_process('DMExecutionContext', '_execute_scalar', stmt, type_)
        return super(DMExecutionContext, self)._execute_scalar(stmt, type_)
    
    def _process_executemany_defaults(self):
        self.dialect.trace_process('DMExecutionContext', '_process_executemany_defaults')
        super(DMExecutionContext, self)._process_executemany_defaults()
        
    def _process_executesingle_defaults(self):
        self.dialect.trace_process('DMExecutionContext', '_process_executesingle_defaults')
        super(DMExecutionContext, self)._process_executesingle_defaults()
        
    def _setup_crud_result_proxy(self):
        self.dialect.trace_process('DMExecutionContext', '_setup_crud_result_proxy')
        return super(DMExecutionContext, self)._setup_crud_result_proxy()
        
    def _setup_ins_pk_from_empty(self):
        self.dialect.trace_process('DMExecutionContext', '_setup_ins_pk_from_empty')
        super(DMExecutionContext, self)._setup_ins_pk_from_empty()
        
    def _setup_ins_pk_from_implicit_returning(self, row):
        self.dialect.trace_process('DMExecutionContext', '_setup_ins_pk_from_implicit_returning', row)
        super(DMExecutionContext, self)._setup_ins_pk_from_implicit_returning(row)

    def _self_process_name(self, name, reserved_words):
        result_name = name
        if result_name.lower() in reserved_words or '\"' in result_name or (result_name.upper() != result_name and result_name.lower() != result_name):
            if '\"' in result_name:
                result_name = result_name.replace('\"', '\"\"')
            result_name = '"%s"' % result_name
        return result_name

    def _set_autoinc_col_from_lastrowid(self, table, autoinc_col, lastrowid):
        self.dialect.trace_process('DMExecutionContext', '_set_autoinc_col_from_lastrowid')
        reserved_words = set([x.lower() for x in RESERVED_WORDS])
        table_name = self._self_process_name(table.name, reserved_words)
        autoinc_col_name = self._self_process_name(autoinc_col.name, reserved_words)
        statement = "select {} from {} where rowid = {}".format(autoinc_col_name, table_name, lastrowid)
        self.dialect.do_execute(self.cursor, statement, None, None)
        return self.cursor.fetchone()[0]

    def _setup_ins_pk_from_lastrowid(self):
        self.dialect.trace_process('DMExecutionContext', '_setup_ins_pk_from_lastrowid')
        key_getter = self.compiled._key_getters_for_crud_column[2]
        table = self.compiled.statement.table
        compiled_params = self.compiled_parameters[0]

        lastrowid = self.get_lastrowid()
        if lastrowid is not None:
            autoinc_col = table._autoincrement_column
            rowid_dict = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5, 'G': 6, 'H': 7, 'I': 8, 'J': 9,
                          'K': 10, 'L': 11,
                          'M': 12, 'N': 13, 'O': 14, 'P': 15, 'Q': 16, 'R': 17, 'S': 18, 'T': 19, 'U': 20,
                          'V': 21, 'W': 22,
                          'X': 23, 'Y': 24, 'Z': 25, 'a': 26, 'b': 27, 'c': 28, 'd': 29, 'e': 30, 'f': 31,
                          'g': 32, 'h': 33,
                          'i': 34, 'j': 35, 'k': 36, 'l': 37, 'm': 38, 'n': 39, 'o': 40, 'p': 41, 'q': 42,
                          'r': 43, 's': 44,
                          't': 45, 'u': 46, 'v': 47, 'w': 48, 'x': 49, 'y': 50, 'z': 51, '0': 52, '1': 53,
                          '2': 54, '3': 55,
                          '4': 56, '5': 57, '6': 58, '7': 59, '8': 60, '9': 61, '+': 62, '/': 63}
            rowid_temp = 0
            for i in lastrowid[-8:]:
                rowid_temp = rowid_temp * 64 + rowid_dict[i]
            lastrowid = rowid_temp

            self.inserted_primary_key = [
                    self._set_autoinc_col_from_lastrowid(table, autoinc_col, lastrowid) if c is autoinc_col else
                    compiled_params.get(key_getter(c), None)
                    for c in table.primary_key
                ]
        else:
            # don't have a usable lastrowid, so
            # do the same as _setup_ins_pk_from_empty
            self.inserted_primary_key = [
                    compiled_params.get(key_getter(c), None)
                    for c in table.primary_key
                ]

    def _use_server_side_cursor(self):
        self.dialect.trace_process('DMExecutionContext', '_use_server_side_cursor')
        return super(DMExecutionContext, self)._use_server_side_cursor()


class DMDialect(default.DefaultDialect):
    name = 'dm'
    supports_alter = True
    supports_unicode_statements = True
    supports_unicode_binds = True
    max_identifier_length = 128
    max_index_name_length = 128    
    supports_sane_rowcount = True
    supports_sane_multi_rowcount = False

    supports_simple_order_by_label = False

    supports_sequences = True
    sequences_optional = False
    postfetch_lastrowid = True

    default_paramstyle = 'named'
    colspecs = colspecs
    ischema_names = ischema_names
    requires_name_normalize = True

    supports_default_values = False
    supports_empty_insert = False
    
    supports_trace = False
    supports_trace_params = False
    outfile = None

    statement_compiler = DMCompiler
    ddl_compiler = DMDDLCompiler
    type_compiler = DMTypeCompiler
    preparer = DMIdentifierPreparer
    execution_ctx_cls = DMExecutionContext

    reflection_options = ('dm_resolve_synonyms', )

    construct_arguments = [
        (sa_schema.Table, {
            "resolve_synonyms": False,
            "on_commit": None,
            "compress": False
        }),
        (sa_schema.Index, {
            "bitmap": False,
            "compress": False
        })
    ]

    def __init__(self,
                 use_ansi=True,
                 optimize_limits=False,
                 use_binds_for_limits=True,
                 exclude_tablespaces=('SYSTEM', 'SYSAUX', ),
                 supports_trace=False,
                 supports_trace_params=False,                 
                 **kwargs):
        self.supports_trace = supports_trace
        self.supports_trace_params = supports_trace_params        
        default.DefaultDialect.__init__(self, **kwargs)
        self.use_ansi = use_ansi
        self.optimize_limits = optimize_limits
        self.use_binds_for_limits = use_binds_for_limits
        self.exclude_tablespaces = exclude_tablespaces
        
        if self.supports_trace:
            self.outfile = open('dmSQLAlchemy_trace.log', 'a')

    def initialize(self, connection):
        super(DMDialect, self).initialize(connection)
        self.implicit_returning = self.__dict__.get(
            'implicit_returning',
            self.server_version_info > (10, )
        )
        self.default_schema_name = self._get_default_schema_name(connection)
        
    def trace_process(self, cls_str=None, func_str=None, *args, **kws):
        if not self.supports_trace:
            return
        now = datetime.now().isoformat()
        self.outfile.write('{}\n'.format(now))
        self.outfile.write('clsname:{}\n'.format(cls_str))
        self.outfile.write('funcname:{}\n'.format(func_str))
        
        if self.supports_trace_params:
            self.outfile.write('args:{}\n'.format(args))
            self.outfile.write('kws:{}\n'.format(kws))
            
        self.outfile.write('\n')
    
    @property
    def _supports_table_compression(self):
        self.trace_process('DMDialect', '_supports_table_compression')
        
        return self.server_version_info and \
            self.server_version_info >= (10, 1, )

    @property
    def _supports_table_compress_for(self):
        self.trace_process('DMDialect', '_supports_table_compress_for')
        return self.server_version_info and \
            self.server_version_info >= (11, )

    @property
    def _supports_char_length(self):
        self.trace_process('DMDialect', '_supports_char_length')
        return True

    @property
    def _supports_nchar(self):
        self.trace_process('DMDialect', '_supports_nchar')
        return True
    
    @property
    def dialect_description(self):
        self.trace_process('DMDialect', 'dialect_description')
        return super(DMDialect, self).dialect_description()
        
    def do_close(self, dbapi_connection):
        self.trace_process('DMDialect', 'do_close', dbapi_connection)
        super(DMDialect, self).do_close(dbapi_connection)
        
    def do_commit(self, dbapi_connection):
        self.trace_process('DMDialect', 'do_commit', dbapi_connection)
        super(DMDialect, self).do_commit(dbapi_connection)
        
    def do_execute(self, cursor, statement, parameters, context=None):
        self.trace_process('DMDialect', 'do_execute', cursor, statement, parameters, context)
        super(DMDialect, self).do_execute(cursor, statement, parameters, context)
        
    def do_execute_no_params(self, cursor, statement, context=None):
        self.trace_process('DMDialect', 'do_execute_no_params', cursor, statement, context)
        super(DMDialect, self).do_execute_no_params(cursor, statement, context)

    def do_release_savepoint(self, connection, name):
        self.trace_process('DMDialect', 'do_release_savepoint', connection, name)
        pass

    def _run_batches(self, connection, all_objects, query, query_fllow, dblink, quote_flag = True):
        batches = list(all_objects)

        while len(batches)>0:
            batch = batches[0:500]
            batches[0:500] = []

            if dblink and not dblink.startswith("@"):
                dblink = f"@{dblink}"

            execution_options = {
                "_dm_dblink": dblink or "",
                "schema_translate_map": None,
            }

            temp_query = query

            if(len(batch) != 0):
                if quote_flag == True:
                    temp_query += '\''
                    temp_query += str(batch[0])
                    temp_query += '\''
                else:
                    temp_query += str(batch[0])

            for i in range(len(batch) - 1):
                if quote_flag == True:
                    temp_query += ', '
                    temp_query += '\''
                    temp_query += str(batch[i + 1])
                    temp_query += '\''
                else:
                    temp_query += ', '
                    temp_query += str(batch[i + 1])

            temp_query += query_fllow
            result = connection.execute(sql.text(temp_query), execution_options=execution_options)
            yield from result.mappings()

    def get_identity_info(self, connection, owner, all_objects, dblink):

        query = "select name as col_name, id as tab_id from syscolumns where id IN (select id from sysobjects where name IN ("
        query_fllow = ") and SUBTYPE$ = 'UTAB' and schid = (select id from sysobjects where name = '"
        query_fllow += str(owner)
        query_fllow += "' and TYPE$ = 'SCH') and info3 & 0x3F not in(0x05 ,0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27)) and info2 = 1;"

        result = self._run_batches(
            connection,
            all_objects,
            query,
            query_fllow,
            dblink
        )

        result_list = []
        table_id_list = []
        tab_col_list = {}
        for row_dict in result:
            table_id_list.append(str(row_dict['tab_id']))
            tab_col_list[str(row_dict['tab_id'])] = row_dict['col_name']
        if len(table_id_list) == 0:
            return result_list
        query = "SELECT id, name, info6 FROM SYSOBJECTS WHERE ID IN ( "
        query_fllow = ");"
        info6 = self._run_batches(
            connection,
            table_id_list,
            query,
            query_fllow,
            dblink,
            False
        )

        for row_dict in info6:
            byte_info = row_dict['info6']
            temp_dict = {}
            temp_dict['col_name'] = tab_col_list[str(row_dict['id'])]
            temp_dict['tab_name'] = row_dict['name']
            temp_dict['start'] = int.from_bytes(byte_info[:8], byteorder = 'little', signed = False)
            temp_dict['increment'] = int.from_bytes(byte_info[8:16], byteorder = 'little', signed = False)
            result_list.append(temp_dict)

        return result_list

    def has_table(self, connection, table_name, schema=None):
        self.trace_process('DMDialect', 'has_table', connection, table_name, schema)
        
        if not schema:
            schema = self.default_schema_name
        cursor = connection.execute(
            sql.text("""SELECT tables_and_views.table_name 
                    FROM (SELECT a_tables.table_name AS table_name, a_tables.owner AS owner 
                    FROM all_tables a_tables UNION ALL SELECT a_views.view_name AS table_name, a_views.owner AS owner 
                    FROM all_views a_views) tables_and_views 
                    WHERE tables_and_views.table_name = :name AND tables_and_views.owner = :schema_name"""),
            name=self.denormalize_name(table_name),
            schema_name=self.denormalize_name(schema))
        return cursor.first() is not None

    def has_sequence(self, connection, sequence_name, schema=None):
        self.trace_process('DMDialect', 'has_sequence', connection, sequence_name, schema)
        
        if not schema:
            schema = self.default_schema_name
        cursor = connection.execute(
            sql.text("""SELECT a_sequences.sequence_name 
                        FROM all_sequences a_sequences
                        WHERE a_sequences.sequence_name = :name AND a_sequences.sequence_owner = :schema_name"""),
            name=self.denormalize_name(sequence_name),
            schema_name=self.denormalize_name(schema))
        return cursor.first() is not None

    def normalize_name(self, name):
        self.trace_process('DMDialect', 'normalize_name', name)
        """convert the given name to lowercase if it is detected as
        case insensitive.

        this method is only used if the dialect defines
        requires_name_normalize=True.

        """ 
        if name is None:
            return None
        if util.py2k:
            if isinstance(name, str):
                name = name.decode(self.encoding)
        if name.upper() == name and not \
                self.identifier_preparer._requires_quotes(name.lower()):
            return name.lower()
        elif name.lower() == name:
            return quoted_name(name, quote=True)
        else:
            return name

    def denormalize_name(self, name):
        self.trace_process('DMDialect', 'denormalize_name', name)
        """convert the given name to a case insensitive identifier
        for the backend if it is an all-lowercase name.

        this method is only used if the dialect defines
        requires_name_normalize=True.

        """        
        if name is None:
            return None
        elif name.lower() == name and not \
                self.identifier_preparer._requires_quotes(name.lower()):
            name = name.upper()
        if util.py2k:
            if not self.supports_unicode_binds:
                name = name.encode(self.encoding)
            else:
                name = unicode(name)
        return name

    def _get_default_schema_name(self, connection):
        self.trace_process('DMDialect', '_get_default_schema_name', connection)
        return self.normalize_name(
            connection.execute('SELECT USER FROM DUAL').scalar())

    def _resolve_synonym(self, connection, desired_owner=None,
                         desired_synonym=None, desired_table=None):
        self.trace_process('DMDialect', '_resolve_synonym', 
                           connection, desired_owner, desired_synonym, desired_table)
        """search for a local synonym matching the given desired owner/name.

        if desired_owner is None, attempts to locate a distinct owner.

        returns the actual name, owner, dblink name, and synonym name if
        found.
        """

        q = "SELECT owner, table_owner, table_name, db_link, "\
            "synonym_name FROM all_synonyms WHERE "
        clauses = []
        params = {}
        if desired_synonym:
            clauses.append("synonym_name = :synonym_name")
            params['synonym_name'] = desired_synonym
        if desired_owner:
            clauses.append("owner = :desired_owner")
            params['desired_owner'] = desired_owner
        if desired_table:
            clauses.append("table_name = :tname")
            params['tname'] = desired_table

        q += " AND ".join(clauses)

        result = connection.execute(sql.text(q), **params)
        if desired_owner:
            row = result.first()
            if row:
                return (row['table_name'], row['table_owner'],
                        row['db_link'], row['synonym_name'])
            else:
                return None, None, None, None
        else:
            rows = result.fetchall()
            if len(rows) > 1:
                raise AssertionError(
                    "There are multiple tables visible to the schema, you "
                    "must specify owner")
            elif len(rows) == 1:
                row = rows[0]
                return (row['table_name'], row['table_owner'],
                        row['db_link'], row['synonym_name'])
            else:
                return None, None, None, None

    @reflection.cache
    def _prepare_reflection_args(self, connection, table_name, schema=None,
                                 resolve_synonyms=False, dblink='', **kw):
        self.trace_process('DMDialect', '_prepare_reflection_args',
                           connection, table_name, schema,
                           resolve_synonyms, dblink, **kw)

        if resolve_synonyms:
            actual_name, owner, dblink, synonym = self._resolve_synonym(
                connection,
                desired_owner=self.denormalize_name(schema),
                desired_synonym=self.denormalize_name(table_name)
            )
        else:
            actual_name, owner, dblink, synonym = None, None, None, None
        if not actual_name:
            actual_name = self.denormalize_name(table_name)

        if dblink:
            owner = connection.scalar(
                sql.text("SELECT username FROM user_db_links "
                         "WHERE db_link=:link"), link=dblink)
            dblink = "@" + dblink
        elif not owner:
            owner = self.denormalize_name(schema or self.default_schema_name)

        return (actual_name, owner, dblink or '', synonym)

    @reflection.cache
    def get_schema_names(self, connection, **kw):
        self.trace_process('DMDialect', 'get_schema_names', connection, **kw)
        
        s = "SELECT SF_GET_SCHEMA_NAME_BY_ID(CURRENT_SCHID());"
        cursor = connection.execute(s,)
        return [self.normalize_name(row[0]) for row in cursor]

    @reflection.cache
    def get_table_names(self, connection, schema=None, **kw):
        self.trace_process('DMDialect', 'get_table_names', connection, schema, **kw)
        
        schema = self.denormalize_name(schema or self.default_schema_name)

        # note that table_names() isn't loading DBLINKed or synonym'ed tables
        if schema is None:
            schema = self.default_schema_name

        sql_str = "SELECT table_name FROM all_tables WHERE "
        if self.exclude_tablespaces:
            sql_str += (
                "nvl(tablespace_name, 'no tablespace') "
                "NOT IN (%s) AND " % (
                    ', '.join(["'%s'" % ts for ts in self.exclude_tablespaces])
                )
            )
        sql_str += (
            "OWNER = :owner "
            "AND DURATION IS NULL")

        cursor = connection.execute(sql.text(sql_str), owner=schema)
        return [self.normalize_name(row[0]) for row in cursor]

    @reflection.cache
    def get_temp_table_names(self, connection, **kw):
        self.trace_process('DMDialect', 'get_temp_table_names', connection, **kw)
        
        schema = self.denormalize_name(self.default_schema_name)

        sql_str = "SELECT table_name FROM all_tables WHERE "
        if self.exclude_tablespaces:
            sql_str += (
                "nvl(tablespace_name, 'no tablespace') "
                "NOT IN (%s) AND " % (
                    ', '.join(["'%s'" % ts for ts in self.exclude_tablespaces])
                )
            )
        sql_str += (
            "OWNER = :owner "
            "AND IOT_NAME IS NULL "
            "AND DURATION IS NOT NULL")

        cursor = connection.execute(sql.text(sql_str), owner=schema)
        return [self.normalize_name(row[0]) for row in cursor]

    @reflection.cache
    def get_view_names(self, connection, schema=None, **kw):
        self.trace_process('DMDialect', 'get_view_names', connection, schema, **kw)
        
        schema = self.denormalize_name(schema or self.default_schema_name)
        s = sql.text("SELECT view_name FROM all_views WHERE owner = :owner")
        cursor = connection.execute(s, owner=self.denormalize_name(schema))
        return [self.normalize_name(row[0]) for row in cursor]

    @reflection.cache
    def get_table_options(self, connection, table_name, schema=None, **kw):
        self.trace_process('DMDialect', 'get_table_options', connection, table_name, schema, **kw)
        
        options = {}

        resolve_synonyms = kw.get('dm_resolve_synonyms', False)
        dblink = kw.get('dblink', '')
        info_cache = kw.get('info_cache')

        (table_name, schema, dblink, synonym) = \
            self._prepare_reflection_args(connection, table_name, schema,
                                          resolve_synonyms, dblink,
                                          info_cache=info_cache)

        params = {"table_name": table_name}

        columns = ["table_name"]
        if self._supports_table_compression:
            columns.append("compression")
        if self._supports_table_compress_for:
            columns.append("compress_for")

        text = "SELECT %(columns)s "\
            "FROM ALL_TABLES%(dblink)s "\
            "WHERE table_name = :table_name"

        if schema is not None:
            params['owner'] = schema
            text += " AND owner = :owner "
        text = text % {'dblink': dblink, 'columns': ", ".join(columns)}

        result = connection.execute(sql.text(text), **params)

        enabled = dict(DISABLED=False, ENABLED=True)

        row = result.first()
        if row:
            if "compression" in row and enabled.get(row.compression, False):
                if "compress_for" in row:
                    options['dm_compress'] = row.compress_for
                else:
                    options['dm_compress'] = True

        return options

    @reflection.cache
    def get_columns(self, connection, table_name, schema=None, **kw):
        self.trace_process('DMDialect', 'get_columns', connection, table_name, schema, **kw)

        resolve_synonyms = kw.get('dm_resolve_synonyms', False)
        dblink = kw.get('dblink', '')
        info_cache = kw.get('info_cache')

        (table_name, schema, dblink, synonym) = \
            self._prepare_reflection_args(connection, table_name, schema,
                                          resolve_synonyms, dblink,
                                          info_cache=info_cache)
        columns = []
        if self._supports_char_length:
            char_length_col = 'char_length'
        else:
            char_length_col = 'data_length'

        text = "SELECT a_tab_cols.column_name, a_tab_cols.data_type, a_tab_cols.%(char_length_col)s, "\
            "a_tab_cols.data_precision, a_tab_cols.data_scale, a_tab_cols.nullable, a_tab_cols.data_default, "\
            "a_col_comments.comments, a_tab_cols.virtual_column FROM ALL_TAB_COLS%(dblink)s a_tab_cols, ALL_COL_COMMENTS a_col_comments "\
            "WHERE a_tab_cols.table_name = "+"'"+table_name+"' "
        if schema is not None:
            text += " AND a_tab_cols.owner = "+"'"+schema+"' "
        text += ("AND a_tab_cols.table_name = a_col_comments.table_name AND a_tab_cols.column_name = a_col_comments.column_name "
                 "AND a_tab_cols.owner = a_col_comments.schema_name AND a_tab_cols.hidden_column = \'NO\' "
                 "ORDER BY column_id")
        text = text % {'dblink': dblink, 'char_length_col': char_length_col}
        c = connection.execute(sql.text(text))

        identity = self.get_identity_info(connection, schema, [table_name], dblink)

        for row in c:
            (colname, orig_colname, coltype, length, precision, scale, nullable, default, comments, virtual_column) = \
                (self.normalize_name(row[0]), row[0], row[1], row[2], row[3], row[4], row[5] == 'Y', row[6], row[7], row[8])

            if coltype in ('DEC', 'NUMERIC', 'DECIMAL', 'NUMBER'):
                if precision == None:
                    coltype = INTEGER
                else:
                    coltype = NUMBER(precision, scale)
            elif coltype in ('VARCHAR', 'VARCHAR2', 'NVARCHAR2', 'CHAR', 'CHARACTER'):
                coltype = self.ischema_names.get(coltype)(length)
            elif 'WITH TIME ZONE' in coltype:
                coltype = TIMESTAMP(timezone = True)
            else:
                coltype = re.sub(r'\(\d+\)', '', coltype)
                try:
                    coltype = self.ischema_names[coltype]
                except KeyError:
                    util.warn("Did not recognize type '%s' of column '%s'" %
                              (coltype, colname))
                    coltype = sqltypes.NULLTYPE

            if virtual_column == "YES":
                computed = dict(sqltext=default)
                default = None
            else:
                computed = None

            cdict = {
                'name': colname,
                'type': coltype,
                'nullable': nullable,
                'default': default,
                'autoincrement': None,
                "comment": comments,
            }
            if orig_colname.lower() == orig_colname:
                cdict['quote'] = True
            if computed is not None:
                cdict["computed"] = computed

            if len(identity) > 0:
                for identity_dict in identity:
                    if self.normalize_name(identity_dict['col_name']) == colname and self.normalize_name(identity_dict['tab_name']) == self.normalize_name(table_name):
                        del identity_dict['col_name']
                        del identity_dict['tab_name']
                        cdict["identity"] = identity_dict
                        cdict["autoincrement"] = True
                        identity.remove(identity_dict)

            columns.append(cdict)
        return columns

    @reflection.cache
    def get_indexes(self, connection, table_name, schema=None,
                    resolve_synonyms=False, dblink='', **kw):
        self.trace_process('DMDialect', 'get_indexes', 
                           connection, table_name, schema,
                           resolve_synonyms, dblink, **kw)

        info_cache = kw.get('info_cache')
        (table_name, schema, dblink, synonym) = \
            self._prepare_reflection_args(connection, table_name, schema,
                                          resolve_synonyms, dblink,
                                          info_cache=info_cache)
        indexes = []

        params = {'table_name': table_name}
        text = \
            "SELECT a.index_name, a.column_name, "\
            "\nb.index_type, b.uniqueness, b.compression, b.prefix_length "\
            "\nFROM ALL_IND_COLUMNS%(dblink)s a, "\
            "\nALL_INDEXES%(dblink)s b "\
            "\nWHERE "\
            "\na.index_name = b.index_name "\
            "\nAND a.table_owner = b.table_owner "\
            "\nAND a.table_name = b.table_name "\
            "\nAND a.table_name = :table_name "

        if schema is not None:
            params['schema'] = schema
            text += "AND a.table_owner = :schema "

        text += "ORDER BY a.index_name, a.column_position"

        text = text % {'dblink': dblink}

        q = sql.text(text)
        rp = connection.execute(q, **params)
        indexes = []
        last_index_name = None
        pk_constraint = self.get_pk_constraint(
            connection, table_name, schema, resolve_synonyms=resolve_synonyms,
            dblink=dblink, info_cache=kw.get('info_cache'))
        pkeys = pk_constraint['constrained_columns']
        uniqueness = dict(NONUNIQUE=False, UNIQUE=True)
        enabled = dict(DISABLED=False, ENABLED=True)

        dm_sys_col = re.compile(r'SYS_NC\d+\$', re.IGNORECASE)

        def upper_name_set(names):
            return set([i.upper() for i in names])

        pk_names = upper_name_set(pkeys)

        def remove_if_primary_key(index):
            
            # don't include the primary key index
            if index is not None and \
               upper_name_set(index['column_names']) == pk_names:
                indexes.pop()

        index = None
        for rset in rp:
            if rset.index_name != last_index_name:
                remove_if_primary_key(index)
                index = dict(name=self.normalize_name(rset.index_name),
                             column_names=[], dialect_options={})
                indexes.append(index)
            index['unique'] = uniqueness.get(rset.uniqueness, False)

            if rset.index_type in ('BITMAP', 'FUNCTION-BASED BITMAP'):
                index['dialect_options']['dm_bitmap'] = True
            if enabled.get(rset.compression, False):
                index['dialect_options']['dm_compress'] = rset.prefix_length

            if not dm_sys_col.match(rset.column_name):
                index['column_names'].append(
                    self.normalize_name(rset.column_name))
            last_index_name = rset.index_name
        remove_if_primary_key(index)
        return indexes

    @reflection.cache
    def _get_constraint_data(self, connection, table_name, schema=None,
                             dblink='', **kw):
        self.trace_process('DMDialect', '_get_constraint_data', connection, table_name, schema, dblink, **kw)

        params = {'table_name': table_name}

        text = \
            "SELECT"\
            "\nac.constraint_name,"\
            "\nac.constraint_type,"\
            "\nloc.column_name AS local_column,"\
            "\nrem.table_name AS remote_table,"\
            "\nrem.column_name AS remote_column,"\
            "\nrem.owner AS remote_owner,"\
            "\nloc.position as loc_pos,"\
            "\nrem.position as rem_pos"\
            "\nFROM all_constraints%(dblink)s ac,"\
            "\nall_cons_columns%(dblink)s loc,"\
            "\nall_cons_columns%(dblink)s rem"\
            "\nWHERE ac.table_name = :table_name"\
            "\nAND ac.constraint_type IN ('R','P','U')"

        if schema is not None:
            params['owner'] = schema
            text += "\nAND ac.owner = :owner"

        text += \
            "\nAND ac.owner = loc.owner"\
            "\nAND ac.constraint_name = loc.constraint_name"\
            "\nAND ac.r_owner = rem.owner(+)"\
            "\nAND ac.r_constraint_name = rem.constraint_name(+)"\
            "\nAND (rem.position IS NULL or loc.position=rem.position)"\
            "\nORDER BY ac.constraint_name, loc.position"

        text = text % {'dblink': dblink}
        rp = connection.execute(sql.text(text), **params)
        constraint_data = rp.fetchall()
        return constraint_data

    @reflection.cache
    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        self.trace_process('DMDialect', 'get_pk_constraint', connection, table_name, schema, **kw)
        
        resolve_synonyms = kw.get('dm_resolve_synonyms', False)
        dblink = kw.get('dblink', '')
        info_cache = kw.get('info_cache')

        (table_name, schema, dblink, synonym) = \
            self._prepare_reflection_args(connection, table_name, schema,
                                          resolve_synonyms, dblink,
                                          info_cache=info_cache)
        pkeys = []
        constraint_name = None
        constraint_data = self._get_constraint_data(
            connection, table_name, schema, dblink,
            info_cache=kw.get('info_cache'))

        for row in constraint_data:
            (cons_name, cons_type, local_column, remote_table, remote_column, remote_owner) = \
                row[0:2] + tuple([self.normalize_name(x) for x in row[2:6]])
            if cons_type == 'P':
                if constraint_name is None:
                    constraint_name = self.normalize_name(cons_name)
                pkeys.append(local_column)
        return {'constrained_columns': pkeys, 'name': constraint_name}

    @reflection.cache
    def get_foreign_keys(self, connection, table_name, schema=None, **kw):
        self.trace_process('DMDialect', 'get_foreign_keys', connection, table_name, schema, **kw)
        
        requested_schema = schema  # to check later on
        resolve_synonyms = kw.get('dm_resolve_synonyms', False)
        dblink = kw.get('dblink', '')
        info_cache = kw.get('info_cache')

        (table_name, schema, dblink, synonym) = \
            self._prepare_reflection_args(connection, table_name, schema,
                                          resolve_synonyms, dblink,
                                          info_cache=info_cache)

        constraint_data = self._get_constraint_data(
            connection, table_name, schema, dblink,
            info_cache=kw.get('info_cache'))

        def fkey_rec():
            return {
                'name': None,
                'constrained_columns': [],
                'referred_schema': None,
                'referred_table': None,
                'referred_columns': []
            }

        fkeys = util.defaultdict(fkey_rec)

        for row in constraint_data:
            (cons_name, cons_type, local_column, remote_table, remote_column, remote_owner) = \
                row[0:2] + tuple([self.normalize_name(x) for x in row[2:6]])

            if cons_type == 'R':
                if remote_table is None:
                    # ticket 363
                    util.warn(
                        ("Got 'None' querying 'table_name' from "
                         "all_cons_columns%(dblink)s - does the user have "
                         "proper rights to the table?") % {'dblink': dblink})
                    continue

                rec = fkeys[cons_name]
                rec['name'] = cons_name
                local_cols, remote_cols = rec[
                    'constrained_columns'], rec['referred_columns']

                if not rec['referred_table']:
                    if resolve_synonyms:
                        ref_remote_name, ref_remote_owner, ref_dblink, ref_synonym = \
                            self._resolve_synonym(
                                connection,
                                desired_owner=self.denormalize_name(
                                    remote_owner),
                                desired_table=self.denormalize_name(
                                    remote_table)
                            )
                        if ref_synonym:
                            remote_table = self.normalize_name(ref_synonym)
                            remote_owner = self.normalize_name(
                                ref_remote_owner)

                    rec['referred_table'] = remote_table

                    if requested_schema is not None or \
                       self.denormalize_name(remote_owner) != schema:
                        rec['referred_schema'] = remote_owner

                local_cols.append(local_column)
                remote_cols.append(remote_column)

        return list(fkeys.values())

    @reflection.cache
    def get_unique_constraints(self, connection, table_name, schema=None, **kw):
        self.trace_process('DMDialect', 'get_unique_constraints',
                           connection, table_name, schema, **kw)
        
        resolve_synonyms = kw.get('dm_resolve_synonyms', False)
        dblink = kw.get('dblink', '')
        info_cache = kw.get('info_cache')

        (table_name, schema, dblink, synonym) = \
            self._prepare_reflection_args(connection, table_name, schema,
                                          resolve_synonyms, dblink,
                                          info_cache=info_cache)
        ucons = []
        constraint_name = None
        constraint_data = self._get_constraint_data(
            connection, table_name, schema, dblink,
            info_cache=kw.get('info_cache'))

        for row in constraint_data:
            (cons_name, cons_type, local_column, remote_table, remote_column, remote_owner) = \
                row[0:2] + tuple([self.normalize_name(x) for x in row[2:6]])
            if cons_type == 'U':
                
                constraint_name = self.normalize_name(cons_name)
                
                exist = False
                for rcon in ucons:
                    if rcon['name'] == constraint_name:
                        rcon['column_names'].append(local_column)
                        exist = True
                        
                if not exist:
                    new_con = {}
                    ukeys = []
                    new_con['name'] = constraint_name
                    ukeys.append(local_column)
                    new_con['column_names'] = ukeys
                    ucons.append(new_con)

        return ucons
    
    @reflection.cache
    def get_view_definition(self, connection, view_name, schema=None,
                            resolve_synonyms=False, dblink='', **kw):
        self.trace_process('DMDialect', 'get_view_definition',
                           connection, view_name, schema,
                           resolve_synonyms, dblink, **kw)
        
        info_cache = kw.get('info_cache')
        (view_name, schema, dblink, synonym) = \
            self._prepare_reflection_args(connection, view_name, schema,
                                          resolve_synonyms, dblink,
                                          info_cache=info_cache)

        params = {'view_name': view_name}
        text = "SELECT text FROM all_views WHERE view_name=:view_name"

        if schema is not None:
            text += " AND owner = :schema"
            params['schema'] = schema

        rp = connection.execute(sql.text(text), **params).scalar()
        if rp:
            if util.py2k:
                rp = rp.decode(self.encoding)
            return rp
        else:
            return None
        
    # for trace only
    def reflecttable(self, connection, table, include_columns, exclude_columns,resolve_fks, **opts):
        self.trace_process('DMDialect', 'reflecttable', connection, table, include_columns, exclude_columns,resolve_fks, **opts)
        return super(DMDialect, self).reflecttable(connection, table, include_columns, exclude_columns,resolve_fks, **opts)
        
    def reset_isolation_level(self, dbapi_conn):
        self.trace_process('DMDialect', 'reflecttable', dbapi_conn)
        super(DMDialect, self).reset_isolation_level(dbapi_conn)
        
    def set_connection_execution_options(self, connection, opts):
        self.trace_process('DMDialect', 'set_connection_execution_options', connection, opts)
        super(DMDialect, self).set_connection_execution_options(connection, opts)
        
    def set_engine_execution_options(self, engine, opts):
        self.trace_process('DMDialect', 'set_engine_execution_options', engine, opts)
        super(DMDialect, self).set_engine_execution_options(engine, opts)
        
    def type_descriptor(self, typeobj):
        self.trace_process('DMDialect', 'type_descriptor', typeobj)
        return super(DMDialect, self).type_descriptor(typeobj)
        
    def validate_identifier(self, ident):
        self.trace_process('DMDialect', 'validate_identifier', ident)
        super(DMDialect, self).validate_identifier(ident)


class _OuterJoinColumn(sql.ClauseElement):
    __visit_name__ = 'outer_join_column'

    def __init__(self, column):
        self.column = column
