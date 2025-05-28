import binascii
import copy
import datetime
import re
import django
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.utils import DatabaseError
from django.db.models import NOT_PROVIDED

class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):
    """
    This class (and its subclasses) are responsible for emitting schema-changing
    statements to the databases - model creation/removal/alteration, field
    renaming, index fiddling, and so on.

    It is intended to eventually completely replace DatabaseCreation.

    This class should be used by creating an instance for each set of schema
    changes (e.g. a migration file), and by first calling start(),
    then the relevant actions, and then commit(). This is necessary to allow
    things like circular foreign key references - FKs will only be created once
    commit() is called.
    """

    sql_alter_column_type = "MODIFY %(column)s %(type)s"
    sql_alter_column_null = "MODIFY %(column)s NULL"
    sql_alter_column_not_null = "MODIFY %(column)s NOT NULL"
    sql_alter_column_default = "ALTER COLUMN %(column)s SET DEFAULT %(default)s"

    sql_create_index = "CREATE INDEX %(name)s ON %(table)s (%(columns)s)%(extra)s"  

    def quote_value(self, value):
        """
        Returns a quoted version of the value so it's safe to use in an SQL
        string. This is not safe against injection from user code; it is
        intended only for use in making SQL scripts or preparing default values
        for particularly tricky backends (defaults are not user-defined, though,
        so this is safe).
        """
        if isinstance(value, (datetime.date, datetime.time, datetime.datetime)):
            return "'%s'" % value
        
        elif isinstance(value, str):
            return "'%s'" % value.replace("\'", "\'\'").replace('%', '%%')
        elif isinstance(value, (bytes, bytearray, memoryview)):
            return "'%s'" % value.hex()
        
        elif isinstance(value, bool):
            return "1" if value else "0"
        else:
            return str(value)

    def _set_field_new_type(self, field, new_type):
        """
        Keep the NULL and DEFAULT properties of the old field. If it has
        changed, it will be handled separately.
        """
        if django.VERSION > (5, 0):
            if field.db_default is not NOT_PROVIDED:
                default_sql, params = self.db_default_sql(field)
                default_sql %= tuple(self.quote_value(p) for p in params)
                new_type += f" DEFAULT {default_sql}"
        if field.null:
            new_type += " NULL"
        else:
            new_type += " NOT NULL"
        return new_type

            
    def prepare_default(self, value):
        """
        Only used for backends which have requires_literal_defaults feature
        """
        return self.quote_value(value)
    
    if django.VERSION >= (4, 2):    
        def _alter_column_type_sql(self, model, old_field, new_field, new_type, old_collation, new_collation):
            
            new_type = self._set_field_new_type(old_field, new_type)
            
            return super()._alter_column_type_sql(model, old_field, new_field, new_type, old_collation, new_collation)
    else:
        def _alter_column_type_sql(self, model, old_field, new_field, new_type):
            """
            Hook to specialize column type alteration for different backends,
            for cases when a creation type is different to an alteration type
            (e.g. SERIAL in PostgreSQL, PostGIS fields).

            Return a two-tuple of: an SQL fragment of (sql, params) to insert into
            an ALTER TABLE statement and a list of extra (sql, params) tuples to
            run once the field is altered.
            """
        
            if new_type == "INTEGER IDENTITY(1,1)" or new_type == "BIGINT IDENTITY(1,1)":
                return (("ADD %(column)s IDENTITY(1,1)" % {"column": self.quote_name(new_field.column),},[],),[],)    
        
            return ((self.sql_alter_column_type % {"column": self.quote_name(new_field.column),"type": new_type,},[],),[],)    


    def _field_should_be_indexed(self, model, field):
        create_index = super()._field_should_be_indexed(model, field)
        db_type = field.db_type(self.connection)
        if db_type is not None and db_type.lower() in self.connection._limited_data_types:
            return False
        return create_index    

        
