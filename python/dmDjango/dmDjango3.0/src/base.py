"""
Dameng database backend for Django.
"""
from __future__ import unicode_literals

import datetime
import decimal
import os
import platform
import sys
import warnings

from django.conf import settings
from django.db import utils
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.base.validation import BaseDatabaseValidation
from django.utils.duration import duration_string
from django.utils.encoding import force_bytes, force_str
from django.utils.functional import cached_property
from django.utils.asyncio import async_unsafe
from django.utils.regex_helper import _lazy_re_compile

try:
    import dmPython as Database
    Database.Binary = bytes
except ImportError as e:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Error loading dmPython module: %s" % e)

# Some of these import dmPython, so import them after checking if it's installed.
from .client import DatabaseClient                      # isort:skip
from .creation import DatabaseCreation                  # isort:skip
from .features import DatabaseFeatures                  # isort:skip
from .introspection import DatabaseIntrospection        # isort:skip
from .operations import DatabaseOperations              # isort:skip
from .schema import DatabaseSchemaEditor                # isort:skip
from .utils import convert_unicode                      # isort:skip
from .validation import DatabaseValidation              # isort:skip

DatabaseError = Database.DatabaseError
IntegrityError = Database.IntegrityError   

class DatabaseWrapper(BaseDatabaseWrapper):
    vendor = 'Dameng'
    display_name = 'DM'
    
    data_types = {
        'SmallAutoField': 'INTEGER IDENTITY(1,1)',
        'AutoField': 'INTEGER IDENTITY(1,1)',
        'BigAutoField': 'BIGINT IDENTITY(1,1)',
        'BinaryField': 'BLOB',
        'BooleanField': 'TINYINT',
        'CharField': 'VARCHAR(%(max_length)s)',
        'CommaSeparatedIntegerField': 'VARCHAR(%(max_length)s)',
        'DateField': 'DATE',
        'DateTimeField': 'TIMESTAMP',
        'DecimalField': 'NUMBER(%(max_digits)s, %(decimal_places)s)',
        'DurationField': 'INTERVAL DAY(9) TO SECOND(6)',
        'FileField': 'VARCHAR(%(max_length)s)',
        'FilePathField': 'VARCHAR(%(max_length)s)',
        'FloatField': 'DOUBLE PRECISION',
        'IntegerField': 'INTEGER',
        'BigIntegerField': 'BIGINT',
        'IPAddressField': 'VARCHAR(15)',
        'GenericIPAddressField': 'VARCHAR(39)',
        'NullBooleanField': 'TINYINT',
        'OneToOneField': 'INTEGER',
        'PositiveIntegerField': 'INTEGER',
        'PositiveBigIntegerField': 'BIGINT',
        'PositiveSmallIntegerField': 'SMALLINT',
        'SlugField': 'VARCHAR(%(max_length)s)',
        'SmallIntegerField': 'SMALLINT',
        'TextField': 'TEXT',
        'TimeField': 'TIMESTAMP',
        'URLField': 'VARCHAR(%(max_length)s)',
        'UUIDField': 'VARCHAR(32)',
        'JSONField': 'TEXT',
    }
    
    data_type_check_constraints = {
        'BooleanField': '%(qn_column)s IN (0,1)',
        'NullBooleanField': '(%(qn_column)s IN (0,1)) OR (%(qn_column)s IS NULL)',
        'PositiveIntegerField': '%(qn_column)s >= 0',
        'PositiveSmallIntegerField': '%(qn_column)s >= 0',
        'PositiveBigIntegerField': '%(qn_column)s >= 0',
        'JSONField': '%(qn_column)s IS JSON',
    }
    
    # DM doesn't support a database index on these columns.
    _limited_data_types = ('clob', 'nclob', 'blob', 'text')    

    operators = {
        'exact': '= %s',
        'iexact': '= UPPER(%s)',
        'contains': "LIKE %s ESCAPE '\\'",
        'icontains': "LIKE UPPER(%s) ESCAPE '\\'",
        'gt': '> %s',
        'gte': '>= %s',
        'lt': '< %s',
        'lte': '<= %s',
        'startswith': "LIKE %s ESCAPE '\\'",
        'endswith': "LIKE %s ESCAPE '\\'",
        'istartswith': "LIKE UPPER(%s) ESCAPE '\\'",
        'iendswith': "LIKE UPPER(%s) ESCAPE '\\'",
    }
    
    pattern_esc = r"REPLACE(REPLACE(REPLACE({}, '\', '\\'), '%', '\%'), '_', '\_')"
    
    pattern_ops = {
        'contains': r"LIKE '%' || {} || '%' ESCAPE '\'",
        'icontains': r"LIKE '%' || UPPER({}) || '%' ESCAPE '\'",
        'startswith': r"LIKE {} || '%' ESCAPE '\'",
        'istartswith': r"LIKE UPPER({}) || '%%' ESCAPE '\'",
        'endswith': r"LIKE '%' || {} ESCAPE '\'",
        'iendswith': r"LIKE '%' || UPPER({}) ESCAPE '\'",
    }

    Database = Database
    SchemaEditorClass = DatabaseSchemaEditor
    client_class = DatabaseClient
    creation_class = DatabaseCreation
    features_class = DatabaseFeatures
    introspection_class = DatabaseIntrospection
    ops_class = DatabaseOperations
    validation_class = DatabaseValidation    

    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper, self).__init__(*args, **kwargs)

        self.features = DatabaseFeatures(self)        
        self.ops = DatabaseOperations(self)
        self.client = DatabaseClient(self)
        self.creation = DatabaseCreation(self)
        self.introspection = DatabaseIntrospection(self)
        self.validation = DatabaseValidation(self)    
        
    def get_connection_params(self):        
        conn_params = self.settings_dict['OPTIONS'].copy()        
        return conn_params
    
    def _connect_string(self):
        settings_dict = self.settings_dict            
        user = settings_dict['OPTIONS'].get('user', settings_dict['USER'].strip())
        passwd = settings_dict['OPTIONS'].get('passwd', settings_dict['PASSWORD'].strip())
        host = settings_dict['OPTIONS'].get('host', settings_dict['HOST'].strip())
        port = settings_dict['OPTIONS'].get('port', settings_dict['PORT'].strip())        
        mpp_type = settings_dict['OPTIONS'].get('mpp_type', {}).get('mpp_type')
        ssl_path = settings_dict['OPTIONS'].get('ssl_path', {}).get('ssl_path')
        ssl_pwd = settings_dict['OPTIONS'].get('ssl_pwd', {}).get('ssl_pwd')            
        
        if mpp_type :
            if port is None or port == "":
                conn_string = '%s/%s*%s@%s' % (user, passwd, mpp_type, host)    #use dm service name in dm_svc.conf to connect to db
            else:
                conn_string = '%s/%s*%s@%s:%s' % (user, passwd, mpp_type, host, port)
        else :
            if port is None or port == "":
                conn_string = '%s/%s@%s' % (user, passwd, host)     #use dm service name in dm_svc.conf to connect to db
            else:
                conn_string = '%s/%s@%s:%s' % (user, passwd, host, port)
                
        if ssl_path :
            conn_string += '#%s' % (ssl_path)
                
        if ssl_pwd :
            conn_string += '@%s' % (ssl_pwd) 
        
        return conn_string        
    
    def _connect_params(self):
        settings_dict = self.settings_dict            
        user = settings_dict['OPTIONS'].get('user', settings_dict['USER'].strip())
        passwd = settings_dict['OPTIONS'].get('passwd', settings_dict['PASSWORD'].strip())
        host = settings_dict['OPTIONS'].get('host', settings_dict['HOST'].strip())
        port = settings_dict['OPTIONS'].get('port', settings_dict['PORT'].strip())        
        mpp_type = settings_dict['OPTIONS'].get('mpp_type', {}).get('mpp_type')
        ssl_path = settings_dict['OPTIONS'].get('ssl_path', {}).get('ssl_path')
        ssl_pwd = settings_dict['OPTIONS'].get('ssl_pwd', {}).get('ssl_pwd')            
        
        conn_param = {}
        conn_param['user'] = user
        conn_param['password'] = passwd
        conn_param['host'] = host
        conn_param['port'] = int(port)
        conn_param['mpp_login'] = False
        conn_param['ssl_path'] = ''
        conn_param['ssl_pwd'] = ''
        
        if ssl_path:
            conn_param['ssl_path'] = ssl_path
            
        if ssl_pwd:
            conn_param['ssl_pwd'] = ssl_pwd
            
        if mpp_type:
            conn_param['mpp_login'] = mpp_type
        
        return conn_param    
    
    @async_unsafe
    def get_new_connection(self, conn_params):
        params = self._connect_params()
        try:
            return Database.connect(user = params['user'], 
                                password = params['password'],
                                host = params['host'],
                                port = params['port'],
                                mpp_login = params['mpp_login'],
                                ssl_path = params['ssl_path'],
                                ssl_pwd = params['ssl_pwd'],
                                **conn_params
                                )
        except Database.DatabaseError as e:
            raise DatabaseError
        except Exception as e:
            raise
    
    def init_connection_state(self):    
        #do nothing
        pass
        
    def create_cursor(self, name=None):
        cursor = self.connection.cursor()
        return CursorWrapper(cursor)   
    
    def _set_autocommit(self, autocommit):
        with self.wrap_database_errors:
            self.connection.autoCommit = autocommit
    
    def disable_constraint_checking(self):
        """
        Disable foreign key checks, primarily for use in adding rows with
        forward references. Always return True to indicate constraint checks
        need to be re-enabled.
        """
        tables = self.introspection.django_table_names(only_existing=True, include_views=False)
        
        if not tables:
            return False
        
        constraints = set()
        
        for foreign_table, constraint in self.ops._get_django_constraints(tables):
            constraints.add((foreign_table, constraint)) 
        
        sqls = [
            'ALTER TABLE /*+ALTER_TAB_COMMIT(0)*/ %s DISABLE CONSTRAINT %s;' % (
                self.ops.quote_name(table),
                self.ops.quote_name(constraint),
            ) for table, constraint in constraints
        ]
        
        auto_tran_sql = """
        DECLARE
            PRAGMA AUTONOMOUS_TRANSACTION;
        BEGIN
        
        """;
        
        for sql in sqls:
            auto_tran_sql = auto_tran_sql + "EXECUTE IMMEDIATE '%s';\n" % (sql)
        
        auto_tran_sql = auto_tran_sql + """
            COMMIT;
        END;
        """
        
        with self.cursor() as cursor:
            for sql in sqls:
                cursor.execute(sql)
        
        return False

    def enable_constraint_checking(self):
        """
        Re-enable foreign key checks after they have been disabled.
        """
        
        self.needs_rollback, needs_rollback = False, self.needs_rollback
        
        tables = self.introspection.django_table_names(only_existing=True, include_views=False)
    
        if not tables:
            self.needs_rollback = needs_rollback
            return
    
        constraints = set()
    
        for foreign_table, constraint in self.ops._get_django_constraints(tables):
            constraints.add((foreign_table, constraint)) 
        
        sqls = [
                'ALTER TABLE /*+ALTER_TAB_COMMIT(0)*/ %s ENABLE CONSTRAINT %s;' % (
                    self.ops.quote_name(table),
                    self.ops.quote_name(constraint),
                    ) for table, constraint in constraints
            ]
        
        try:
            with self.cursor() as cursor:
                for sql in sqls:
                    cursor.execute(sql)
        finally:
            self.needs_rollback = needs_rollback
            
    def check_constraints(self, table_names=None):
        """
        Backends can override this method if they can apply constraint
        checking (e.g. via "SET CONSTRAINTS ALL IMMEDIATE"). Should raise an
        IntegrityError if any invalid foreign key references are encountered.
        """
        self.enable_constraint_checking()    

    def is_usable(self):
        try:
            cursor = self.connection.cursor()
            cursor.execute('select 1 from dual')
        except Database.Error:
            return False
        else:
            return True
        
    @cached_property
    def dameng_full_version(self):
        with self.temporary_connection():
            return self.connection.server_version

    @cached_property
    def dameng_version(self):
        try:
            return int(self.dameng_full_version.split('.')[0])
        except ValueError:
            return None        


FORMAT_QMARK_REGEX = _lazy_re_compile(r'(?<!%)%s')
    
class CursorWrapper(object):
        
    codes_for_integrityerror = (1048,)

    def __init__(self, cursor):
        self.cursor = cursor

    def _getTableNameBySql(self, sql_org) :
        sql = sql_org.lower()        
        '''find begin index'''
        headlen = 0
        if -1 != sql.find("insert into"):
            headlen = len("insert into")
        elif -1 != sql.find("insert"):
            headlen = len("insert")
        else :
            headlen = 0
    
        if 0 == headlen:
            return None
    
        ''' find end index----keyword 'values' is after tablename or tablename(col1,col2...)'''
        valuesIndex = sql.find("values")
        if -1 == valuesIndex:
            return None;
    
        '''extract table name'''
        sqltb = sql_org[headlen : valuesIndex]
        leftB = sqltb.find("(")
        if -1 == leftB:
            return sqltb
        else :
            return sqltb[0 : leftB]
        
    def _setLastInsertIdentity(self, insertsql, bflag):
        tbname = self._getTableNameBySql(insertsql)
            
        if bflag :
            self.cursor.execute('SET IDENTITY_INSERT %s ON WITH REPLACE NULL' % tbname)
        else :
            self.cursor.execute('SET IDENTITY_INSERT %s OFF' % tbname)

    def _check_placeholder(self, sql):
        if not isinstance(sql, str):
            return sql
        
        ind = sql.find("%s")
        if -1 == ind:
            return sql
        
        ret_sql = ""
        while -1 != ind:
            ret_sql = ret_sql + sql[0 : ind]
            sql = sql[ind : ]
            ret_len = len(ret_sql)
            
            if (ret_sql[ret_len - 1] == "'" and sql[2] == "'") or (ret_sql[ret_len - 1] == '"' and sql[2] == '"'):
                ret_sql = ret_sql + sql[0 : 3] 
                sql = sql[3 : ]
            else:
                ret_sql = ret_sql + "?"
                sql = sql[2 : ]
                
            ind = sql.find("%s")
            
        ret_sql = ret_sql + sql
        
        return ret_sql
    
    def convert_query(self, query):
        return FORMAT_QMARK_REGEX.sub('?', query).replace('%%', '%')
    
    def execute(self, query, args=None):
        try:
            # args is None means no string interpolation
            try:
                if args is None:
                    return self.cursor.execute(query, args)
                
                query = self.convert_query(query)
                return self.cursor.execute(query, args)
            except Database.DatabaseError as e:
                if hasattr(e.args[0], "code") == False:
                    raise
                
                if e.args[0].code == -2723:
                    self._setLastInsertIdentity(query, True)
                    self.cursor.execute(query, args)
                    lastrowid = self.cursor.lastrowid
                    self._setLastInsertIdentity(query, False)
                    self.cursor.lastrowid = lastrowid
                elif e.args[0].code == -6407 or e.args[0].code == -7116:
                    self.cursor.execute(query, args)
                elif e.args[0].code == -6105:
                    raise
                else:
                    raise
            except Database.OperationalError as e:
                raise
        except Database.OperationalError as e:
            # Map some error codes to IntegrityError, since they seem to be
            # misclassified and Django would prefer the more logical place.
            if e.args[0] in self.codes_for_integrityerror:
                raise IntegrityError(*tuple(e.args))
            raise
        except Database.DatabaseError as e:
            if hasattr(e.args[0], "code") == False:
                tmpstr = str(e)
                if tmpstr.find("Not Open") != -1:
                    raise Database.InterfaceError
            
            if isinstance(e, Database.IntegrityError):
                raise IntegrityError(*tuple(e.args))
            
            raise

    def executemany(self, query, args):
        if not args:
            # No params given, nothing to do
            return None

        try:
            query = self.convert_query(query)
            return self.cursor.executemany(query, args)
        except Database.OperationalError as e:
            # Map some error codes to IntegrityError, since they seem to be
            # misclassified and Django would prefer the more logical place.
            if e.args[0] in self.codes_for_integrityerror:
                raise IntegrityError(*tuple(e.args))
            raise

    def __getattr__(self, attr):
        if attr == 'rowcount':
            pass
        if attr in self.__dict__:
            return self.__dict__[attr]
        else:
            return getattr(self.cursor, attr)
        return getattr(self.cursor, attr)

    def __iter__(self):
        return iter(self.cursor)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):        
        self.close()
