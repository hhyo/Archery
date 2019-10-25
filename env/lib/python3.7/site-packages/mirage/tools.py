from django.apps import apps as installed_apps
from django.db import connections, router
from tqdm import tqdm

from .crypto import Crypto


class Migrator:
    def __init__(self, app, model, field, key=None, tofield=None):
        self.app = app
        self.model = model.lower()
        self.field = field.lower()
        self.crypto = Crypto(key)
        self.tofield = tofield

    def encrypt(self, apps=None, schema_editor=None, offset=0, total=None, limit=1000):
        return self.executor(apps, schema_editor, offset, total, limit, method='encrypt')

    def decrypt(self, apps=None, schema_editor=None, offset=0, total=None, limit=1000):
        return self.executor(apps, schema_editor, offset, total, limit, method='decrypt')

    def copy(self, apps=None, schema_editor=None, offset=0, total=None, limit=1000):
        return self.executor(apps, schema_editor, offset, total, limit, method='copy')

    def encrypt_to(self, apps=None, schema_editor=None, offset=0, total=None, limit=1000):
        return self.executor(apps, schema_editor, offset, total, limit, method='encrypt_to')

    def decrypt_to(self, apps=None, schema_editor=None, offset=0, total=None, limit=1000):
        return self.executor(apps, schema_editor, offset, total, limit, method='decrypt_to')

    def executor(self, apps=None, schema_editor=None, offset=0, total=None, limit=1000, method=None):
        if not method:
            return

        if not apps:
            apps = installed_apps
        model = apps.get_model(self.app, self.model)
        if not schema_editor:
            db_alias = router.db_for_write(model=model)
        else:
            db_alias = schema_editor.connection.alias
        db_table = model._meta.db_table if model._meta.db_table else f"{self.app}_{self.model}"
        if not total:
            total = model.objects.using(db_alias).latest("id").id
        if limit > total:
            limit = total

        t = tqdm(total=total-offset)
        while offset < total:
            value_list = []
            with connections[db_alias].cursor() as cursor:
                cursor.execute(f"select id, {self.field} from {db_table} where id>{offset} order by id limit {limit};")
                for query in cursor.fetchall():
                    if method in ['encrypt', 'encrypt_to']:
                        value_list.append([query[0], self.crypto.encrypt(query[1])])
                    elif method in ['decrypt', 'decrypt_to']:
                        text = self.crypto.decrypt(query[1]) or ''
                        value_list.append([query[0], text.replace("'", "''")])
                    elif method == 'copy':
                        text = query[1] or ''
                        value_list.append([query[0], text.replace("'", "''")])
                execute_sql = ''
                for value in value_list:
                    if method in ['encrypt', 'decrypt']:
                        execute_sql += f"update {db_table} set {self.field}='{value[1]}' where id={value[0]};"
                    elif method in ['copy', 'encrypt_to', 'decrypt_to']:
                        execute_sql += f"update {db_table} set {self.tofield}='{value[1]}' where id={value[0]};"
                cursor.execute(execute_sql)
            if value_list:
                t.update(value_list[-1][0] - offset)
                offset = value_list[-1][0]
        t.close()
