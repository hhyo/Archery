# encoding: utf-8
"""Module containing :class:`Terminal`, the primary API entry point."""
# pylint: disable=too-many-lines
#         Too many lines in module (1027/1000)
import codecs
import collections
import contextlib
import curses
import functools
import io
import locale
import os
import select
import struct
import sys
import time
import warnings
import re

try:
    import termios
    import fcntl
    import tty
    HAS_TTY = True
except ImportError:
    _TTY_METHODS = ('setraw', 'cbreak', 'kbhit', 'height', 'width')
    _MSG_NOSUPPORT = (
        "One or more of the modules: 'termios', 'fcntl', and 'tty' "
        "are not found on your platform '{0}'. The following methods "
        "of Terminal are dummy/no-op unless a deriving class overrides "
        "them: {1}".format(sys.platform.lower(), ', '.join(_TTY_METHODS)))
    warnings.warn(_MSG_NOSUPPORT)
    HAS_TTY = False

try:
    InterruptedError
except NameError:
    # alias py2 exception to py3
    # pylint: disable=redefined-builtin
    InterruptedError = select.error

try:
    from collections import OrderedDict
except ImportError:
    # python 2.6 requires 3rd party library (backport)
    #
    # pylint: disable=import-error
    #         Unable to import 'ordereddict'
    from ordereddict import OrderedDict

# local imports
from .formatters import (ParameterizingString,
                         NullCallableString,
                         resolve_capability,
                         resolve_attribute,
                         )

from ._capabilities import (
    CAPABILITIES_RAW_MIXIN,
    CAPABILITIES_ADDITIVES,
    CAPABILITY_DATABASE,
)

from .sequences import (SequenceTextWrapper,
                        Sequence,
                        Termcap,
                        )

from .keyboard import (get_keyboard_sequences,
                       get_leading_prefixes,
                       get_keyboard_codes,
                       resolve_sequence,
                       _read_until,
                       _time_left,
                       )


_CUR_TERM = None  # See comments at end of file


class Terminal(object):
    """
    An abstraction for color, style, positioning, and input in the terminal.

    This keeps the endless calls to ``tigetstr()`` and ``tparm()`` out of your
    code, acts intelligently when somebody pipes your output to a non-terminal,
    and abstracts over the complexity of unbuffered keyboard input. It uses the
    terminfo database to remain portable across terminal types.
    """
    # pylint: disable=too-many-instance-attributes,too-many-public-methods
    #         Too many public methods (28/20)
    #         Too many instance attributes (12/7)

    #: Sugary names for commonly-used capabilities
    _sugar = dict(
        save='sc',
        restore='rc',
        # 'clear' clears the whole screen.
        clear_eol='el',
        clear_bol='el1',
        clear_eos='ed',
        position='cup',  # deprecated
        enter_fullscreen='smcup',
        exit_fullscreen='rmcup',
        move='cup',
        move_x='hpa',
        move_y='vpa',
        move_left='cub1',
        move_right='cuf1',
        move_up='cuu1',
        move_down='cud1',
        hide_cursor='civis',
        normal_cursor='cnorm',
        reset_colors='op',  # oc doesn't work on my OS X terminal.
        normal='sgr0',
        reverse='rev',
        italic='sitm',
        no_italic='ritm',
        shadow='sshm',
        no_shadow='rshm',
        standout='smso',
        no_standout='rmso',
        subscript='ssubm',
        no_subscript='rsubm',
        superscript='ssupm',
        no_superscript='rsupm',
        underline='smul',
        no_underline='rmul',
        cursor_report='u6',
        cursor_request='u7',
        terminal_answerback='u8',
        terminal_enquire='u9',
    )

    def __init__(self, kind=None, stream=None, force_styling=False):
        """
        Initialize the terminal.

        :arg str kind: A terminal string as taken by :func:`curses.setupterm`.
            Defaults to the value of the ``TERM`` environment variable.

            .. note:: Terminals withing a single process must share a common
                ``kind``. See :obj:`_CUR_TERM`.

        :arg file stream: A file-like object representing the Terminal output.
            Defaults to the original value of :obj:`sys.__stdout__`, like
            :func:`curses.initscr` does.

            If ``stream`` is not a tty, empty Unicode strings are returned for
            all capability values, so things like piping your program output to
            a pipe or file does not emit terminal sequences.

        :arg bool force_styling: Whether to force the emission of capabilities
            even if :obj:`sys.__stdout__` does not seem to be connected to a
            terminal. If you want to force styling to not happen, use
            ``force_styling=None``.

            This comes in handy if users are trying to pipe your output through
            something like ``less -r`` or build systems which support decoding
            of terminal sequences.
        """
        # pylint: disable=global-statement,too-many-branches
        global _CUR_TERM
        self._keyboard_fd = None

        # Default stream is stdout, keyboard valid as stdin only when
        # output stream is stdout or stderr and is a tty.
        if stream is None:
            stream = sys.__stdout__
        if stream in (sys.__stdout__, sys.__stderr__):
            self._keyboard_fd = sys.__stdin__.fileno()

        # we assume our input stream to be line-buffered until either the
        # cbreak of raw context manager methods are entered with an
        # attached tty.
        self._line_buffered = True

        try:
            stream_fd = (stream.fileno() if hasattr(stream, 'fileno') and
                         callable(stream.fileno) else None)
        except io.UnsupportedOperation:
            stream_fd = None

        self._stream = stream
        self._is_a_tty = stream_fd is not None and os.isatty(stream_fd)
        self._does_styling = ((self.is_a_tty or force_styling) and
                              force_styling is not None)

        # _keyboard_fd only non-None if both stdin and stdout is a tty.
        self._keyboard_fd = (self._keyboard_fd
                             if self._keyboard_fd is not None and
                             self.is_a_tty and os.isatty(self._keyboard_fd)
                             else None)
        self._normal = None  # cache normal attr, preventing recursive lookups

        # The descriptor to direct terminal initialization sequences to.
        self._init_descriptor = (sys.__stdout__.fileno() if stream_fd is None
                                 else stream_fd)
        self._kind = kind or os.environ.get('TERM', 'unknown')

        if self.does_styling:
            # Initialize curses (call setupterm).
            #
            # Make things like tigetstr() work. Explicit args make setupterm()
            # work even when -s is passed to nosetests. Lean toward sending
            # init sequences to the stream if it has a file descriptor, and
            # send them to stdout as a fallback, since they have to go
            # somewhere.
            try:
                curses.setupterm(self._kind, self._init_descriptor)
            except curses.error as err:
                warnings.warn('Failed to setupterm(kind={0!r}): {1}'
                              .format(self._kind, err))
                self._kind = None
                self._does_styling = False
            else:
                if _CUR_TERM is None or self._kind == _CUR_TERM:
                    _CUR_TERM = self._kind
                else:
                    warnings.warn(
                        'A terminal of kind "%s" has been requested; due to an'
                        ' internal python curses bug, terminal capabilities'
                        ' for a terminal of kind "%s" will continue to be'
                        ' returned for the remainder of this process.' % (
                            self._kind, _CUR_TERM,))

        # initialize capabilities and terminal keycodes database
        self.__init__capabilities()
        self.__init__keycodes()

    def __init__capabilities(self):
        # important that we lay these in their ordered direction, so that our
        # preferred, 'color' over 'set_a_attributes1', for example.
        self.caps = OrderedDict()

        # some static injected patterns, esp. without named attribute access.
        for name, (attribute, pattern) in CAPABILITIES_ADDITIVES.items():
            self.caps[name] = Termcap(name, pattern, attribute)

        for name, (attribute, kwds) in CAPABILITY_DATABASE.items():
            if self.does_styling:
                # attempt dynamic lookup
                cap = getattr(self, attribute)
                if cap:
                    self.caps[name] = Termcap.build(
                        name, cap, attribute, **kwds)
                    continue

            # fall-back
            pattern = CAPABILITIES_RAW_MIXIN.get(name)
            if pattern:
                self.caps[name] = Termcap(name, pattern, attribute)

        # make a compiled named regular expression table
        self.caps_compiled = re.compile(
            '|'.join(cap.pattern for name, cap in self.caps.items()))

        # for tokenizer, the '.lastgroup' is the primary lookup key for
        # 'self.caps', unless 'MISMATCH'; then it is an unmatched character.
        self._caps_compiled_any = re.compile('|'.join(
            cap.named_pattern for name, cap in self.caps.items()
        ) + '|(?P<MISMATCH>.)')
        self._caps_unnamed_any = re.compile('|'.join(
            '({0})'.format(cap.pattern) for name, cap in self.caps.items()
        ) + '|(.)')

    def __init__keycodes(self):
        # Initialize keyboard data determined by capability.
        # Build database of int code <=> KEY_NAME.
        self._keycodes = get_keyboard_codes()

        # Store attributes as: self.KEY_NAME = code.
        for key_code, key_name in self._keycodes.items():
            setattr(self, key_name, key_code)

        # Build database of sequence <=> KEY_NAME.
        self._keymap = get_keyboard_sequences(self)

        # build set of prefixes of sequences
        self._keymap_prefixes = get_leading_prefixes(self._keymap)

        # keyboard stream buffer
        self._keyboard_buf = collections.deque()

        if self._keyboard_fd is not None:
            # set input encoding and initialize incremental decoder
            locale.setlocale(locale.LC_ALL, '')
            self._encoding = locale.getpreferredencoding() or 'ascii'

            try:
                self._keyboard_decoder = codecs.getincrementaldecoder(
                    self._encoding)()

            except LookupError as err:
                # encoding is illegal or unsupported, use 'ascii'
                warnings.warn('LookupError: {0}, fallback to ASCII for '
                              'keyboard.'.format(err))
                self._encoding = 'ascii'
                self._keyboard_decoder = codecs.getincrementaldecoder(
                    self._encoding)()

    def __getattr__(self, attr):
        r"""
        Return a terminal capability as Unicode string.

        For example, ``term.bold`` is a unicode string that may be prepended
        to text to set the video attribute for bold, which should also be
        terminated with the pairing :attr:`normal`. This capability
        returns a callable, so you can use ``term.bold("hi")`` which
        results in the joining of ``(term.bold, "hi", term.normal)``.

        Compound formatters may also be used. For example::

            >>> term.bold_blink_red_on_green("merry x-mas!")

        For a parametrized capability such as ``move`` (or ``cup``), pass the
        parameters as positional arguments::

            >>> term.move(line, column)

        See the manual page `terminfo(5)
        <http://invisible-island.net/ncurses/man/terminfo.5.html>`_ for a
        complete list of capabilities and their arguments.
        """
        if not self.does_styling:
            return NullCallableString()
        val = resolve_attribute(self, attr)
        # Cache capability resolution: note this will prevent this
        # __getattr__ method for being called again.  That's the idea!
        setattr(self, attr, val)
        return val

    @property
    def kind(self):
        """
        Read-only property: Terminal kind determined on class initialization.

        :rtype: str
        """
        return self._kind

    @property
    def does_styling(self):
        """
        Read-only property: Whether this class instance may emit sequences.

        :rtype: bool
        """
        return self._does_styling

    @property
    def is_a_tty(self):
        """
        Read-only property: Whether :attr:`~.stream` is a terminal.

        :rtype: bool
        """
        return self._is_a_tty

    @property
    def height(self):
        """
        Read-only property: Height of the terminal (in number of lines).

        :rtype: int
        """
        return self._height_and_width().ws_row

    @property
    def width(self):
        """
        Read-only property: Width of the terminal (in number of columns).

        :rtype: int
        """
        return self._height_and_width().ws_col

    @staticmethod
    def _winsize(fd):
        """
        Return named tuple describing size of the terminal by ``fd``.

        If the given platform does not have modules :mod:`termios`,
        :mod:`fcntl`, or :mod:`tty`, window size of 80 columns by 25
        rows is always returned.

        :arg int fd: file descriptor queries for its window size.
        :raises IOError: the file descriptor ``fd`` is not a terminal.
        :rtype: WINSZ

        WINSZ is a :class:`collections.namedtuple` instance, whose structure
        directly maps to the return value of the :const:`termios.TIOCGWINSZ`
        ioctl return value. The return parameters are:

            - ``ws_row``: width of terminal by its number of character cells.
            - ``ws_col``: height of terminal by its number of character cells.
            - ``ws_xpixel``: width of terminal by pixels (not accurate).
            - ``ws_ypixel``: height of terminal by pixels (not accurate).
        """
        if HAS_TTY:
            data = fcntl.ioctl(fd, termios.TIOCGWINSZ, WINSZ._BUF)
            return WINSZ(*struct.unpack(WINSZ._FMT, data))
        return WINSZ(ws_row=25, ws_col=80, ws_xpixel=0, ws_ypixel=0)

    def _height_and_width(self):
        """
        Return a tuple of (terminal height, terminal width).

        If :attr:`stream` or :obj:`sys.__stdout__` is not a tty or does not
        support :func:`fcntl.ioctl` of :const:`termios.TIOCGWINSZ`, a window
        size of 80 columns by 25 rows is returned for any values not
        represented by environment variables ``LINES`` and ``COLUMNS``, which
        is the default text mode of IBM PC compatibles.

        :rtype: WINSZ

        WINSZ is a :class:`collections.namedtuple` instance, whose structure
        directly maps to the return value of the :const:`termios.TIOCGWINSZ`
        ioctl return value. The return parameters are:

            - ``ws_row``: width of terminal by its number of character cells.
            - ``ws_col``: height of terminal by its number of character cells.
            - ``ws_xpixel``: width of terminal by pixels (not accurate).
            - ``ws_ypixel``: height of terminal by pixels (not accurate).

        """
        for fd in (self._init_descriptor, sys.__stdout__):
            try:
                if fd is not None:
                    return self._winsize(fd)
            except IOError:
                pass

        return WINSZ(ws_row=int(os.getenv('LINES', '25')),
                     ws_col=int(os.getenv('COLUMNS', '80')),
                     ws_xpixel=None,
                     ws_ypixel=None)

    @contextlib.contextmanager
    def location(self, x=None, y=None):
        """
        Context manager for temporarily moving the cursor.

        Move the cursor to a certain position on entry, let you print stuff
        there, then return the cursor to its original position::

            term = Terminal()
            with term.location(2, 5):
                for x in xrange(10):
                    print('I can do it %i times!' % x)
            print('We're back to the original location.')

        Specify ``x`` to move to a certain column, ``y`` to move to a certain
        row, both, or neither. If you specify neither, only the saving and
        restoration of cursor position will happen. This can be useful if you
        simply want to restore your place after doing some manual cursor
        movement.

        .. note:: The store- and restore-cursor capabilities used internally
            provide no stack. This means that :meth:`location` calls cannot be
            nested: only one should be entered at a time.
        """
        # pylint: disable=invalid-name
        #         Invalid argument name "x"

        # Save position and move to the requested column, row, or both:
        self.stream.write(self.save)
        if x is not None and y is not None:
            self.stream.write(self.move(y, x))
        elif x is not None:
            self.stream.write(self.move_x(x))
        elif y is not None:
            self.stream.write(self.move_y(y))
        try:
            self.stream.flush()
            yield
        finally:
            # Restore original cursor position:
            self.stream.write(self.restore)
            self.stream.flush()

    def get_location(self, timeout=None):
        r"""
        Return tuple (row, column) of cursor position.

        :arg float timeout: Return after time elapsed in seconds with value
            ``(-1, -1)`` indicating that the remote end did not respond.
        :rtype: tuple
        :returns: cursor position as tuple in form of (row, column).

        The location of the cursor is determined by emitting the ``u7``
        terminal capability, or VT100 `Query Cursor Position
        <http://www.termsys.demon.co.uk/vtansi.htm#status>`_ when such
        capability is undefined, which elicits a response from a reply string
        described by capability ``u6``, or again VT100's definition of
        ``\x1b[%i%d;%dR`` when undefined.

        The ``(row, col)`` return value matches the parameter order of the
        ``move`` capability, so that the following sequence should cause the
        cursor to not move at all::

            >>> term = Terminal()
            >>> term.move(*term.get_location()))

        .. warning:: You might first test that a terminal is capable of
           informing you of its location, while using a timeout, before
           later calling.  When a timeout is specified, always ensure the
           return value is conditionally checked for ``(-1, -1)``.
        """
        # Local lines attached by termios and remote login protocols such as
        # ssh and telnet both provide a means to determine the window
        # dimensions of a connected client, but **no means to determine the
        # location of the cursor**.
        #
        # from http://invisible-island.net/ncurses/terminfo.src.html,
        #
        # > The System V Release 4 and XPG4 terminfo format defines ten string
        # > capabilities for use by applications, <u0>...<u9>.   In this file,
        # > we use certain of these capabilities to describe functions which
        # > are not covered by terminfo.  The mapping is as follows:
        # >
        # >  u9   terminal enquire string (equiv. to ANSI/ECMA-48 DA)
        # >  u8   terminal answerback description
        # >  u7   cursor position request (equiv. to VT100/ANSI/ECMA-48 DSR 6)
        # >  u6   cursor position report (equiv. to ANSI/ECMA-48 CPR)
        query_str = self.u7 or u'\x1b[6n'

        # determine response format as a regular expression
        response_re = self.caps['cursor_report'].re_compiled

        # Avoid changing user's desired raw or cbreak mode if already entered,
        # by entering cbreak mode ourselves.  This is necessary to receive user
        # input without awaiting a human to press the return key.   This mode
        # also disables echo, which we should also hide, as our input is an
        # sequence that is not meaningful for display as an output sequence.

        ctx = None
        try:
            if self._line_buffered:
                ctx = self.cbreak()
                ctx.__enter__()

            # emit the 'query cursor position' sequence,
            self.stream.write(query_str)
            self.stream.flush()

            # expect a response,
            match, data = _read_until(term=self,
                                      pattern=response_re,
                                      timeout=timeout)

            # ensure response sequence is excluded from subsequent input,
            if match:
                data = (data[:match.start()] + data[match.end():])

            # re-buffer keyboard data, if any
            self.ungetch(data)

            if match:
                # return matching sequence response, the cursor location.
                row, col = match.groups()
                return int(row), int(col)

        finally:
            if ctx is not None:
                ctx.__exit__(None, None, None)

        # We chose to return an illegal value rather than an exception,
        # favoring that users author function filters, such as max(0, y),
        # rather than crowbarring such logic into an exception handler.
        return -1, -1

    @contextlib.contextmanager
    def fullscreen(self):
        """
        Context manager that switches to secondary screen, restoring on exit.

        Under the hood, this switches between the primary screen buffer and
        the secondary one. The primary one is saved on entry and restored on
        exit.  Likewise, the secondary contents are also stable and are
        faithfully restored on the next entry::

            with term.fullscreen():
                main()

        .. note:: There is only one primary and one secondary screen buffer.
           :meth:`fullscreen` calls cannot be nested, only one should be
           entered at a time.
        """
        self.stream.write(self.enter_fullscreen)
        try:
            yield
        finally:
            self.stream.write(self.exit_fullscreen)

    @contextlib.contextmanager
    def hidden_cursor(self):
        """
        Context manager that hides the cursor, setting visibility on exit.

            with term.hidden_cursor():
                main()

        .. note:: :meth:`hidden_cursor` calls cannot be nested: only one
            should be entered at a time.
        """
        self.stream.write(self.hide_cursor)
        try:
            yield
        finally:
            self.stream.write(self.normal_cursor)

    @property
    def color(self):
        """
        A callable string that sets the foreground color.

        :arg int num: The foreground color index. This should be within the
           bounds of :attr:`~.number_of_colors`.
        :rtype: ParameterizingString

        The capability is unparameterized until called and passed a number,
        0-15, at which point it returns another string which represents a
        specific color change. This second string can further be called to
        color a piece of text and set everything back to normal afterward.
        """
        if not self.does_styling:
            return NullCallableString()
        return ParameterizingString(self._foreground_color,
                                    self.normal, 'color')

    @property
    def on_color(self):
        """
        A callable capability that sets the background color.

        :arg int num: The background color index.
        :rtype: ParameterizingString
        """
        if not self.does_styling:
            return NullCallableString()
        return ParameterizingString(self._background_color,
                                    self.normal, 'on_color')

    @property
    def normal(self):
        """
        A capability that resets all video attributes.

        :rtype: str

        ``normal`` is an alias for ``sgr0`` or ``exit_attribute_mode``. Any
        styling attributes previously applied, such as foreground or
        background colors, reverse video, or bold are reset to defaults.
        """
        if self._normal:
            return self._normal
        self._normal = resolve_capability(self, 'normal')
        return self._normal

    @property
    def stream(self):
        """
        Read-only property: stream the terminal outputs to.

        This is a convenience attribute. It is used internally for implied
        writes performed by context managers :meth:`~.hidden_cursor`,
        :meth:`~.fullscreen`, :meth:`~.location`, and :meth:`~.keypad`.
        """
        return self._stream

    @property
    def number_of_colors(self):
        """
        Read-only property: number of colors supported by terminal.

        Common values are 0, 8, 16, 88, and 256.

        Most commonly, this may be used to test whether the terminal supports
        colors. Though the underlying capability returns -1 when there is no
        color support, we return 0. This lets you test more Pythonically::

            if term.number_of_colors:
                ...
        """
        # This is actually the only remotely useful numeric capability. We
        # don't name it after the underlying capability, because we deviate
        # slightly from its behavior, and we might someday wish to give direct
        # access to it.

        # trim value to 0, as tigetnum('colors') returns -1 if no support,
        # and -2 if no such capability.
        return max(0, self.does_styling and curses.tigetnum('colors') or -1)

    @property
    def _foreground_color(self):
        """
        Convenience capability to support :attr:`~.on_color`.

        Prefers returning sequence for capability ``setaf``, "Set foreground
        color to #1, using ANSI escape". If the given terminal does not
        support such sequence, fallback to returning attribute ``setf``,
        "Set foreground color #1".
        """
        return self.setaf or self.setf

    @property
    def _background_color(self):
        """
        Convenience capability to support :attr:`~.on_color`.

        Prefers returning sequence for capability ``setab``, "Set background
        color to #1, using ANSI escape". If the given terminal does not
        support such sequence, fallback to returning attribute ``setb``,
        "Set background color #1".
        """
        return self.setab or self.setb

    def ljust(self, text, width=None, fillchar=u' '):
        """
        Left-align ``text``, which may contain terminal sequences.

        :arg str text: String to be aligned
        :arg int width: Total width to fill with aligned text. If
            unspecified, the whole width of the terminal is filled.
        :arg str fillchar: String for padding the right of ``text``
        :rtype: str
        """
        # Left justification is different from left alignment, but we continue
        # the vocabulary error of the str method for polymorphism.
        if width is None:
            width = self.width
        return Sequence(text, self).ljust(width, fillchar)

    def rjust(self, text, width=None, fillchar=u' '):
        """
        Right-align ``text``, which may contain terminal sequences.

        :arg str text: String to be aligned
        :arg int width: Total width to fill with aligned text. If
            unspecified, the whole width of the terminal is used.
        :arg str fillchar: String for padding the left of ``text``
        :rtype: str
        """
        if width is None:
            width = self.width
        return Sequence(text, self).rjust(width, fillchar)

    def center(self, text, width=None, fillchar=u' '):
        """
        Center ``text``, which may contain terminal sequences.

        :arg str text: String to be centered
        :arg int width: Total width in which to center text. If
            unspecified, the whole width of the terminal is used.
        :arg str fillchar: String for padding the left and right of ``text``
        :rtype: str
        """
        if width is None:
            width = self.width
        return Sequence(text, self).center(width, fillchar)

    def length(self, text):
        u"""
        Return printable length of a string containing sequences.

        :arg str text: String to measure. May contain terminal sequences.
        :rtype: int
        :returns: The number of terminal character cells the string will occupy
            when printed

        Wide characters that consume 2 character cells are supported:

        >>> term = Terminal()
        >>> term.length(term.clear + term.red(u'コンニチハ'))
        10

        .. note:: Sequences such as 'clear', which is considered as a
            "movement sequence" because it would move the cursor to
            (y, x)(0, 0), are evaluated as a printable length of
            *0*.
        """
        return Sequence(text, self).length()

    def strip(self, text, chars=None):
        r"""
        Return ``text`` without sequences and leading or trailing whitespace.

        :rtype: str

        >>> term.strip(u' \x1b[0;3m xyz ')
        u'xyz'
        """
        return Sequence(text, self).strip(chars)

    def rstrip(self, text, chars=None):
        r"""
        Return ``text`` without terminal sequences or trailing whitespace.

        :rtype: str

        >>> term.rstrip(u' \x1b[0;3m xyz ')
        u'  xyz'
        """
        return Sequence(text, self).rstrip(chars)

    def lstrip(self, text, chars=None):
        r"""
        Return ``text`` without terminal sequences or leading whitespace.

        :rtype: str

        >>> term.lstrip(u' \x1b[0;3m xyz ')
        u'xyz '
        """
        return Sequence(text, self).lstrip(chars)

    def strip_seqs(self, text):
        r"""
        Return ``text`` stripped of only its terminal sequences.

        :rtype: str

        >>> term.strip_seqs(u'\x1b[0;3mxyz')
        u'xyz'
        >>> term.strip_seqs(term.cuf(5) + term.red(u'test'))
        u'     test'

        .. note:: Non-destructive sequences that adjust horizontal distance
            (such as ``\b`` or ``term.cuf(5)``) are replaced by destructive
            space or erasing.
        """
        return Sequence(text, self).strip_seqs()

    def split_seqs(self, text, **kwds):
        r"""
        Return ``text`` split by individual character elements and sequences.

        :arg kwds: remaining keyword arguments for :func:`re.split`.
        :rtype: list[str]

        >>> term.split_seqs(term.underline(u'xyz'))
        ['\x1b[4m', 'x', 'y', 'z', '\x1b(B', '\x1b[m']
        """
        pattern = self._caps_unnamed_any
        return list(filter(None, re.split(pattern, text, **kwds)))

    def wrap(self, text, width=None, **kwargs):
        """
        Text-wrap a string, returning a list of wrapped lines.

        :arg str text: Unlike :func:`textwrap.wrap`, ``text`` may contain
            terminal sequences, such as colors, bold, or underline. By
            default, tabs in ``text`` are expanded by
            :func:`string.expandtabs`.
        :arg int width: Unlike :func:`textwrap.wrap`, ``width`` will
            default to the width of the attached terminal.
        :rtype: list

        See :class:`textwrap.TextWrapper` for keyword arguments that can
        customize wrapping behaviour.
        """
        width = self.width if width is None else width
        lines = []
        for line in text.splitlines():
            lines.extend(
                (_linewrap for _linewrap in SequenceTextWrapper(
                    width=width, term=self, **kwargs).wrap(line))
                if line.strip() else (u'',))

        return lines

    def getch(self):
        """
        Read, decode, and return the next byte from the keyboard stream.

        :rtype: unicode
        :returns: a single unicode character, or ``u''`` if a multi-byte
            sequence has not yet been fully received.

        This method name and behavior mimics curses ``getch(void)``, and
        it supports :meth:`inkey`, reading only one byte from
        the keyboard string at a time. This method should always return
        without blocking if called after :meth:`kbhit` has returned True.

        Implementors of alternate input stream methods should override
        this method.
        """
        assert self._keyboard_fd is not None
        byte = os.read(self._keyboard_fd, 1)
        return self._keyboard_decoder.decode(byte, final=False)

    def ungetch(self, text):
        """
        Buffer input data to be discovered by next call to :meth:`~.inkey`.

        :arg str ucs: String to be buffered as keyboard input.
        """
        self._keyboard_buf.extendleft(text)

    def kbhit(self, timeout=None, **_kwargs):
        """
        Return whether a keypress has been detected on the keyboard.

        This method is used by :meth:`inkey` to determine if a byte may
        be read using :meth:`getch` without blocking.  The standard
        implementation simply uses the :func:`select.select` call on stdin.

        :arg float timeout: When ``timeout`` is 0, this call is
            non-blocking, otherwise blocking indefinitely until keypress
            is detected when None (default). When ``timeout`` is a
            positive number, returns after ``timeout`` seconds have
            elapsed (float).
        :rtype: bool
        :returns: True if a keypress is awaiting to be read on the keyboard
            attached to this terminal.  When input is not a terminal, False is
            always returned.
        """
        if _kwargs.pop('_intr_continue', None) is not None:
            warnings.warn('keyword argument _intr_continue deprecated: '
                          'beginning v1.9.6, behavior is as though such '
                          'value is always True.')
        if _kwargs:
            raise TypeError('inkey() got unexpected keyword arguments {!r}'
                            .format(_kwargs))

        stime = time.time()
        ready_r = [None, ]
        check_r = [self._keyboard_fd] if self._keyboard_fd is not None else []

        while HAS_TTY and True:
            try:
                ready_r, _, _ = select.select(check_r, [], [], timeout)
            except InterruptedError:
                # Beginning with python3.5, IntrruptError is no longer thrown
                # https://www.python.org/dev/peps/pep-0475/
                #
                # For previous versions of python, we take special care to
                # retry select on InterruptedError exception, namely to handle
                # a custom SIGWINCH handler. When installed, it would cause
                # select() to be interrupted with errno 4 (EAGAIN).
                #
                # Just as in python3.5, it is ignored, and a new timeout value
                # is derived from the previous unless timeout becomes negative.
                # because the signal handler has blocked beyond timeout, then
                # False is returned. Otherwise, when timeout is None, we
                # continue to block indefinitely (default).
                if timeout is not None:
                    # subtract time already elapsed,
                    timeout -= time.time() - stime
                    if timeout > 0:
                        continue
                    # no time remains after handling exception (rare)
                    ready_r = []        # pragma: no cover
                    break               # pragma: no cover
            else:
                break

        return False if self._keyboard_fd is None else check_r == ready_r

    @contextlib.contextmanager
    def cbreak(self):
        """
        Allow each keystroke to be read immediately after it is pressed.

        This is a context manager for :func:`tty.setcbreak`.

        This context manager activates 'rare' mode, the opposite of 'cooked'
        mode: On entry, :func:`tty.setcbreak` mode is activated disabling
        line-buffering of keyboard input and turning off automatic echo of
        input as output.

        .. note:: You must explicitly print any user input you would like
            displayed.  If you provide any kind of editing, you must handle
            backspace and other line-editing control functions in this mode
            as well!

        **Normally**, characters received from the keyboard cannot be read
        by Python until the *Return* key is pressed. Also known as *cooked* or
        *canonical input* mode, it allows the tty driver to provide
        line-editing before shuttling the input to your program and is the
        (implicit) default terminal mode set by most unix shells before
        executing programs.

        Technically, this context manager sets the :mod:`termios` attributes
        of the terminal attached to :obj:`sys.__stdin__`.

        .. note:: :func:`tty.setcbreak` sets ``VMIN = 1`` and ``VTIME = 0``,
            see http://www.unixwiz.net/techtips/termios-vmin-vtime.html
        """
        if HAS_TTY and self._keyboard_fd is not None:
            # Save current terminal mode:
            save_mode = termios.tcgetattr(self._keyboard_fd)
            save_line_buffered = self._line_buffered
            tty.setcbreak(self._keyboard_fd, termios.TCSANOW)
            try:
                self._line_buffered = False
                yield
            finally:
                # Restore prior mode:
                termios.tcsetattr(self._keyboard_fd,
                                  termios.TCSAFLUSH,
                                  save_mode)
                self._line_buffered = save_line_buffered
        else:
            yield

    @contextlib.contextmanager
    def raw(self):
        r"""
        A context manager for :func:`tty.setraw`.

        Although both :meth:`break` and :meth:`raw` modes allow each keystroke
        to be read immediately after it is pressed, Raw mode disables
        processing of input and output.

        In cbreak mode, special input characters such as ``^C`` or ``^S`` are
        interpreted by the terminal driver and excluded from the stdin stream.
        In raw mode these values are receive by the :meth:`inkey` method.

        Because output processing is not done, the newline ``'\n'`` is not
        enough, you must also print carriage return to ensure that the cursor
        is returned to the first column::

            with term.raw():
                print("printing in raw mode", end="\r\n")
        """
        if HAS_TTY and self._keyboard_fd is not None:
            # Save current terminal mode:
            save_mode = termios.tcgetattr(self._keyboard_fd)
            save_line_buffered = self._line_buffered
            tty.setraw(self._keyboard_fd, termios.TCSANOW)
            try:
                self._line_buffered = False
                yield
            finally:
                # Restore prior mode:
                termios.tcsetattr(self._keyboard_fd,
                                  termios.TCSAFLUSH,
                                  save_mode)
                self._line_buffered = save_line_buffered
        else:
            yield

    @contextlib.contextmanager
    def keypad(self):
        r"""
        Context manager that enables directional keypad input.

        On entrying, this puts the terminal into "keyboard_transmit" mode by
        emitting the keypad_xmit (smkx) capability. On exit, it emits
        keypad_local (rmkx).

        On an IBM-PC keyboard with numeric keypad of terminal-type *xterm*,
        with numlock off, the lower-left diagonal key transmits sequence
        ``\\x1b[F``, translated to :class:`~.Terminal` attribute
        ``KEY_END``.

        However, upon entering :meth:`keypad`, ``\\x1b[OF`` is transmitted,
        translating to ``KEY_LL`` (lower-left key), allowing you to determine
        diagonal direction keys.
        """
        try:
            self.stream.write(self.smkx)
            yield
        finally:
            self.stream.write(self.rmkx)

    def inkey(self, timeout=None, esc_delay=0.35, **_kwargs):
        """
        Read and return the next keyboard event within given timeout.

        Generally, this should be used inside the :meth:`raw` context manager.

        :arg float timeout: Number of seconds to wait for a keystroke before
            returning.  When ``None`` (default), this method may block
            indefinitely.
        :arg float esc_delay: To distinguish between the keystroke of
           ``KEY_ESCAPE``, and sequences beginning with escape, the parameter
           ``esc_delay`` specifies the amount of time after receiving escape
           (``chr(27)``) to seek for the completion of an application key
           before returning a :class:`~.Keystroke` instance for
           ``KEY_ESCAPE``.
        :rtype: :class:`~.Keystroke`.
        :returns: :class:`~.Keystroke`, which may be empty (``u''``) if
           ``timeout`` is specified and keystroke is not received.
        :raises RuntimeError: When :attr:`stream` is not a terminal, having
            no keyboard attached, a ``timeout`` value of ``None`` would block
            indefinitely, prevented by by raising an exception.

        .. note:: When used without the context manager :meth:`cbreak`, or
            :meth:`raw`, :obj:`sys.__stdin__` remains line-buffered, and this
            function will block until the return key is pressed!
        """
        if _kwargs.pop('_intr_continue', None) is not None:
            warnings.warn('keyword argument _intr_continue deprecated: '
                          'beginning v1.9.6, behavior is as though such '
                          'value is always True.')
        if _kwargs:
            raise TypeError('inkey() got unexpected keyword arguments {!r}'
                            .format(_kwargs))
        if timeout is None and self._keyboard_fd is None:
            raise RuntimeError(
                'Terminal.inkey() called, but no terminal with keyboard '
                'attached to process.  This call would hang forever.')

        resolve = functools.partial(resolve_sequence,
                                    mapper=self._keymap,
                                    codes=self._keycodes)

        stime = time.time()

        # re-buffer previously received keystrokes,
        ucs = u''
        while self._keyboard_buf:
            ucs += self._keyboard_buf.pop()

        # receive all immediately available bytes
        while self.kbhit(timeout=0):
            ucs += self.getch()

        # decode keystroke, if any
        ks = resolve(text=ucs)

        # so long as the most immediately received or buffered keystroke is
        # incomplete, (which may be a multibyte encoding), block until until
        # one is received.
        while not ks and self.kbhit(timeout=_time_left(stime, timeout)):
            ucs += self.getch()
            ks = resolve(text=ucs)

        # handle escape key (KEY_ESCAPE) vs. escape sequence (like those
        # that begin with \x1b[ or \x1bO) up to esc_delay when
        # received. This is not optimal, but causes least delay when
        # "meta sends escape" is used, or when an unsupported sequence is
        # sent.
        #
        # The statement, "ucs in self._keymap_prefixes" has an effect on
        # keystrokes such as Alt + Z ("\x1b[z" with metaSendsEscape): because
        # no known input sequences begin with such phrasing to allow it to be
        # returned more quickly than esc_delay otherwise blocks for.
        if ks.code == self.KEY_ESCAPE:
            esctime = time.time()
            while (ks.code == self.KEY_ESCAPE and
                   ucs in self._keymap_prefixes and
                   self.kbhit(timeout=_time_left(esctime, esc_delay))):
                ucs += self.getch()
                ks = resolve(text=ucs)

        # buffer any remaining text received
        self.ungetch(ucs[len(ks):])
        return ks


class WINSZ(collections.namedtuple('WINSZ', (
        'ws_row', 'ws_col', 'ws_xpixel', 'ws_ypixel'))):
    """
    Structure represents return value of :const:`termios.TIOCGWINSZ`.

    .. py:attribute:: ws_row

        rows, in characters

    .. py:attribute:: ws_col

        columns, in characters

    .. py:attribute:: ws_xpixel

        horizontal size, pixels

    .. py:attribute:: ws_ypixel

        vertical size, pixels
    """
    #: format of termios structure
    _FMT = 'hhhh'
    #: buffer of termios structure appropriate for ioctl argument
    _BUF = '\x00' * struct.calcsize(_FMT)


#: _CUR_TERM = None
#: From libcurses/doc/ncurses-intro.html (ESR, Thomas Dickey, et. al)::
#:
#:   "After the call to setupterm(), the global variable cur_term is set to
#:    point to the current structure of terminal capabilities. By calling
#:    setupterm() for each terminal, and saving and restoring cur_term, it
#:    is possible for a program to use two or more terminals at once."
#:
#: However, if you study Python's ``./Modules/_cursesmodule.c``, you'll find::
#:
#:   if (!initialised_setupterm && setupterm(termstr,fd,&err) == ERR) {
#:
#: Python - perhaps wrongly - will not allow for re-initialisation of new
#: terminals through :func:`curses.setupterm`, so the value of cur_term cannot
#: be changed once set: subsequent calls to :func:`curses.setupterm` have no
#: effect.
#:
#: Therefore, the :attr:`Terminal.kind` of each :class:`Terminal` is
#: essentially a singleton. This global variable reflects that, and a warning
#: is emitted if somebody expects otherwise.
