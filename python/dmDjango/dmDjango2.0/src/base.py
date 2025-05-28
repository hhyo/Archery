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
import django

from django.conf import settings
from django.db import utils
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.base.validation import BaseDatabaseValidation
if django.VERSION<(3,0):
    from django.utils import six, timezone
from django.utils.duration import duration_string
from django.utils.encoding import force_bytes, force_text
from django.utils.functional import cached_property

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

DatabaseError = Database.DatabaseError
IntegrityError = Database.IntegrityError   

class DatabaseWrapper(BaseDatabaseWrapper):
    vendor = 'Dameng'
    
    data_types = {
        'AutoField': 'INTEGER IDENTITY(1,1)',
        'BigAutoField': 'BIGINT IDENTITY(1,1)',
        'BinaryField': 'BLOB',
        'BooleanField': 'bit',
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
        'NullBooleanField': 'bit',
        'OneToOneField': 'INTEGER',
        'PositiveIntegerField': 'INTEGER',
        'PositiveSmallIntegerField': 'SMALLINT',
        'SlugField': 'VARCHAR(%(max_length)s)',
        'SmallIntegerField': 'SMALLINT',
        'TextField': 'TEXT',
        'TimeField': 'TIME',
        'URLField': 'VARCHAR(%(max_length)s)',
        'UUIDField': 'VARCHAR(32)',
    }
    
    data_type_check_constraints = {
        'BooleanField': '%(qn_column)s IN (0,1)',
        'NullBooleanField': '(%(qn_column)s IN (0,1)) OR (%(qn_column)s IS NULL)',
        'PositiveIntegerField': '%(qn_column)s >= 0',
        'PositiveSmallIntegerField': '%(qn_column)s >= 0',
    }

    operators = {
        'exact': '= %s',
        'iexact': 'LIKE %s',
        'contains': 'LIKE %s',
        'icontains': 'LIKE %s',
        'regex': 'REGEXP %s',
        'iregex': 'REGEXP %s',
        'gt': '> %s',
        'gte': '>= %s',
        'lt': '< %s',
        'lte': '<= %s',
        'startswith': 'LIKE %s',
        'endswith': 'LIKE %s',
        'istartswith': 'LIKE %s',
        'iendswith': 'LIKE %s',
    }
    
    pattern_esc = r"REPLACE(REPLACE(REPLACE({}, '\\', '\\\\'), '%%', '\%%'), '_', '\_')"
    pattern_ops = {
        'contains': "LIKE BINARY CONCAT('%%', {}, '%%')",
        'icontains': "LIKE CONCAT('%%', {}, '%%')",
        'startswith': "LIKE BINARY CONCAT({}, '%%')",
        'istartswith': "LIKE CONCAT({}, '%%')",
        'endswith': "LIKE BINARY CONCAT('%%', {})",
        'iendswith': "LIKE CONCAT('%%', {})",
    }

    Database = Database
    SchemaEditorClass = DatabaseSchemaEditor
    client_class = DatabaseClient
    creation_class = DatabaseCreation
    features_class = DatabaseFeatures
    introspection_class = DatabaseIntrospection
    ops_class = DatabaseOperations
    validation_class = BaseDatabaseValidation    

    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper, self).__init__(*args, **kwargs)

        self.features = DatabaseFeatures(self)        
        self.ops = DatabaseOperations(self)
        self.client = DatabaseClient(self)
        self.creation = DatabaseCreation(self)
        self.introspection = DatabaseIntrospection(self)
        self.validation = BaseDatabaseValidation(self)    
        
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
    
    def get_new_connection(self, conn_params):
        params = self._connect_string()
        return Database.connect(user = params['user'], 
                                password = params['password'],
                                host = params['host'],
                                port = params['port'],
                                mpp_login = params['mpp_login'],
                                ssl_path = params['ssl_path'],
                                ssl_pwd = params['ssl_pwd'],
                                **conn_params
                                )
    
    def init_connection_state(self):    
        #do nothing
        pass
        
    def create_cursor(self, name=None):
        cursor = self.connection.cursor()
        return CursorWrapper(cursor)   
    
    def _set_autocommit(self, autocommit):
        with self.wrap_database_errors:
            self.connection.autoCommit = autocommit
            
    def is_usable(self):
        "TODO"
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
    
    
    
class CursorWrapper(object):
        
    codes_for_integrityerror = (1048,)

    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, args=None):
        try:
            # args is None means no string interpolation
            return self.cursor.execute(query, args)
        except Database.OperationalError as e:
            # Map some error codes to IntegrityError, since they seem to be
            # misclassified and Django would prefer the more logical place.
            if e.args[0] in self.codes_for_integrityerror:
                if django.VERSION<(3,0):
                    six.reraise(utils.IntegrityError, utils.IntegrityError(*tuple(e.args)), sys.exc_info()[2])
                if django.VERSION>=(3,0):
                    raise utils.IntegrityError(*tuple(e.args))
            raise

    def executemany(self, query, args):
        try:
            return self.cursor.executemany(query, args)
        except Database.OperationalError as e:
            # Map some error codes to IntegrityError, since they seem to be
            # misclassified and Django would prefer the more logical place.
            if e.args[0] in self.codes_for_integrityerror:
                if django.VERSION < (3, 0):
                    six.reraise(utils.IntegrityError, utils.IntegrityError(*tuple(e.args)), sys.exc_info()[2])
                if django.VERSION>=(3,0):
                    raise utils.IntegrityError(*tuple(e.args))
            raise

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return self.__dict__[attr]
        else:
            return getattr(self.cursor, attr)

    def __iter__(self):
        return iter(self.cursor)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):        
        self.close()