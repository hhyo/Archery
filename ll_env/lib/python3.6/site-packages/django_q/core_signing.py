from __future__ import unicode_literals

import datetime
import time
import zlib

from django.core.signing import BadSignature, SignatureExpired, b64_decode, JSONSerializer, \
    Signer as Sgnr, TimestampSigner as TsS, dumps
from django.utils import baseconv
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_bytes, force_str, force_text

dumps = dumps

"""
The loads function is the same as the `django.core.signing.loads` function
The difference is that `this` loads function calls `TimestampSigner` and `Signer`
"""


def loads(s, key=None, salt='django.core.signing', serializer=JSONSerializer, max_age=None):
    """
    Reverse of dumps(), raise BadSignature if signature fails.

    The serializer is expected to accept a bytestring.
    """
    # TimestampSigner.unsign() returns str but base64 and zlib compression
    # operate on bytes.
    base64d = force_bytes(TimestampSigner(key, salt=salt).unsign(s, max_age=max_age))
    decompress = False
    if base64d[:1] == b'.':
        # It's compressed; uncompress it first
        base64d = base64d[1:]
        decompress = True
    data = b64_decode(base64d)
    if decompress:
        data = zlib.decompress(data)
    return serializer().loads(data)


class Signer(Sgnr):

    def unsign(self, signed_value):
        # force_str is removed in Django 2.0
        signed_value = force_str(signed_value)
        if self.sep not in signed_value:
            raise BadSignature('No "%s" found in value' % self.sep)
        value, sig = signed_value.rsplit(self.sep, 1)
        if constant_time_compare(sig, self.signature(value)):
            # force_text is removed in Django 2.0
            return force_text(value)
        raise BadSignature('Signature "%s" does not match' % sig)


"""
TimestampSigner is also the same as `django.core.signing.TimestampSigner` but is
calling `this` Signer.
"""


class TimestampSigner(Signer, TsS):

    def unsign(self, value, max_age=None):
        """
        Retrieve original value and check it wasn't signed more
        than max_age seconds ago.
        """
        result = super(TimestampSigner, self).unsign(value)
        value, timestamp = result.rsplit(self.sep, 1)
        timestamp = baseconv.base62.decode(timestamp)
        if max_age is not None:
            if isinstance(max_age, datetime.timedelta):
                max_age = max_age.total_seconds()
            # Check timestamp is not older than max_age
            age = time.time() - timestamp
            if age > max_age:
                raise SignatureExpired(
                    'Signature age %s > %s seconds' % (age, max_age))
        return value
