import datetime

from django.utils.encoding import force_bytes, force_text

from .base import Database

if int(Database.version.split('.', 1)[0]) >= 5 and \
        (int(Database.version.split('.', 2)[1]) >= 1 or
         not hasattr(Database, 'UNICODE')):
    convert_unicode = force_text
else:
    convert_unicode = force_bytes


class InsertIdVar(object):
    """
    A late-binding cursor variable that can be passed to Cursor.execute
    as a parameter, in order to receive the id of the row created by an
    insert statement.
    """

    def bind_parameter(self, cursor):
        param = cursor.cursor.var(Database.NUMBER)
        cursor._insert_id_var = param
        return param
