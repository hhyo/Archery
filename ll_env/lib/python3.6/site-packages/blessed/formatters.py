"""Sub-module providing sequence-formatting functions."""
# standard imports
import curses

# 3rd-party
import six


def _make_colors():
    """
    Return set of valid colors and their derivatives.

    :rtype: set
    """
    derivatives = ('on', 'bright', 'on_bright',)
    colors = set('black red green yellow blue magenta cyan white'.split())
    return set(['_'.join((_deravitive, _color))
                for _deravitive in derivatives
                for _color in colors]) | colors


def _make_compoundables(colors):
    """
    Return given set ``colors`` along with all "compoundable" attributes.

    :arg set colors: set of color names as string.
    :rtype: set
    """
    _compoundables = set('bold underline reverse blink dim italic shadow '
                         'standout subscript superscript'.split())
    return colors | _compoundables


#: Valid colors and their background (on), bright,
#: and bright-background derivatives.
COLORS = _make_colors()

#: Attributes and colors which may be compounded by underscore.
COMPOUNDABLES = _make_compoundables(COLORS)


class ParameterizingString(six.text_type):
    r"""
    A Unicode string which can be called as a parameterizing termcap.

    For example::

        >>> term = Terminal()
        >>> color = ParameterizingString(term.color, term.normal, 'color')
        >>> color(9)('color #9')
        u'\x1b[91mcolor #9\x1b(B\x1b[m'
    """

    def __new__(cls, *args):
        """
        Class constructor accepting 3 positional arguments.

        :arg cap: parameterized string suitable for curses.tparm()
        :arg normal: terminating sequence for this capability (optional).
        :arg name: name of this terminal capability (optional).
        """
        assert args and len(args) < 4, args
        new = six.text_type.__new__(cls, args[0])
        new._normal = args[1] if len(args) > 1 else u''
        new._name = args[2] if len(args) > 2 else u'<not specified>'
        return new

    def __call__(self, *args):
        """
        Returning :class:`FormattingString` instance for given parameters.

        Return evaluated terminal capability (self), receiving arguments
        ``*args``, followed by the terminating sequence (self.normal) into
        a :class:`FormattingString` capable of being called.

        :rtype: :class:`FormattingString` or :class:`NullCallableString`
        """
        try:
            # Re-encode the cap, because tparm() takes a bytestring in Python
            # 3. However, appear to be a plain Unicode string otherwise so
            # concats work.
            attr = curses.tparm(self.encode('latin1'), *args).decode('latin1')
            return FormattingString(attr, self._normal)
        except TypeError as err:
            # If the first non-int (i.e. incorrect) arg was a string, suggest
            # something intelligent:
            if args and isinstance(args[0], six.string_types):
                raise TypeError(
                    "A native or nonexistent capability template, %r received"
                    " invalid argument %r: %s. You probably misspelled a"
                    " formatting call like `bright_red'" % (
                        self._name, args, err))
            # Somebody passed a non-string; I don't feel confident
            # guessing what they were trying to do.
            raise
        except curses.error as err:
            # ignore 'tparm() returned NULL', you won't get any styling,
            # even if does_styling is True. This happens on win32 platforms
            # with http://www.lfd.uci.edu/~gohlke/pythonlibs/#curses installed
            if "tparm() returned NULL" not in six.text_type(err):
                raise
            return NullCallableString()


class ParameterizingProxyString(six.text_type):
    r"""
    A Unicode string which can be called to proxy missing termcap entries.

    This class supports the function :func:`get_proxy_string`, and mirrors
    the behavior of :class:`ParameterizingString`, except that instead of
    a capability name, receives a format string, and callable to filter the
    given positional ``*args`` of :meth:`ParameterizingProxyString.__call__`
    into a terminal sequence.

    For example::

        >>> from blessed import Terminal
        >>> term = Terminal('screen')
        >>> hpa = ParameterizingString(term.hpa, term.normal, 'hpa')
        >>> hpa(9)
        u''
        >>> fmt = u'\x1b[{0}G'
        >>> fmt_arg = lambda *arg: (arg[0] + 1,)
        >>> hpa = ParameterizingProxyString((fmt, fmt_arg), term.normal, 'hpa')
        >>> hpa(9)
        u'\x1b[10G'
    """

    def __new__(cls, *args):
        """
        Class constructor accepting 4 positional arguments.

        :arg fmt: format string suitable for displaying terminal sequences.
        :arg callable: receives __call__ arguments for formatting fmt.
        :arg normal: terminating sequence for this capability (optional).
        :arg name: name of this terminal capability (optional).
        """
        assert args and len(args) < 4, args
        assert isinstance(args[0], tuple), args[0]
        assert callable(args[0][1]), args[0][1]
        new = six.text_type.__new__(cls, args[0][0])
        new._fmt_args = args[0][1]
        new._normal = args[1] if len(args) > 1 else u''
        new._name = args[2] if len(args) > 2 else u'<not specified>'
        return new

    def __call__(self, *args):
        """
        Returning :class:`FormattingString` instance for given parameters.

        Arguments are determined by the capability.  For example, ``hpa``
        (move_x) receives only a single integer, whereas ``cup`` (move)
        receives two integers.  See documentation in terminfo(5) for the
        given capability.

        :rtype: FormattingString
        """
        return FormattingString(self.format(*self._fmt_args(*args)),
                                self._normal)


def get_proxy_string(term, attr):
    """
    Proxy and return callable string for proxied attributes.

    :arg Terminal term: :class:`~.Terminal` instance.
    :arg str attr: terminal capability name that may be proxied.
    :rtype: None or :class:`ParameterizingProxyString`.
    :returns: :class:`ParameterizingProxyString` for some attributes
        of some terminal types that support it, where the terminfo(5)
        database would otherwise come up empty, such as ``move_x``
        attribute for ``term.kind`` of ``screen``.  Otherwise, None.
    """
    # normalize 'screen-256color', or 'ansi.sys' to its basic names
    term_kind = next(iter(_kind for _kind in ('screen', 'ansi',)
                          if term.kind.startswith(_kind)), term)
    _proxy_table = {  # pragma: no cover
        'screen': {
            # proxy move_x/move_y for 'screen' terminal type, used by tmux(1).
            'hpa': ParameterizingProxyString(
                (u'\x1b[{0}G', lambda *arg: (arg[0] + 1,)), term.normal, attr),
            'vpa': ParameterizingProxyString(
                (u'\x1b[{0}d', lambda *arg: (arg[0] + 1,)), term.normal, attr),
        },
        'ansi': {
            # proxy show/hide cursor for 'ansi' terminal type.  There is some
            # demand for a richly working ANSI terminal type for some reason.
            'civis': ParameterizingProxyString(
                (u'\x1b[?25l', lambda *arg: ()), term.normal, attr),
            'cnorm': ParameterizingProxyString(
                (u'\x1b[?25h', lambda *arg: ()), term.normal, attr),
            'hpa': ParameterizingProxyString(
                (u'\x1b[{0}G', lambda *arg: (arg[0] + 1,)), term.normal, attr),
            'vpa': ParameterizingProxyString(
                (u'\x1b[{0}d', lambda *arg: (arg[0] + 1,)), term.normal, attr),
            'sc': '\x1b[s',
            'rc': '\x1b[u',
        }
    }
    return _proxy_table.get(term_kind, {}).get(attr, None)


class FormattingString(six.text_type):
    r"""
    A Unicode string which doubles as a callable.

    This is used for terminal attributes, so that it may be used both
    directly, or as a callable.  When used directly, it simply emits
    the given terminal sequence.  When used as a callable, it wraps the
    given (string) argument with the 2nd argument used by the class
    constructor::

        >>> style = FormattingString(term.bright_blue, term.normal)
        >>> print(repr(style))
        u'\x1b[94m'
        >>> style('Big Blue')
        u'\x1b[94mBig Blue\x1b(B\x1b[m'
    """

    def __new__(cls, *args):
        """
        Class constructor accepting 2 positional arguments.

        :arg sequence: terminal attribute sequence.
        :arg normal: terminating sequence for this attribute (optional).
        """
        assert 1 <= len(args) <= 2, args
        new = six.text_type.__new__(cls, args[0])
        new._normal = args[1] if len(args) > 1 else u''
        return new

    def __call__(self, *args):
        """Return ``text`` joined by ``sequence`` and ``normal``."""
        # Jim Allman brings us this convenience of allowing existing
        # unicode strings to be joined as a call parameter to a formatting
        # string result, allowing nestation:
        #
        # >>> t.red('This is ', t.bold('extremely'), ' dangerous!')
        for idx, ucs_part in enumerate(args):
            if not isinstance(ucs_part, six.string_types):
                raise TypeError("Positional argument #{idx} is {is_type} "
                                "expected any of {expected_types}: "
                                "{ucs_part!r}".format(
                                    idx=idx, ucs_part=ucs_part,
                                    is_type=type(ucs_part),
                                    expected_types=six.string_types,
                                ))
        postfix = u''
        if self and self._normal:
            postfix = self._normal
            _refresh = self._normal + self
            args = [_refresh.join(ucs_part.split(self._normal))
                    for ucs_part in args]

        return self + u''.join(args) + postfix


class NullCallableString(six.text_type):
    """
    A dummy callable Unicode alternative to :class:`FormattingString`.

    This is used for colors on terminals that do not support colors,
    it is just a basic form of unicode that may also act as a callable.
    """

    def __new__(cls):
        """Class constructor."""
        new = six.text_type.__new__(cls, u'')
        return new

    def __call__(self, *args):
        """
        Allow empty string to be callable, returning given string, if any.

        When called with an int as the first arg, return an empty Unicode. An
        int is a good hint that I am a :class:`ParameterizingString`, as there
        are only about half a dozen string-returning capabilities listed in
        terminfo(5) which accept non-int arguments, they are seldom used.

        When called with a non-int as the first arg (no no args at all), return
        the first arg, acting in place of :class:`FormattingString` without
        any attributes.
        """
        if not args or isinstance(args[0], int):
            # As a NullCallableString, even when provided with a parameter,
            # such as t.color(5), we must also still be callable, fe:
            #
            # >>> t.color(5)('shmoo')
            #
            # is actually simplified result of NullCallable()() on terminals
            # without color support, so turtles all the way down: we return
            # another instance.
            return NullCallableString()
        return u''.join(args)


def split_compound(compound):
    """
    Split compound formating string into segments.

    >>> split_compound('bold_underline_bright_blue_on_red')
    ['bold', 'underline', 'bright_blue', 'on_red']

    :arg str compound: a string that may contain compounds, separated by
        underline (``_``).
    :rtype: list
    """
    merged_segs = []
    # These occur only as prefixes, so they can always be merged:
    mergeable_prefixes = ['on', 'bright', 'on_bright']
    for segment in compound.split('_'):
        if merged_segs and merged_segs[-1] in mergeable_prefixes:
            merged_segs[-1] += '_' + segment
        else:
            merged_segs.append(segment)
    return merged_segs


def resolve_capability(term, attr):
    """
    Resolve a raw terminal capability using :func:`tigetstr`.

    :arg Terminal term: :class:`~.Terminal` instance.
    :arg str attr: terminal capability name.
    :returns: string of the given terminal capability named by ``attr``,
       which may be empty (u'') if not found or not supported by the
       given :attr:`~.Terminal.kind`.
    :rtype: str
    """
    # Decode sequences as latin1, as they are always 8-bit bytes, so when
    # b'\xff' is returned, this must be decoded to u'\xff'.
    if not term.does_styling:
        return u''
    val = curses.tigetstr(term._sugar.get(attr, attr))
    return u'' if val is None else val.decode('latin1')


def resolve_color(term, color):
    """
    Resolve a simple color name to a callable capability.

    This function supports :func:`resolve_attribute`.

    :arg Terminal term: :class:`~.Terminal` instance.
    :arg str color: any string found in set :const:`COLORS`.
    :returns: a string class instance which emits the terminal sequence
        for the given color, and may be used as a callable to wrap the
        given string with such sequence.
    :returns: :class:`NullCallableString` when
        :attr:`~.Terminal.number_of_colors` is 0,
        otherwise :class:`FormattingString`.
    :rtype: :class:`NullCallableString` or :class:`FormattingString`
    """
    if term.number_of_colors == 0:
        return NullCallableString()

    # NOTE(erikrose): Does curses automatically exchange red and blue and cyan
    # and yellow when a terminal supports setf/setb rather than setaf/setab?
    # I'll be blasted if I can find any documentation. The following
    # assumes it does: to terminfo(5) describes color(1) as COLOR_RED when
    # using setaf, but COLOR_BLUE when using setf.
    color_cap = (term._background_color if 'on_' in color else
                 term._foreground_color)

    # curses constants go up to only 7, so add an offset to get at the
    # bright colors at 8-15:
    offset = 8 if 'bright_' in color else 0
    base_color = color.rsplit('_', 1)[-1]

    attr = 'COLOR_%s' % (base_color.upper(),)
    fmt_attr = color_cap(getattr(curses, attr) + offset)
    return FormattingString(fmt_attr, term.normal)


def resolve_attribute(term, attr):
    """
    Resolve a terminal attribute name into a capability class.

    :arg Terminal term: :class:`~.Terminal` instance.
    :arg str attr: Sugary, ordinary, or compound formatted terminal
        capability, such as "red_on_white", "normal", "red", or
        "bold_on_black", respectively.
    :returns: a string class instance which emits the terminal sequence
        for the given terminal capability, or may be used as a callable to
        wrap the given string with such sequence.
    :returns: :class:`NullCallableString` when
        :attr:`~.Terminal.number_of_colors` is 0,
        otherwise :class:`FormattingString`.
    :rtype: :class:`NullCallableString` or :class:`FormattingString`
    """
    if attr in COLORS:
        return resolve_color(term, attr)

    # A direct compoundable, such as `bold' or `on_red'.
    if attr in COMPOUNDABLES:
        sequence = resolve_capability(term, attr)
        return FormattingString(sequence, term.normal)

    # Given `bold_on_red', resolve to ('bold', 'on_red'), RECURSIVE
    # call for each compounding section, joined and returned as
    # a completed completed FormattingString.
    formatters = split_compound(attr)
    if all(fmt in COMPOUNDABLES for fmt in formatters):
        resolution = (resolve_attribute(term, fmt) for fmt in formatters)
        return FormattingString(u''.join(resolution), term.normal)
    else:
        # otherwise, this is our end-game: given a sequence such as 'csr'
        # (change scrolling region), return a ParameterizingString instance,
        # that when called, performs and returns the final string after curses
        # capability lookup is performed.
        tparm_capseq = resolve_capability(term, attr)
        if not tparm_capseq:
            # and, for special terminals, such as 'screen', provide a Proxy
            # ParameterizingString for attributes they do not claim to support,
            # but actually do! (such as 'hpa' and 'vpa').
            proxy = get_proxy_string(term, term._sugar.get(attr, attr))
            if proxy is not None:
                return proxy
        return ParameterizingString(tparm_capseq, term.normal, attr)
