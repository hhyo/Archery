import binascii
import copy
import datetime
import re
import sys

import django
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.utils import DatabaseError
if django.VERSION<(3,0):
    from django.utils import six


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

    def quote_value(self, value):
        """
        Returns a quoted version of the value so it's safe to use in an SQL
        string. This is not safe against injection from user code; it is
        intended only for use in making SQL scripts or preparing default values
        for particularly tricky backends (defaults are not user-defined, though,
        so this is safe).
        """
        if sys.version_info.major == 2:
            if isinstance(value, unicode):
                value_return = value.encode('utf-8')
                return "'%s'" % value_return.replace("\'", "\'\'").replace('%', '%%')
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
            
    def prepare_default(self, value):
        """
        Only used for backends which have requires_literal_defaults feature
        """
        return self.quote_value(value)
        
                    
        
