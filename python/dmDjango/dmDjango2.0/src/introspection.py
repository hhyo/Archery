from collections import namedtuple
import re
import dmPython

from django.db.backends.base.introspection import (
    BaseDatabaseIntrospection, FieldInfo, TableInfo,
)

FieldInfo = namedtuple('FieldInfo', FieldInfo._fields + ('extra',))
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
        dmPython.STRING: 'TextField',
        dmPython.INTERVAL: 'DurationField',                            
    }
    
    cache_bust_counter = 1

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
            
        return [TableInfo(row[0], row[1])
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
                END as internal_size
            FROM user_tab_cols,TMP_VIEW
            WHERE table_name = TMP_VIEW.tab_name and column_name = TMP_VIEW.colname;
            """, [table_name.replace('\'', '\'\'')])
        field_map = {
            column: (internal_size, default if default != 'NULL' else None)
            for column, default, internal_size in cursor.fetchall()
        }
        self.cache_bust_counter += 1
        cursor.execute("SELECT * FROM {} WHERE ROWNUM < 2 AND {} > 0".format(
            self.connection.ops.quote_name(table_name.replace('\'', '\'\'')),
            self.cache_bust_counter))
        description = []
        for desc in cursor.description:
            name = desc[0]
            internal_size, default = field_map[name]
            name = name % {}
            description.append(FieldInfo(
                self.identifier_converter(name), desc[1], desc[2], internal_size, desc[4] or 0,
                desc[5] or 0, desc[6], default))
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
        constraints = self.get_key_columns(cursor, table_name)
        relations = {}
        for my_fieldname, other_table, other_field in constraints:
            relations[my_fieldname] = (other_field, other_table)
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
        """ % (table_name.replace('\'', '\'\''))
         
        key_columns = []
        cursor.execute(sql)
        key_columns.extend(cursor.fetchall())
        return key_columns

    def get_indexes(self, cursor, table_name):
        """
        Returns a dictionary of indexed fieldname -> infodict for the given
        table, where each infodict is in the format:
            {'primary_key': boolean representing whether it's the primary key,
             'unique': boolean representing whether it's a unique index}

        Only single-column indexes are introspected.
        """
        sql = """SELECT LOWER(uic.column_name) as column_name,
            CASE user_constraints.constraint_type WHEN 'P' THEN 1 ELSE 0
            END AS is_primary_key,
            CASE user_indexes.uniqueness WHEN 'UNIQUE' THEN 1 ELSE 0
            END AS is_unique
            FROM user_constraints, user_indexes, user_ind_columns uic
            WHERE user_constraints.constraint_type (+) = 'P'
            AND user_constraints.index_name (+) = uic.index_name
            AND user_indexes.uniqueness (+) = 'UNIQUE'
            AND user_indexes.index_name (+) = uic.index_name
            AND uic.table_name = UPPER('%s')
            AND uic.column_position = 1
            AND NOT EXISTS(
            SELECT 1
            FROM user_ind_columns uic_1
            WHERE uic_1.index_name = uic.index_name
            AND uic_1.column_position = 2)
        """
     
        cursor.execute(sql % table_name)
        
        rows = list(cursor.fetchall())        
        indexes = {}
        for row in rows:            
            indexes[row[0]] = {'primary_key': bool(row[1]), 'unique': bool(row[2])}
        return indexes

    def get_constraints(self, cursor, table_name):
        """
        Retrieves any constraints or keys (unique, pk, fk, check, index)
        across one or more columns.

        Returns a dict mapping constraint names to their attributes,
        where attributes is a dict with keys:
         * columns: List of columns this covers
         * primary_key: True if primary key, False otherwise
         * unique: True if this is a unique constraint, False otherwise
         * foreign_key: (table, column) of target, or None
         * check: True if check constraint, False otherwise
         * index: True if index, False otherwise.

        Some backends may return special constraint names that don't exist
        if they don't name constraints of a certain type (e.g. SQLite)
        """
        constraints = {}
        # Loop over the constraints, getting PKs and uniques
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
                AND cols.table_name = ?
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
        
