import sys
import time

from django.db.backends.base.creation import BaseDatabaseCreation

TEST_DATABASE_PREFIX = 'test_'

class DatabaseCreation(BaseDatabaseCreation):            
    def _create_test_db(self, verbosity=1, autoclobber=False, keepdb=False):
        TEST_NAME = self._test_database_name()
        TEST_USER = self._test_database_user()
        TEST_PASSWD = self._test_database_passwd()
        TEST_TBLSPACE = self._test_database_tblspace()
        TEST_TBLSPACE_TMP = self._test_database_tblspace_tmp()

        parameters = {
            'dbname': TEST_NAME,
            'user': TEST_USER,
            'password': TEST_PASSWD,
            'tblspace': TEST_TBLSPACE,
            'tblspace_temp': TEST_TBLSPACE_TMP,
        }

        cursor = self.connection.cursor()
        if self._test_database_create():
            try:
                self._execute_test_db_creation(cursor, parameters, verbosity, keepdb)
            except Exception as e:
                sys.stderr.write("Got an error creating the test database: %s\n" % e)
                if not autoclobber:
                    confirm = input("It appears the test database, %s, already exists. Type 'yes' to delete it, or 'no' to cancel: " % TEST_NAME)
                if autoclobber or confirm == 'yes':
                    try:
                        if verbosity >= 1:
                            print("Destroying old test database '%s'..." % self.connection.alias)
                        self._destroy_test_user(cursor, parameters, verbosity)
                        self._execute_test_db_destruction(cursor, parameters, verbosity)
                        self._execute_test_db_creation(cursor, parameters, verbosity, keepdb)
                    except Exception as e:
                        sys.stderr.write("Got an error recreating the test database: %s\n" % e)
                        sys.exit(2)
                else:
                    print("Tests cancelled.")
                    sys.exit(1)

        if self._test_user_create():
            if verbosity >= 1:
                print("Creating test user...")
            try:
                self._create_test_user(cursor, parameters, verbosity, keepdb)
            except Exception as e:
                sys.stderr.write("Got an error creating the test user: %s\n" % e)
                if not autoclobber:
                    confirm = input("It appears the test user, %s, already exists. Type 'yes' to delete it, or 'no' to cancel: " % TEST_USER)
                if autoclobber or confirm == 'yes':
                    try:
                        if verbosity >= 1:
                            print("Destroying old test user...")
                        self._destroy_test_user(cursor, parameters, verbosity)
                        if verbosity >= 1:
                            print("Creating test user...")
                        self._create_test_user(cursor, parameters, verbosity, keepdb)
                    except Exception as e:
                        sys.stderr.write("Got an error recreating the test user: %s\n" % e)
                        sys.exit(2)
                else:
                    print("Tests cancelled.")
                    sys.exit(1)

        self.connection.settings_dict['SAVED_USER'] = self.connection.settings_dict['USER']
        self.connection.settings_dict['SAVED_PASSWORD'] = self.connection.settings_dict['PASSWORD']
        self.connection.settings_dict['TEST_USER'] = self.connection.settings_dict['USER'] = TEST_USER
        self.connection.settings_dict['PASSWORD'] = TEST_PASSWD

        return self.connection.settings_dict['NAME']

    def _destroy_test_db(self, test_database_name, verbosity=1):
        """
        Destroy a test database, prompting the user for confirmation if the
        database already exists. Returns the name of the test database created.
        """
        TEST_NAME = self._test_database_name()
        TEST_USER = self._test_database_user()
        TEST_PASSWD = self._test_database_passwd()
        TEST_TBLSPACE = self._test_database_tblspace()
        TEST_TBLSPACE_TMP = self._test_database_tblspace_tmp()

        self.connection.settings_dict['USER'] = self.connection.settings_dict['SAVED_USER']
        self.connection.settings_dict['PASSWORD'] = self.connection.settings_dict['SAVED_PASSWORD']

        parameters = {
            'dbname': TEST_NAME,
            'user': TEST_USER,
            'password': TEST_PASSWD,
            'tblspace': TEST_TBLSPACE,
            'tblspace_temp': TEST_TBLSPACE_TMP,
        }

        cursor = self.connection.cursor()
        time.sleep(10) # To avoid "database is being accessed by other users" errors.
        if self._test_user_create():
            if verbosity >= 1:
                print('Destroying test user...')
            self._destroy_test_user(cursor, parameters, verbosity)
        time.sleep(10)
        if self._test_database_create():
            if verbosity >= 1:
                print('Destroying test database tables...')
            self._execute_test_db_destruction(cursor, parameters, verbosity)
        self.connection.close()

    def _execute_test_db_creation(self, cursor, parameters, verbosity, keepdb=False):
        if verbosity >= 2:
            print("_create_test_db(): dbname = %s" % parameters['dbname'])
        statements = [
            """CREATE TABLESPACE %(tblspace)s
               DATAFILE '%(tblspace)s.dbf' SIZE 128
               AUTOEXTEND ON NEXT 10
            """,
        ]
        self._execute_statements(cursor, statements, parameters, verbosity)

    def _create_test_user(self, cursor, parameters, verbosity, keepdb=False):
        if verbosity >= 2:
            print("_create_test_user(): username = %s" % parameters['user'])
        statements = [
            """CREATE USER %(user)s
               IDENTIFIED BY %(password)s
               DEFAULT TABLESPACE %(tblspace)s
            """,
            """GRANT CREATE SESSION,
                     CREATE TABLE,
                     CREATE SEQUENCE,
                     CREATE PROCEDURE,
                     CREATE TRIGGER,
                     CREATE INDEX,
                     CREATE VIEW,
                     CREATE MATERIALIZED VIEW
               TO %(user)s""",
        ]
        self._execute_statements(cursor, statements, parameters, verbosity)

    def _execute_test_db_destruction(self, cursor, parameters, verbosity):
        if verbosity >= 2:
            print("_execute_test_db_destruction(): dbname=%s" % parameters['dbname'])
        statements = [
            'DROP TABLESPACE if exists %(tblspace)s ',
            ]
        self._execute_statements(cursor, statements, parameters, verbosity)

    def _destroy_test_user(self, cursor, parameters, verbosity):
        if verbosity >= 2:
            print("_destroy_test_user(): user=%s" % parameters['user'])
            print("Be patient.  This can take some time...")
        statements = [
            'DROP USER %(user)s CASCADE',
        ]
        self._execute_statements(cursor, statements, parameters, verbosity)

    def _execute_statements(self, cursor, statements, parameters, verbosity):
        for template in statements:
            stmt = template % parameters
            if verbosity >= 2:
                print(stmt)
            try:
                cursor.execute(stmt)
            except Exception as err:
                sys.stderr.write("Failed (%s)\n" % (err))
                raise

    def _test_settings_get(self, key, default=None, prefixed=None):
        """
        Return a value from the test settings dict, or a given default, or a
        prefixed entry from the main settings dict.
        """
        settings_dict = self.connection.settings_dict
        val = settings_dict['TEST'].get(key, default)
        if val is None and prefixed:
            val = TEST_DATABASE_PREFIX + settings_dict[prefixed]
        return val

    def _test_database_name(self):
        return self._test_settings_get('NAME', prefixed='NAME')
    
    '''
    def _test_database_name(self):
        name = TEST_DATABASE_PREFIX + self.connection.settings_dict['NAME']
        try:
            if self.connection.settings_dict['TEST_NAME']:
                name = self.connection.settings_dict['TEST_NAME']
        except AttributeError:
            pass
        return name
    '''

    def _test_database_create(self):
        return self.connection.settings_dict.get('TEST_CREATE', True)

    def _test_user_create(self):
        return self.connection.settings_dict.get('TEST_USER_CREATE', True)

    def _test_database_user(self):
        name = TEST_DATABASE_PREFIX + self.connection.settings_dict['USER']
        try:
            if self.connection.settings_dict['TEST_USER']:
                name = self.connection.settings_dict['TEST_USER']
        except KeyError:
            pass
        return name

    def _test_database_passwd(self):
        name =  self._test_settings_get("PASSWORD")
        try:
            if self.connection.settings_dict['TEST_PASSWD']:
                name = self.connection.settings_dict['TEST_PASSWD']
        except KeyError:
            pass
        return name

    def _test_database_tblspace(self):
        name = TEST_DATABASE_PREFIX + self.connection.settings_dict['NAME']
        try:
            if self.connection.settings_dict['TEST_TBLSPACE']:
                name = self.connection.settings_dict['TEST_TBLSPACE']
        except KeyError:
            pass
        return name

    def _test_database_tblspace_tmp(self):
        name = TEST_DATABASE_PREFIX + self.connection.settings_dict['NAME'] + '_temp'
        try:
            if self.connection.settings_dict['TEST_TBLSPACE_TMP']:
                name = self.connection.settings_dict['TEST_TBLSPACE_TMP']
        except KeyError:
            pass
        return name

    def _get_test_db_name(self):

        return self.connection.settings_dict['NAME']

    def test_db_signature(self):
        settings_dict = self.connection.settings_dict
        return (
            settings_dict['HOST'],
            settings_dict['PORT'],
            settings_dict['ENGINE'],
            settings_dict['NAME'],
            self._test_database_user(),
        )

    def set_autocommit(self):
        self.connection.connection.autocommit = True
        
    def sql_create_model(self, model, style, known_models=set()):
        """
        Returns the SQL required to create a single model, as a tuple of:
            (list_of_sql, pending_references_dict)
        """
        opts = model._meta
        if not opts.managed or opts.proxy or opts.swapped:
            return [], {}
        final_output = []
        table_output = []
        pending_references = {}
        qn = self.connection.ops.quote_name
        for f in opts.local_fields:
            col_type = f.db_type(connection=self.connection)
            tablespace = f.db_tablespace or opts.db_tablespace
            if col_type is None:
                # Skip ManyToManyFields, because they're not represented as
                # database columns in this table.
                continue
            # Make the definition (e.g. 'foo VARCHAR(30)') for this field.
            field_output = [style.SQL_FIELD(qn(f.column)),
                style.SQL_COLTYPE(col_type)]

            null = f.null
            if (f.empty_strings_allowed and not f.primary_key and
                    self.connection.features.interprets_empty_strings_as_nulls):
                null = True
            if not null:
                field_output.append(style.SQL_KEYWORD('NOT NULL'))
            if f.primary_key:
                field_output.append(style.SQL_KEYWORD('PRIMARY KEY'))
            elif f.unique:
                field_output.append(style.SQL_KEYWORD('UNIQUE'))
            elif f.has_default():
                field_output.append(style.SQL_KEYWORD('DEFAULT'))
                field_output.append("'%s'" % f.get_default())
                
            if tablespace and f.unique:
                # We must specify the index tablespace inline, because we
                # won't be generating a CREATE INDEX statement for this field.
                tablespace_sql = self.connection.ops.tablespace_sql(
                    tablespace, inline=True)
                if tablespace_sql:
                    field_output.append(tablespace_sql)
            if f.rel:
                ref_output, pending = self.sql_for_inline_foreign_key_references(
                    f, known_models, style)
                if pending:
                    pending_references.setdefault(f.rel.to, []).append(
                        (model, f))
                else:
                    field_output.extend(ref_output)
            table_output.append(' '.join(field_output))
        for field_constraints in opts.unique_together:
            table_output.append(style.SQL_KEYWORD('UNIQUE') + ' (%s)' %
                ", ".join(
                    [style.SQL_FIELD(qn(opts.get_field(f).column))
                     for f in field_constraints]))

        full_statement = [style.SQL_KEYWORD('CREATE TABLE') + ' ' +
                          style.SQL_TABLE(qn(opts.db_table)) + ' (']
        for i, line in enumerate(table_output):  # Combine and add commas.
            full_statement.append(
                '    %s%s' % (line, i < len(table_output) - 1 and ',' or ''))
        full_statement.append(')')
        if opts.db_tablespace:
            tablespace_sql = self.connection.ops.tablespace_sql(
                opts.db_tablespace)
            if tablespace_sql:
                full_statement.append(tablespace_sql)
        full_statement.append(';')
        final_output.append('\n'.join(full_statement))

        if opts.has_auto_field:
            # Add any extra SQL needed to support auto-incrementing primary
            # keys.
            auto_column = opts.auto_field.db_column or opts.auto_field.name
            autoinc_sql = self.connection.ops.autoinc_sql(opts.db_table,
                                                          auto_column)
            if autoinc_sql:
                for stmt in autoinc_sql:
                    final_output.append(stmt)

        return final_output, pending_references
