"""Compatibility wrappers for Py2/Py3."""

import sys
import os

if sys.version_info[0] < 3:
    from UserDict import UserDict, IterableUserDict
    from urllib import quote
    from urllib import quote_plus
    from urllib import unquote as urllib_unquote
    from urllib import urlopen
    from urlparse import urlparse

    def unquote(uri):
        """Specialized unquote that uses UTF-8 for parsing."""
        uri = uri.encode('ascii')
        unquoted = urllib_unquote(uri)
        return unquoted.decode('utf-8')

    # Old-style of re-raising an exception is SyntaxError in Python 3,
    # so hide behind exec() so the Python 3 parser doesn't see it
    exec('''def reraise(exc_type, exc_value, exc_traceback):
        """Re-raise an exception given information from sys.exc_info()

        Note that unlike six.reraise, this does not support replacing the
        traceback. All arguments must come from a single sys.exc_info() call.
        """
        raise exc_type, exc_value, exc_traceback
    ''')

else:
    from collections import UserDict
    IterableUserDict = UserDict
    from urllib.parse import quote, quote_plus, unquote, urlparse
    from urllib.request import urlopen

    def reraise(exc_type, exc_value, exc_traceback):
        """Re-raise an exception given information from sys.exc_info()

        Note that unlike six.reraise, this does not support replacing the
        traceback. All arguments must come from a single sys.exc_info() call.
        """
        # In Python 3, all exception info is contained in one object.
        raise exc_value

try:
    from shutil import which
except ImportError:
    # shutil.which() from Python 3.6
    # "Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
    # 2011, 2012, 2013, 2014, 2015, 2016, 2017 Python Software Foundation;
    # All Rights Reserved"
    def which(cmd, mode=os.F_OK | os.X_OK, path=None):
        """Given a command, mode, and a PATH string, return the path which
        conforms to the given mode on the PATH, or None if there is no such
        file.

        `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
        of os.environ.get("PATH"), or can be overridden with a custom search
        path.

        """
        # Check that a given file can be accessed with the correct mode.
        # Additionally check that `file` is not a directory, as on Windows
        # directories pass the os.access check.
        def _access_check(fn, mode):
            return (os.path.exists(fn) and os.access(fn, mode)
                    and not os.path.isdir(fn))

        # If we're given a path with a directory part, look it up directly rather
        # than referring to PATH directories. This includes checking relative to the
        # current directory, e.g. ./script
        if os.path.dirname(cmd):
            if _access_check(cmd, mode):
                return cmd
            return None

        if path is None:
            path = os.environ.get("PATH", os.defpath)
        if not path:
            return None
        path = path.split(os.pathsep)

        if sys.platform == "win32":
            # The current directory takes precedence on Windows.
            if not os.curdir in path:
                path.insert(0, os.curdir)

            # PATHEXT is necessary to check on Windows.
            pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
            # See if the given file matches any of the expected path extensions.
            # This will allow us to short circuit when given "python.exe".
            # If it does match, only test that one, otherwise we have to try
            # others.
            if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
                files = [cmd]
            else:
                files = [cmd + ext for ext in pathext]
        else:
            # On other platforms you don't have things like PATHEXT to tell you
            # what file suffixes are executable, so just pass on cmd as-is.
            files = [cmd]

        seen = set()
        for dir in path:
            normdir = os.path.normcase(dir)
            if not normdir in seen:
                seen.add(normdir)
                for thefile in files:
                    name = os.path.join(dir, thefile)
                    if _access_check(name, mode):
                        return name
        return None
