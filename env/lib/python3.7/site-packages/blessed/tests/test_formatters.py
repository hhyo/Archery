# -*- coding: utf-8 -*-
"""Tests string formatting functions."""
# std
import curses

# 3rd-party
import mock
import pytest


def test_parameterizing_string_args_unspecified(monkeypatch):
    """Test default args of formatters.ParameterizingString."""
    from blessed.formatters import ParameterizingString, FormattingString
    # first argument to tparm() is the sequence name, returned as-is;
    # subsequent arguments are usually Integers.
    tparm = lambda *args: u'~'.join(
        arg.decode('latin1') if not num else '%s' % (arg,)
        for num, arg in enumerate(args)).encode('latin1')

    monkeypatch.setattr(curses, 'tparm', tparm)

    # given,
    pstr = ParameterizingString(u'')

    # exercise __new__
    assert str(pstr) == u''
    assert pstr._normal == u''
    assert pstr._name == u'<not specified>'

    # exercise __call__
    zero = pstr(0)
    assert type(zero) is FormattingString
    assert zero == u'~0'
    assert zero('text') == u'~0text'

    # exercise __call__ with multiple args
    onetwo = pstr(1, 2)
    assert type(onetwo) is FormattingString
    assert onetwo == u'~1~2'
    assert onetwo('text') == u'~1~2text'


def test_parameterizing_string_args(monkeypatch):
    """Test basic formatters.ParameterizingString."""
    from blessed.formatters import ParameterizingString, FormattingString

    # first argument to tparm() is the sequence name, returned as-is;
    # subsequent arguments are usually Integers.
    tparm = lambda *args: u'~'.join(
        arg.decode('latin1') if not num else '%s' % (arg,)
        for num, arg in enumerate(args)).encode('latin1')

    monkeypatch.setattr(curses, 'tparm', tparm)

    # given,
    pstr = ParameterizingString(u'cap', u'norm', u'seq-name')

    # exercise __new__
    assert str(pstr) == u'cap'
    assert pstr._normal == u'norm'
    assert pstr._name == u'seq-name'

    # exercise __call__
    zero = pstr(0)
    assert type(zero) is FormattingString
    assert zero == u'cap~0'
    assert zero('text') == u'cap~0textnorm'

    # exercise __call__ with multiple args
    onetwo = pstr(1, 2)
    assert type(onetwo) is FormattingString
    assert onetwo == u'cap~1~2'
    assert onetwo('text') == u'cap~1~2textnorm'


def test_parameterizing_string_type_error(monkeypatch):
    """Test formatters.ParameterizingString raising TypeError."""
    from blessed.formatters import ParameterizingString

    def tparm_raises_TypeError(*args):
        raise TypeError('custom_err')

    monkeypatch.setattr(curses, 'tparm', tparm_raises_TypeError)

    # given,
    pstr = ParameterizingString(u'cap', u'norm', u'cap-name')

    # ensure TypeError when given a string raises custom exception
    try:
        pstr('XYZ')
        assert False, "previous call should have raised TypeError"
    except TypeError as err:
        assert (err.args[0] == (  # py3x
            "A native or nonexistent capability template, "
            "'cap-name' received invalid argument ('XYZ',): "
            "custom_err. You probably misspelled a "
            "formatting call like `bright_red'") or
            err.args[0] == (
                "A native or nonexistent capability template, "
                "u'cap-name' received invalid argument ('XYZ',): "
                "custom_err. You probably misspelled a "
                "formatting call like `bright_red'"))

    # ensure TypeError when given an integer raises its natural exception
    try:
        pstr(0)
        assert False, "previous call should have raised TypeError"
    except TypeError as err:
        assert err.args[0] == "custom_err"


def test_formattingstring(monkeypatch):
    """Test simple __call__ behavior of formatters.FormattingString."""
    from blessed.formatters import FormattingString

    # given, with arg
    pstr = FormattingString(u'attr', u'norm')

    # exercise __call__,
    assert pstr._normal == u'norm'
    assert str(pstr) == u'attr'
    assert pstr('text') == u'attrtextnorm'

    # given, with empty attribute
    pstr = FormattingString(u'', u'norm')
    assert pstr('text') == u'text'


def test_nested_formattingstring(monkeypatch):
    """Test nested __call__ behavior of formatters.FormattingString."""
    from blessed.formatters import FormattingString

    # given, with arg
    pstr = FormattingString(u'a1-', u'n-')
    zstr = FormattingString(u'a2-', u'n-')

    # exercise __call__
    assert pstr('x-', zstr('f-'), 'q-') == 'a1-x-a2-f-n-a1-q-n-'


def test_nested_formattingstring_type_error(monkeypatch):
    """Test formatters.FormattingString raising TypeError."""
    from blessed.formatters import FormattingString

    # given,
    pstr = FormattingString(u'a-', u'n-')
    expected_msg = (
        "Positional argument #1 is {0} expected any of "
        .format(type(1)))

    # exercise,
    with pytest.raises(TypeError) as err:
        pstr('text', 1, '...')

    # verify,
    assert expected_msg in str(err.value)


def test_nullcallablestring(monkeypatch):
    """Test formatters.NullCallableString"""
    from blessed.formatters import (NullCallableString)

    # given, with arg
    pstr = NullCallableString()

    # exercise __call__,
    assert str(pstr) == u''
    assert pstr('text') == u'text'
    assert pstr('text', 'moretext') == u'textmoretext'
    assert pstr(99, 1) == u''
    assert pstr() == u''
    assert pstr(0) == u''


def test_split_compound():
    """Test formatters.split_compound."""
    from blessed.formatters import split_compound

    assert split_compound(u'') == [u'']
    assert split_compound(u'a_b_c') == [u'a', u'b', u'c']
    assert split_compound(u'a_on_b_c') == [u'a', u'on_b', u'c']
    assert split_compound(u'a_bright_b_c') == [u'a', u'bright_b', u'c']
    assert split_compound(u'a_on_bright_b_c') == [u'a', u'on_bright_b', u'c']


def test_resolve_capability(monkeypatch):
    """Test formatters.resolve_capability and term sugaring """
    from blessed.formatters import resolve_capability

    # given, always returns a b'seq'
    tigetstr = lambda attr: ('seq-%s' % (attr,)).encode('latin1')
    monkeypatch.setattr(curses, 'tigetstr', tigetstr)
    term = mock.Mock()
    term._sugar = dict(mnemonic='xyz')

    # exercise
    assert resolve_capability(term, 'mnemonic') == u'seq-xyz'
    assert resolve_capability(term, 'natural') == u'seq-natural'

    # given, where tigetstr returns None
    tigetstr_none = lambda attr: None
    monkeypatch.setattr(curses, 'tigetstr', tigetstr_none)

    # exercise,
    assert resolve_capability(term, 'natural') == u''

    # given, where does_styling is False
    def raises_exception(*args):
        assert False, "Should not be called"
    term.does_styling = False
    monkeypatch.setattr(curses, 'tigetstr', raises_exception)

    # exercise,
    assert resolve_capability(term, 'natural') == u''


def test_resolve_color(monkeypatch):
    """Test formatters.resolve_color."""
    from blessed.formatters import (resolve_color,
                                      FormattingString,
                                      NullCallableString)

    color_cap = lambda digit: 'seq-%s' % (digit,)
    monkeypatch.setattr(curses, 'COLOR_RED', 1984)

    # given, terminal with color capabilities
    term = mock.Mock()
    term._background_color = color_cap
    term._foreground_color = color_cap
    term.number_of_colors = -1
    term.normal = 'seq-normal'

    # exercise,
    red = resolve_color(term, 'red')
    assert type(red) == FormattingString
    assert red == u'seq-1984'
    assert red('text') == u'seq-1984textseq-normal'

    # exercise bold, +8
    bright_red = resolve_color(term, 'bright_red')
    assert type(bright_red) == FormattingString
    assert bright_red == u'seq-1992'
    assert bright_red('text') == u'seq-1992textseq-normal'

    # given, terminal without color
    term.number_of_colors = 0

    # exercise,
    red = resolve_color(term, 'red')
    assert type(red) == NullCallableString
    assert red == u''
    assert red('text') == u'text'

    # exercise bold,
    bright_red = resolve_color(term, 'bright_red')
    assert type(bright_red) == NullCallableString
    assert bright_red == u''
    assert bright_red('text') == u'text'


def test_resolve_attribute_as_color(monkeypatch):
    """ Test simple resolve_attribte() given color name. """
    import blessed
    from blessed.formatters import resolve_attribute

    resolve_color = lambda term, digit: 'seq-%s' % (digit,)
    COLORS = set(['COLORX', 'COLORY'])
    COMPOUNDABLES = set(['JOINT', 'COMPOUND'])
    monkeypatch.setattr(blessed.formatters, 'resolve_color', resolve_color)
    monkeypatch.setattr(blessed.formatters, 'COLORS', COLORS)
    monkeypatch.setattr(blessed.formatters, 'COMPOUNDABLES', COMPOUNDABLES)
    term = mock.Mock()
    assert resolve_attribute(term, 'COLORX') == u'seq-COLORX'


def test_resolve_attribute_as_compoundable(monkeypatch):
    """ Test simple resolve_attribte() given a compoundable. """
    import blessed
    from blessed.formatters import resolve_attribute, FormattingString

    resolve_cap = lambda term, digit: 'seq-%s' % (digit,)
    COMPOUNDABLES = set(['JOINT', 'COMPOUND'])
    monkeypatch.setattr(blessed.formatters,
                        'resolve_capability',
                        resolve_cap)
    monkeypatch.setattr(blessed.formatters, 'COMPOUNDABLES', COMPOUNDABLES)
    term = mock.Mock()
    term.normal = 'seq-normal'

    compound = resolve_attribute(term, 'JOINT')
    assert type(compound) is FormattingString
    assert str(compound) == u'seq-JOINT'
    assert compound('text') == u'seq-JOINTtextseq-normal'


def test_resolve_attribute_non_compoundables(monkeypatch):
    """ Test recursive compounding of resolve_attribute(). """
    import blessed
    from blessed.formatters import resolve_attribute, ParameterizingString
    uncompoundables = lambda attr: ['split', 'compound']
    resolve_cap = lambda term, digit: 'seq-%s' % (digit,)
    monkeypatch.setattr(blessed.formatters,
                        'split_compound',
                        uncompoundables)
    monkeypatch.setattr(blessed.formatters,
                        'resolve_capability',
                        resolve_cap)
    tparm = lambda *args: u'~'.join(
        arg.decode('latin1') if not num else '%s' % (arg,)
        for num, arg in enumerate(args)).encode('latin1')
    monkeypatch.setattr(curses, 'tparm', tparm)

    term = mock.Mock()
    term.normal = 'seq-normal'

    # given
    pstr = resolve_attribute(term, 'not-a-compoundable')
    assert type(pstr) == ParameterizingString
    assert str(pstr) == u'seq-not-a-compoundable'
    # this is like calling term.move_x(3)
    assert pstr(3) == u'seq-not-a-compoundable~3'
    # this is like calling term.move_x(3)('text')
    assert pstr(3)('text') == u'seq-not-a-compoundable~3textseq-normal'


def test_resolve_attribute_recursive_compoundables(monkeypatch):
    """ Test recursive compounding of resolve_attribute(). """
    import blessed
    from blessed.formatters import resolve_attribute, FormattingString

    # patch,
    resolve_cap = lambda term, digit: 'seq-%s' % (digit,)
    monkeypatch.setattr(blessed.formatters,
                        'resolve_capability',
                        resolve_cap)
    tparm = lambda *args: u'~'.join(
        arg.decode('latin1') if not num else '%s' % (arg,)
        for num, arg in enumerate(args)).encode('latin1')
    monkeypatch.setattr(curses, 'tparm', tparm)
    monkeypatch.setattr(curses, 'COLOR_RED', 6502)
    monkeypatch.setattr(curses, 'COLOR_BLUE', 6800)

    color_cap = lambda digit: 'seq-%s' % (digit,)
    term = mock.Mock()
    term._background_color = color_cap
    term._foreground_color = color_cap
    term.normal = 'seq-normal'

    # given,
    pstr = resolve_attribute(term, 'bright_blue_on_red')

    # exercise,
    assert type(pstr) == FormattingString
    assert str(pstr) == 'seq-6808seq-6502'
    assert pstr('text') == 'seq-6808seq-6502textseq-normal'


def test_pickled_parameterizing_string(monkeypatch):
    """Test pickle-ability of a formatters.ParameterizingString."""
    from blessed.formatters import ParameterizingString, FormattingString

    # simply send()/recv() over multiprocessing Pipe, a simple
    # pickle.loads(dumps(...)) did not reproduce this issue,
    from multiprocessing import Pipe
    import pickle

    # first argument to tparm() is the sequence name, returned as-is;
    # subsequent arguments are usually Integers.
    tparm = lambda *args: u'~'.join(
        arg.decode('latin1') if not num else '%s' % (arg,)
        for num, arg in enumerate(args)).encode('latin1')

    monkeypatch.setattr(curses, 'tparm', tparm)

    # given,
    pstr = ParameterizingString(u'seqname', u'norm', u'cap-name')

    # multiprocessing Pipe implicitly pickles.
    r, w = Pipe()

    # exercise picklability of ParameterizingString
    for proto_num in range(pickle.HIGHEST_PROTOCOL):
        assert pstr == pickle.loads(pickle.dumps(pstr, protocol=proto_num))
    w.send(pstr)
    assert r.recv() == pstr

    # exercise picklability of FormattingString
    # -- the return value of calling ParameterizingString
    zero = pstr(0)
    for proto_num in range(pickle.HIGHEST_PROTOCOL):
        assert zero == pickle.loads(pickle.dumps(zero, protocol=proto_num))
    w.send(zero)
    assert r.recv() == zero


def test_tparm_returns_null(monkeypatch):
    """ Test 'tparm() returned NULL' is caught (win32 PDCurses systems). """
    # on win32, any calls to tparm raises curses.error with message,
    # "tparm() returned NULL", function PyCurses_tparm of _cursesmodule.c
    from blessed.formatters import ParameterizingString, NullCallableString

    def tparm(*args):
        raise curses.error("tparm() returned NULL")

    monkeypatch.setattr(curses, 'tparm', tparm)

    term = mock.Mock()
    term.normal = 'seq-normal'

    pstr = ParameterizingString(u'cap', u'norm', u'seq-name')

    value = pstr(u'x')
    assert type(value) is NullCallableString


def test_tparm_other_exception(monkeypatch):
    """ Test 'tparm() returned NULL' is caught (win32 PDCurses systems). """
    # on win32, any calls to tparm raises curses.error with message,
    # "tparm() returned NULL", function PyCurses_tparm of _cursesmodule.c
    from blessed.formatters import ParameterizingString, NullCallableString

    def tparm(*args):
        raise curses.error("unexpected error in tparm()")

    monkeypatch.setattr(curses, 'tparm', tparm)

    term = mock.Mock()
    term.normal = 'seq-normal'

    pstr = ParameterizingString(u'cap', u'norm', u'seq-name')

    try:
        pstr(u'x')
        assert False, "previous call should have raised curses.error"
    except curses.error:
        pass
