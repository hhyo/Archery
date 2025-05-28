from __future__ import unicode_literals

import datetime
import re
import uuid

import django
from django.conf import settings
from django.db.backends.base.operations import BaseDatabaseOperations
from django.db.backends.utils import truncate_name
if django.VERSION<(3,0):
    from django.utils import six
from django.utils import timezone
from django.utils.encoding import force_bytes, force_text

from .base import Database
from .utils import InsertIdVar, convert_unicode


class DatabaseOperations(BaseDatabaseOperations):
    """
    This class encapsulates all backend-specific differences, such as the way
    a backend performs ordering or calculates the ID of a recently-inserted
    row.
    """
    
    compiler_module = "dmDjango.compiler"
    
    # CharField data type if the max_length argument isn't provided.
    cast_char_field_without_max_length = 'varchar'
    
    # Prefix for EXPLAIN queries, or None EXPLAIN isn't supported.
    explain_prefix = 'EXPLAIN'
    
    # Mapping of Field.get_internal_type() (typically the model field's class
    # name) to the data type to use for the Cast() function, if different from
    # DatabaseWrapper.data_types.    
    cast_data_types = {
        'AutoField': 'integer',
        'BigAutoField': 'bigint',
    }    
    
    # DAMENG stores positive fields as UNSIGNED ints.
    integer_field_ranges = dict(BaseDatabaseOperations.integer_field_ranges,
        PositiveSmallIntegerField=(0, 65535),
        PositiveIntegerField=(0, 4294967295),
    )

    def date_extract_sql(self, lookup_type, field_name):
        """
        Given a lookup_type of 'year', 'month' or 'day', returns the SQL that
        extracts a value from the given date field field_name.
        """
        if lookup_type == 'week_day':            
            return "DAYOFWEEK(%s)" % field_name
        else:            
            return "EXTRACT(%s FROM %s)" % (lookup_type.upper(), field_name)

    def date_interval_sql(self, timedelta):
        """
        Implements the date interval functionality for expressions
        """
        minutes, seconds = divmod(timedelta.seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days = str(timedelta.days)
        day_precision = len(days)
        fmt = "INTERVAL '%s %02d:%02d:%02d.%06d' DAY(%d) TO SECOND(6)"
        return fmt % (days, hours, minutes, seconds, timedelta.microseconds,
                day_precision), []

    def date_trunc_sql(self, lookup_type, field_name):
        """
        Given a lookup_type of 'year', 'month' or 'day', returns the SQL that
        truncates the given date field field_name to a date object with only
        the given specificity.
        """
        if lookup_type in ('year', 'month'):
            return "TRUNC(%s, '%s')" % (field_name, lookup_type.upper())
        else:
            return "TRUNC(%s)" % field_name
        
    _tzname_re = re.compile(r'^[\w/:+-]+$')

    def _convert_field_to_tz(self, field_name, tzname):
        if not settings.USE_TZ:
            return field_name
        if not self._tzname_re.match(tzname):
            raise ValueError("Invalid time zone name: %s" % tzname)
        # Convert from UTC to local time, returning TIMESTAMP WITH TIME ZONE.
        result = "(FROM_TZ(%s, '0:00') AT TIME ZONE '%s')" % (field_name, tzname)
        # Extracting from a TIMESTAMP WITH TIME ZONE ignore the time zone.
        # Convert to a DATETIME. There's no built-in function to do that; the easiest is to go through a string.
        result = "TO_CHAR(%s, 'YYYY-MM-DD HH24:MI:SS')" % result
        result = "TO_DATE(%s, 'YYYY-MM-DD HH24:MI:SS')" % result
        # Re-convert to a TIMESTAMP because EXTRACT only handles the date part
        # on DATE values, even though they actually store the time part.
        return "CAST(%s AS TIMESTAMP)" % result        

    def datetime_cast_date_sql(self, field_name, tzname):
        """
        Returns the SQL necessary to cast a datetime value to date value.
        """
        field_name = self._convert_field_to_tz(field_name, tzname)
        sql = 'TRUNC(%s)' % field_name
        return sql, []

    def datetime_extract_sql(self, lookup_type, field_name, tzname):
        """
        Given a lookup_type of 'year', 'month', 'day', 'hour', 'minute' or
        'second', returns the SQL that extracts a value from the given
        datetime field field_name, and a tuple of parameters.
        """
        field_name = self._convert_field_to_tz(field_name, tzname)
        sql = self.date_extract_sql(lookup_type, field_name)
        return sql

    def datetime_trunc_sql(self, lookup_type, field_name, tzname):
        """
        Given a lookup_type of 'year', 'month', 'day', 'hour', 'minute' or
        'second', returns the SQL that truncates the given datetime field
        field_name to a datetime object with only the given specificity, and
        a tuple of parameters.
        """
        field_name = self._convert_field_to_tz(field_name, tzname)        
        if lookup_type in ('year', 'month'):
            sql = "TRUNC(%s, '%s')" % (field_name, lookup_type.upper())
        elif lookup_type == 'week':
            sql = "TRUNC(%s, 'IW')" % field_name
        elif lookup_type == 'day':
            sql = "TRUNC(%s)" % field_name
        elif lookup_type == 'hour':
            sql = "TRUNC(%s, 'HH24')" % field_name
        elif lookup_type == 'minute':
            sql = "TRUNC(%s, 'MI')" % field_name
        else:
            sql = "CAST(%s AS DATETIME)" % field_name
        return sql

    def deferrable_sql(self):
        """
        Returns the SQL necessary to make a constraint "initially deferred"
        during a CREATE TABLE statement.
        """
        return " DEFERRABLE INITIALLY DEFERRED"

    def drop_sequence_sql(self, table):
        """
        Returns any SQL necessary to drop the sequence for the given table.
        Returns None if no SQL is necessary.
        """
        return "DROP SEQUENCE %s;" % self.quote_name(self._get_sequence_name(table))

    def fetch_returned_insert_id(self, cursor):
        """
        Given a cursor object that has just performed an INSERT...RETURNING
        statement into a table that has an auto-incrementing ID, returns the
        newly created ID.
        """
        return int(cursor._insert_id_var.getvalue())

    def field_cast_sql(self, db_type, internal_type):
        """
        Given a column type (e.g. 'BLOB', 'VARCHAR'), and an internal type
        (e.g. 'GenericIPAddressField'), returns the SQL necessary to cast it
        before using it in a WHERE statement. Note that the resulting string
        should contain a '%s' placeholder for the column being searched against.
        """
        if db_type and db_type.endswith('LOB'):
            return "DBMS_LOB.SUBSTR(%s)"
        else:
            return "%s"    

    def last_executed_query(self, cursor, sql, params):
        """
        Returns a string of the query last executed by the given cursor, with
        placeholders replaced with actual values.

        `sql` is the raw query containing placeholders, and `params` is the
        sequence of parameters. These are used by default, but this method
        exists for database backends to provide a better implementation
        according to their own quoting schemes.
        """
        # The DB API definition does not define this attribute.
        statement = cursor.statement
        if django.VERSION<(3,0):
            if statement and six.PY2 and not isinstance(statement, unicode):  # NOQA: unicode undefined on PY3
                statement = statement.decode('utf-8')
        return super(DatabaseOperations, self).last_executed_query(cursor, statement, params)

    def last_insert_id(self, cursor, table_name, pk_name):
        """
        Given a cursor object that has just performed an INSERT statement into
        a table that has an auto-incrementing ID, returns the newly created ID.

        This method also receives the table name and the name of the primary-key
        column.
        """
        cursor.execute('SELECT MAX(%s) from %s' %(self.quote_name(pk_name), self.quote_name(table_name)))
        return cursor.fetchone()[0]

    def lookup_cast(self, lookup_type, internal_type=None):
        """
        Returns the string to use in a query when performing lookups
        ("contains", "like", etc.). The resulting string should contain a '%s'
        placeholder for the column being searched against.
        """
        if lookup_type in ('iexact', 'icontains', 'istartswith', 'iendswith'):
            return "UPPER(%s)"
        return "%s"

    def max_in_list_size(self):
        """
        Returns the maximum number of items that can be passed in a single 'IN'
        list condition, or None if the backend does not impose a limit.
        """
        return 1000

    def max_name_length(self):
        """
        Returns the maximum length of table and column names, or None if there
        is no limit.
        """
        return 128

    def no_limit_value(self):
        """
        Returns the value to use for the LIMIT when we are wanting "LIMIT
        infinity". Returns None if the limit clause can be omitted in this case.
        """
        return 4294967295

    def pk_default_value(self):
        """
        Returns the value to use during an INSERT statement to specify that
        the field should use its default value.
        """
        return 'NULL'

    def process_clob(self, value):
        """
        Returns the value of a CLOB column, for backends that return a locator
        object that requires additional processing.
        """
        if value is None:
            return ''
        return force_text(value.read())

    def return_insert_id(self):
        """
        For backends that support returning the last insert ID as part
        of an insert query, this method returns the SQL and params to
        append to the INSERT query. The returned fragment should
        contain a format string to hold the appropriate column.
        """
        return "RETURNING %s INTO ?", (InsertIdVar(),)

    def quote_name(self, name):
        """
        Returns a quoted version of the given table, index or column name. Does
        not quote the given name if it's already been quoted.
        """    
        if not name.startswith('"') or not name.endswith('"'):
            name = name.replace('\"', '\"\"')
            name = '"%s"' % truncate_name(name, self.max_name_length())
                    
        return name

    def random_function_sql(self):
        """
        Returns an SQL expression that returns a random value.
        """
        return "DBMS_RANDOM.RANDOM"

    def regex_lookup(self, lookup_type):
        """
        Returns the string to use in a query when performing regular expression
        lookups (using "regex" or "iregex"). The resulting string should
        contain a '%s' placeholder for the column being searched against.

        If the feature is not supported (or part of it is not supported), a
        NotImplementedError exception can be raised.
        """
        if lookup_type == 'regex':
            match_option = "'c'"
        else:
            match_option = "'i'"
        return 'REGEXP_LIKE(%%s, %%s, %s)' % match_option

    def savepoint_create_sql(self, sid):
        """
        Returns the SQL for starting a new savepoint. Only required if the
        "uses_savepoints" feature is True. The "sid" parameter is a string
        for the savepoint id.
        """
        return convert_unicode("SAVEPOINT " + self.quote_name(sid))    

    def savepoint_rollback_sql(self, sid):
        """
        Returns the SQL for rolling back the given savepoint.
        """
        return convert_unicode("ROLLBACK TO SAVEPOINT " + self.quote_name(sid))
    
    def savepoint_commit_sql(self, sid):
        """
        Return the SQL for committing the given savepoint.
        """
        return convert_unicode("RELEASE_SAVEPOINT('%s') " % self.quote_name(sid))

    def sql_flush(self, style, tables, sequences, allow_cascade=False):
        """
        Returns a list of SQL statements required to remove all data from
        the given database tables (without actually removing the tables
        themselves).

        The returned value also includes SQL statements required to reset DB
        sequences passed in :param sequences:.

        The `style` argument is a Style object as returned by either
        color_style() or no_style() in django.core.management.color.

        The `allow_cascade` argument determines whether truncation may cascade
        to tables with foreign keys pointing the tables being truncated.
        PostgreSQL requires a cascade even if these tables are empty.
        """
        if tables:            
            sql = ['%s %s %s;' % (
                style.SQL_KEYWORD('TRUNCATE'),
                style.SQL_KEYWORD('TABLE'),
                style.SQL_FIELD(self.quote_name(table))
            ) for table in tables]
            # Since we've just deleted all the rows, running our sequence
            # ALTER code will reset the sequence to 0.
            sql.extend(self.sequence_reset_by_name_sql(style, sequences))
            return sql
        else:
            return []

    def sequence_reset_sql(self, style, model_list):
        """
        Returns a list of the SQL statements required to reset sequences for
        the given models.

        The `style` argument is a Style object as returned by either
        color_style() or no_style() in django.core.management.color.
        """
        from django.db import models
        output = []
        query = self._sequence_reset_sql
        for model in model_list:
            for f in model._meta.local_fields:
                if isinstance(f, models.AutoField):
                    table_name = self.quote_name(model._meta.db_table)
                    sequence_name = self._get_sequence_name(model._meta.db_table)
                    column_name = self.quote_name(f.column)
                    output.append(query % {'sequence': sequence_name,
                                           'table': table_name,
                                           'column': column_name})
                    # Only one AutoField is allowed per model, so don't
                    # continue to loop
                    break
            for f in model._meta.many_to_many:
                if not f.remote_field.through:
                    table_name = self.quote_name(f.m2m_db_table())
                    sequence_name = self._get_sequence_name(f.m2m_db_table())
                    column_name = self.quote_name('id')
                    output.append(query % {'sequence': sequence_name,
                                           'table': table_name,
                                           'column': column_name})
        return output

    def start_transaction_sql(self):
        """
        Returns the SQL statement required to start a transaction.
        """
        return ''

    def tablespace_sql(self, tablespace, inline=False):
        """
        Returns the SQL that will be used in a query to define the tablespace.

        Returns '' if the backend doesn't support tablespaces.

        If inline is True, the SQL is appended to a row; otherwise it's appended
        to the entire CREATE TABLE or CREATE INDEX statement.
        """
        if inline:
            return "USING INDEX TABLESPACE %s" % self.quote_name(tablespace)
        else:
            return "TABLESPACE %s" % self.quote_name(tablespace)    

    def prep_for_iexact_query(self, x):
        return x    

    def adapt_datetimefield_value(self, value):
        """
        Transforms a datetime value to an object compatible with what is expected
        by the backend driver for datetime columns.
        """
        if value is None:
            return None
        
        # DAMENG doesn't support tz-aware datetimes
        if timezone.is_aware(value):
            if settings.USE_TZ:
                value = timezone.make_naive(value, self.connection.timezone)
            else:
                raise ValueError("Dameng does not support timezone-aware datetimes when USE_TZ is False.")

        if django.VERSION<(3,0):
            return six.text_type(value)
        if django.VERSION>=(3,0):
            return str(value)

    def adapt_timefield_value(self, value):
        """
        Transforms a time value to an object compatible with what is expected
        by the backend driver for time columns.
        """
        if value is None:
            return None

        # Dameng doesn't support tz-aware times
        if timezone.is_aware(value):
            raise ValueError("Dameng backend does not support timezone-aware times.")

        return six.text_type(value)    

    def get_db_converters(self, expression):
        """
        Get a list of functions needed to convert field data.

        Some field types on some backends do not provide data in the correct
        format, this is the hook for converter functions.
        """
        converters = super(DatabaseOperations, self).get_db_converters(expression)
        internal_type = expression.output_field.get_internal_type()
        if internal_type == 'TextField':
            converters.append(self.convert_textfield_value)
        elif internal_type == 'BinaryField':
            converters.append(self.convert_binaryfield_value)
        elif internal_type in ['BooleanField', 'NullBooleanField']:
            converters.append(self.convert_booleanfield_value)
        elif internal_type == 'DateTimeField':
            converters.append(self.convert_datetimefield_value)
        elif internal_type == 'DateField':
            converters.append(self.convert_datefield_value)
        elif internal_type == 'TimeField':
            converters.append(self.convert_timefield_value)
        elif internal_type == 'UUIDField':
            converters.append(self.convert_uuidfield_value)        
        return converters 
    
    # convert function
    if django.VERSION>=(2,0):
        def convert_textfield_value(self, value, expression, connection):
            if isinstance(value, Database.LOB):
                value = force_text(value.read())
            return value

        def convert_binaryfield_value(self, value, expression, connection):
            if isinstance(value, Database.LOB):
                value = force_bytes(value.read())
            return value

        def convert_booleanfield_value(self, value, expression, connection):
            if value in (0, 1):
                value = bool(value)
            return value

        def convert_datetimefield_value(self, value, expression, connection):
            if value is not None:
                if settings.USE_TZ:
                    value = timezone.make_aware(value, self.connection.timezone)
            return value

        def convert_datefield_value(self, value, expression, connection):
            if isinstance(value, Database.Timestamp):
                value = value.date()
            return value

        def convert_timefield_value(self, value, expression, connection):
            if isinstance(value, Database.Timestamp):
                value = value.time()
            return value

        def convert_uuidfield_value(self, value, expression, connection):
            if value is not None:
                value = uuid.UUID(value)
            return value

    if django.VERSION<(2,0):
        def convert_textfield_value(self, value, expression, connection, context):
            if isinstance(value, Database.LOB):
                value = force_text(value.read())
            return value

        def convert_binaryfield_value(self, value, expression, connection, context):
            if isinstance(value, Database.LOB):
                value = force_bytes(value.read())
            return value

        def convert_booleanfield_value(self, value, expression, connection, context):
            if value in (0, 1):
                value = bool(value)
            return value

        def convert_datetimefield_value(self, value, expression, connection, context):
            if value is not None:
                if settings.USE_TZ:
                    value = timezone.make_aware(value, self.connection.timezone)
            return value

        def convert_datefield_value(self, value, expression, connection, context):
            if isinstance(value, Database.Timestamp):
                value = value.date()
            return value

        def convert_timefield_value(self, value, expression, connection, context):
            if isinstance(value, Database.Timestamp):
                value = value.time()
            return value

        def convert_uuidfield_value(self, value, expression, connection, context):
            if value is not None:
                value = uuid.UUID(value)
            return value

    def combine_expression(self, connector, sub_expressions):
        if connector == '%%':
            return 'MOD(%s)' % ','.join(sub_expressions)
        elif connector == '&':
            return 'BITAND(%s)' % ','.join(sub_expressions)        
        elif connector == '^':
            return 'POWER(%s)' % ','.join(sub_expressions)
        return super(DatabaseOperations, self).combine_expression(connector, sub_expressions)    
    
    def _get_sequence_name(self, table):
        name_length = self.max_name_length() - 3
        return '%s_SQ' % truncate_name(table, name_length).upper()

    def _get_trigger_name(self, table):
        name_length = self.max_name_length() - 3
        return '%s_TR' % truncate_name(table, name_length).upper()            
    
    
    def bulk_insert_sql(self, fields, placeholder_rows):
        return " UNION ALL ".join(
            "SELECT %s FROM DUAL" % ", ".join(row)
            for row in placeholder_rows
        )
    
    #added from Django version 2.2.4
    def binary_placeholder_sql(self, value):
        """
        Some backends require special syntax to insert binary content (MySQL
        for example uses '_binary %s').
        """
        return '?'    
        


    
