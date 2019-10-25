from typing import Union, Any, Optional, IO

Buffer = Union[bytes, bytearray, memoryview]

import sys

def b(s: str) -> bytes: ...
def bchr(s: int) -> bytes: ...
def bord(s: bytes) -> int: ...
def tobytes(s: Union[bytes, str]) -> bytes: ...
def tostr(b: bytes) -> str: ...
def bytestring(x: Any) -> bool: ...

def is_native_int(s: Any) -> bool: ...
def is_string(x: Any) -> bool: ...

def BytesIO(b: bytes) -> IO[bytes]: ...

if sys.version_info[0] == 2:
    from sys import maxint
    iter_range = xrange

    if sys.version_info[1] < 7:
        import types
        _memoryview = types.NoneType
    else:
        _memoryview = memoryview

else:
    from sys import maxsize as maxint
    iter_range = range

    _memoryview = memoryview

def _copy_bytes(start: Optional[int], end: Optional[int], seq: Buffer) -> bytes: ...
