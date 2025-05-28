from collections import namedtuple
import re
import dmPython

from django.db import models
from django.db.backends.base.introspection import (
    BaseDatabaseIntrospection, FieldInfo as BaseFieldInfo, TableInfo,
)
from django.utils.functional import cached_property

FieldInfo = namedtuple('FieldInfo', BaseFieldInfo._fields + ('is_autofield', 'is_json'))
InfoLine = namedtuple('InfoLine', 'col_name data_type max_len num_prec num_scale extra column_default')

foreign_key_re = re.compile(r"\sCONSTRAINT `[^`]*` FOREIGN KEY \(`([^`]*)`\) REFERENCES `([^`]*)` \(`([^`]*)`\)")

class DatabaseIntrospection(BaseDatabaseIntrospection):
    data_types_reverse = {
        dmPython.DATE: 'DateField',
        dmPython.TIME: 'TimeField',
        dmPython.TIMESTAMP: 'DateTimeField',
        dmPython.NUMBER: 'DecimalField',
        dmPython.BIGINT: 'BigIntegerField',
        dmPython.ROWID: 'BigIntegerField',
        dmPython.DOUBLE: 'FloatField',
        dmPython.REAL:  'FloatField',
        dmPython.DECIMAL: 'DecimalField',
        dmPython.STRING: 'CharField',
        dmPython.FIXED_STRING: 'CharField',
        dmPython.BOOLEAN: 'BooleanField',
        dmPython.BLOB: 'BinaryField',
        dmPython.CLOB: 'TextField',
        dmPython.INTERVAL: 'DurationField',                            
    }
    
    cache_bust_counter = 1
    
    def identifier_converter(self, name):
        return name.lower()
    
    def get_field_type(self, data_type, description):
        """
        description:
        name type_code display_size internal_size precision scale null_ok default is_autofield is_json
        0    1         2            3             4         5     6       7       8            9
        """
        if data_type == dmPython.NUMBER:
            precision, scale, null_ok, default, is_auto = description[4:9]
            if scale == 0:
                if precision > 11:
                    return 'BigAutoField' if is_auto else 'BigIntegerField'
                elif 4 < precision < 6:
                    return 'SmallIntegerField'
                elif 1 < precision < 4:
                    return 'BooleanField'
                elif is_auto:
                    return 'AutoField'
                else:
                    return 'IntegerField'
                
        if data_type == dmPython.BIGINT:
            precision, scale, null_ok, default, is_auto = description[4:9]
            return 'BigAutoField' if is_auto else 'BigIntegerField'
                
        if data_type == dmPython.CLOB and description.is_json:
            return 'JSONField'

        return super().get_field_type(data_type, description)    

    def get_table_list(self, cursor):
        "Returns a list of table names in the current database."
        cursor.execute("""SELECT all_tables.table_name,
                't'            
                FROM all_tables
            WHERE
                all_tables.owner = '%s'
                AND NOT EXISTS (
                    SELECT 1
                    FROM user_mviews
                    WHERE user_mviews.mview_name = all_tables.table_name
                )
            UNION ALL
            SELECT view_name, 'v' FROM user_views
            UNION ALL
            SELECT mview_name, 'v' FROM user_mviews""" % (cursor.cursor.cursor.connection.current_schema.replace('\'', '\'\'')))
            
        return [TableInfo(self.identifier_converter(row[0]), row[1])
                for row in cursor.fetchall()]

    def get_table_description(self, cursor, table_name):
        """
        Returns a description of the table, with the DB-API cursor.description interface."
        """
        # user_tab_columns gives data default for columns
        cursor.execute("""
            with TMP_VIEW as(
            select 
                col.table_name as tab_name, 
                col.column_name as colname
            from user_tab_cols col 
            where col.table_name = UPPER(?) 
            )
            SELECT
                column_name,
                data_default,
                CASE
                    WHEN char_used IS NULL THEN data_length
                    ELSE char_length
                END as internal_size,
                CASE
                    WHEN EXISTS (
                        SELECT  1
                        FROM user_json_columns
                        WHERE
                            user_json_columns.table_name = user_tab_cols.table_name AND
                            user_json_columns.column_name = user_tab_cols.column_name
                    )
                    THEN 1
                    ELSE 0
                END as is_json
            FROM user_tab_cols,TMP_VIEW
            WHERE table_name = TMP_VIEW.tab_name and column_name = TMP_VIEW.colname;
            """, [table_name.replace('\'', '\'\'')])
        field_map = {
            column: (internal_size, default if default != 'NULL' else None, is_json)
            for column, default, internal_size, is_json in cursor.fetchall()
        }
        self.cache_bust_counter += 1
        cursor.execute("SELECT * FROM {} WHERE ROWNUM < 2 AND {} > 0".format(
            self.connection.ops.quote_name(table_name.replace('\'', '\'\'')),
            self.cache_bust_counter))
        description = []
        length = len(FieldInfo._fields)
        for desc in cursor.description:
            name = desc[0]
            internal_size, default, is_json = field_map[name]
            if length == 10:
                description.append(FieldInfo(
                    self.identifier_converter(name), desc[1], desc[2], desc[3], desc[4] or 0,
                    desc[5] or 0, desc[6], default, None, is_json
                ))
            else:
                description.append(FieldInfo(
                    self.identifier_converter(name), desc[1], desc[2], desc[3], desc[4] or 0,
                    desc[5] or 0, desc[6], default, None, None, is_json
                ))
        return description

    def _name_to_index(self, cursor, table_name):
        """
        Returns a dictionary of {field_name: field_index} for the given table.
        Indexes are 0-based.
        """
        return dict([(d[0], i) for i, d in enumerate(self.get_table_description(cursor, table_name))])

    def get_relations(self, cursor, table_name):
        """
        Returns a dictionary of {field_name: (field_name_other_table, other_table)}
        representing all relationships to the given table.
        """
        table_name = table_name.upper()
        constraints = self.get_key_columns(cursor, table_name)
        relations = {}
        for my_fieldname, other_table, other_field in constraints:
            relations[self.identifier_converter(my_fieldname)] = (self.identifier_converter(other_field), self.identifier_converter(other_table))
        return relations

    def get_key_columns(self, cursor, table_name):
        """
        Returns a list of (column_name, referenced_table_name, referenced_column_name) for all
        key columns in given table.
        """
        
        sql = """
        SELECT ca.column_name, cb.table_name, cb.column_name
        FROM   user_constraints, USER_CONS_COLUMNS ca, USER_CONS_COLUMNS cb
        WHERE  user_constraints.table_name = '%s' AND
           user_constraints.constraint_name = ca.constraint_name AND
           user_constraints.r_constraint_name = cb.constraint_name AND
           ca.position = cb.position
        """ % (table_name.upper().replace('\'', '\'\''))
         
        cursor.execute(sql)
        
        key_columns =  [
            tuple(self.identifier_converter(cell) for cell in row)
            for row in cursor.fetchall()
        ]
        
        return key_columns

    def get_constraints(self, cursor, table_name):
        """
        Retrieve any constraints or keys (unique, pk, fk, check, index)
        across one or more columns.

        Return a dict mapping constraint names to their attributes,
        where attributes is a dict with keys:
         * columns: List of columns this covers
         * primary_key: True if primary key, False otherwise
         * unique: True if this is a unique constraint, False otherwise
         * foreign_key: (table, column) of target, or None
         * check: True if check constraint, False otherwise
         * index: True if index, False otherwise.
         * orders: The order (ASC/DESC) defined for the columns of indexes
         * type: The type of the index (btree, hash, etc.)

        Some backends may return special constraint names that don't exist
        if they don't name constraints of a certain type (e.g. SQLite)
        """
        constraints = {}
        # Loop over the constraints, getting PKs, uniques, and checks
        cursor.execute("""
            SELECT
                user_constraints.constraint_name,
                LISTAGG(LOWER(cols.column_name), ',') WITHIN GROUP (ORDER BY cols.position),
                CASE user_constraints.constraint_type
                    WHEN 'P' THEN 1
                    ELSE 0
                END AS is_primary_key,
                CASE
                    WHEN user_constraints.constraint_type IN ('P', 'U') THEN 1
                    ELSE 0
                END AS is_unique,
                CASE user_constraints.constraint_type
                    WHEN 'C' THEN 1
                    ELSE 0
                END AS is_check_constraint
            FROM
                user_constraints
            LEFT OUTER JOIN
                user_cons_columns cols ON user_constraints.constraint_name = cols.constraint_name
            WHERE
                user_constraints.constraint_type = ANY('P', 'U', 'C')
                AND user_constraints.table_name = '%s'
            GROUP BY user_constraints.constraint_name, user_constraints.constraint_type
        """ % table_name.upper().replace('\'', '\'\''))
        rows = cursor.fetchall()
        for constraint, columns, pk, unique, check in rows:
            constraint = self.identifier_converter(constraint)
            constraints[constraint] = {
                'columns': columns.split(','),
                'primary_key': bool(pk),
                'unique': bool(unique),
                'foreign_key': None,
                'check': bool(check),
                'index': bool(unique),  # All uniques come with an index
            }
        # Foreign key constraints
        cursor.execute("""
            SELECT
                cons.constraint_name,
                LISTAGG(LOWER(cols.column_name), ',') WITHIN GROUP (ORDER BY cols.position),
                LOWER(rcols.table_name),
                LOWER(rcols.column_name)
            FROM
                user_constraints cons
            INNER JOIN
                user_cons_columns rcols ON rcols.constraint_name = cons.r_constraint_name AND rcols.position = 1
            LEFT OUTER JOIN
                user_cons_columns cols ON cons.constraint_name = cols.constraint_name
            WHERE
                cons.constraint_type = 'R' AND
                cons.table_name = '%s'
            GROUP BY cons.constraint_name, rcols.table_name, rcols.column_name
        """ % table_name.upper().replace('\'', '\'\''))
        rows = cursor.fetchall()
        for constraint, columns, other_table, other_column in rows:           
            constraint = self.identifier_converter(constraint)
            constraints[constraint] = {
                'primary_key': False,
                'unique': False,
                'foreign_key': (other_table, other_column),
                'check': False,
                'index': False,
                'columns': columns.split(','),
            }
        # Now get indexes
        cursor.execute("""
            SELECT
                ind.index_name,
                ind.index_type,
                LISTAGG(LOWER(cols.column_name), ',') WITHIN GROUP (ORDER BY cols.column_position),
                LISTAGG(cols.descend, ',') WITHIN GROUP (ORDER BY cols.column_position)
            FROM
                user_ind_columns cols, user_indexes ind
            WHERE
                cols.table_name = '%s' AND
                NOT EXISTS (
                    SELECT 1
                    FROM user_constraints cons
                    WHERE ind.index_name = cons.index_name
                ) AND cols.index_name = ind.index_name
            GROUP BY ind.index_name, ind.index_type
        """ % table_name.upper().replace('\'', '\'\''))
        rows = cursor.fetchall()
        for constraint, type_, columns, orders in rows:
            if isinstance(constraint, str) and re.findall(r'INDEX\d{8}', constraint):
                continue            
            constraint = self.identifier_converter(constraint)
            constraints[constraint] = {
                'primary_key': False,
                'unique': False,
                'foreign_key': None,
                'check': False,
                'index': True,
                'type': 'idx' if type_ == 'NORMAL' else type_,
                'columns': columns.split(','),
                'orders': orders.split(','),
            }
        return constraints
    
    # added on 2019-7-30
    def get_sequences(self, cursor, table_name, table_fields=()):
        cursor.execute("""
            SELECT
                user_constraints.constraint_name,
                cols.column_name
            FROM
                user_constraints,
                user_cons_columns cols
            WHERE
                user_constraints.constraint_name = cols.constraint_name
                AND user_constraints.table_name = cols.table_name
                AND user_constraints.constraint_type = 'P'
                AND cols.table_name = UPPER(?)
        """, [table_name])
        row = cursor.fetchone()
        if row:
            return [{
                'name': self.identifier_converter(row[0]),
                'table': self.identifier_converter(table_name),
                'column': self.identifier_converter(row[1]),
            }]
        for f in table_fields:
            if isinstance(f, models.AutoField):
                return [{'table': table_name, 'column': f.column}]
        return []   
        
