import sys
from aliyunsdkcore.vendored import six

if six.PY2:
    from base64 import encodestring as b64_encode_bytes
    from base64 import decodestring as b64_decode_bytes

    def ensure_bytes(s, encoding='utf-8', errors='strict'):
        if isinstance(s, unicode):
            return s.encode(encoding, errors)
        if isinstance(s, str):
            return s
        raise ValueError("Expected str or unicode, received %s." % type(s))

    def ensure_string(s, encoding='utf-8', errors='strict'):
        if isinstance(s, unicode):
            return s.encode(encoding, errors)
        if isinstance(s, str):
            return s
        raise ValueError("Expected str or unicode, received %s." % type(s))

else:
    from base64 import encodebytes as b64_encode_bytes
    from base64 import decodebytes as b64_decode_bytes

    def ensure_bytes(s, encoding='utf-8', errors='strict'):
        if isinstance(s, str):
            return bytes(s, encoding=encoding)
        if isinstance(s, bytes):
            return s
        if isinstance(s, bytearray):
            return bytes(s)
        raise ValueError(
            "Expected str or bytes or bytearray, received %s." %
            type(s))

    def ensure_string(s, encoding='utf-8', errors='strict'):
        if isinstance(s, str):
            return s
        if isinstance(s, (bytes, bytearray)):
            return str(s, encoding='utf-8')
        raise ValueError(
            "Expected str or bytes or bytearray, received %s." %
            type(s))
