"""
A thin, practical wrapper around terminal capabilities in Python.

http://pypi.python.org/pypi/blessed
"""
# std imports
import platform as _platform

# local
from blessed.terminal import Terminal

if ('3', '0', '0') <= _platform.python_version_tuple() < ('3', '2', '2+'):
    # Good till 3.2.10
    # Python 3.x < 3.2.3 has a bug in which tparm() erroneously takes a string.
    raise ImportError('Blessed needs Python 3.2.3 or greater for Python 3 '
                      'support due to http://bugs.python.org/issue10570.')

__all__ = ('Terminal',)
__version__ = '1.15.0'
