import sys

if sys.version_info[0] == 3:
    PY2 = False
    unicode = str
    unichr = chr
    long = int
else:
    PY2 = True
    unicode = unicode
    unichr = unichr
    long = long
