# -*- coding: utf-8 -*-
"""Tests for Terminal() sequences and sequence-awareness."""
# std imports
import platform
import random
import sys
import os

# local
from .accessories import (
    all_terms,
    as_subprocess,
    TestTerminal,
    unicode_parm,
    many_columns,
    unicode_cap,
)

# 3rd party
import pytest
import mock
import six


def test_capability():
    """Check that capability lookup works."""
    @as_subprocess
    def child():
        # Also test that Terminal grabs a reasonable default stream. This test
        # assumes it will be run from a tty.
        t = TestTerminal()
        sc = unicode_cap('sc')
        assert t.save == sc
        assert t.save == sc  # Make sure caching doesn't screw it up.

    child()


def test_capability_without_tty():
    """Assert capability templates are '' when stream is not a tty."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=six.StringIO())
        assert t.save == u''
        assert t.red == u''

    child()


def test_capability_with_forced_tty():
    """force styling should return sequences even for non-ttys."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=six.StringIO(), force_styling=True)
        assert t.save == unicode_cap('sc')

    child()


def test_parametrization():
    """Test parameterizing a capability."""
    @as_subprocess
    def child():
        assert TestTerminal().cup(3, 4) == unicode_parm('cup', 3, 4)

    child()


def test_height_and_width():
    """Assert that ``height_and_width()`` returns full integers."""
    @as_subprocess
    def child():
        t = TestTerminal()  # kind shouldn't matter.
        assert isinstance(t.height, int)
        assert isinstance(t.width, int)

    child()


def test_stream_attr():
    """Make sure Terminal ``stream`` is stdout by default."""
    @as_subprocess
    def child():
        assert TestTerminal().stream == sys.__stdout__

    child()


def test_location_with_styling(all_terms):
    """Make sure ``location()`` works on all terminals."""
    @as_subprocess
    def child_with_styling(kind):
        t = TestTerminal(kind=kind, stream=six.StringIO(), force_styling=True)
        with t.location(3, 4):
            t.stream.write(u'hi')
        expected_output = u''.join(
            (unicode_cap('sc') or u'\x1b[s',
             unicode_parm('cup', 4, 3),
             u'hi',
             unicode_cap('rc') or u'\x1b[u'))
        assert (t.stream.getvalue() == expected_output)

    child_with_styling(all_terms)


def test_location_without_styling():
    """Make sure ``location()`` silently passes without styling."""
    @as_subprocess
    def child_without_styling():
        """No side effect for location as a context manager without styling."""
        t = TestTerminal(stream=six.StringIO(), force_styling=None)

        with t.location(3, 4):
            t.stream.write(u'hi')

        assert t.stream.getvalue() == u'hi'

    child_without_styling()


def test_horizontal_location(all_terms):
    """Make sure we can move the cursor horizontally without changing rows."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind, stream=six.StringIO(), force_styling=True)
        with t.location(x=5):
            pass
        _hpa = unicode_parm('hpa', 5)
        if not _hpa and (kind.startswith('screen') or
                         kind.startswith('ansi')):
            _hpa = u'\x1b[6G'
        expected_output = u''.join(
            (unicode_cap('sc') or u'\x1b[s',
             _hpa,
             unicode_cap('rc') or u'\x1b[u'))
        assert (t.stream.getvalue() == expected_output), (
            repr(t.stream.getvalue()), repr(expected_output))

    child(all_terms)


def test_vertical_location(all_terms):
    """Make sure we can move the cursor horizontally without changing rows."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind, stream=six.StringIO(), force_styling=True)
        with t.location(y=5):
            pass
        _vpa = unicode_parm('vpa', 5)
        if not _vpa and (kind.startswith('screen') or
                         kind.startswith('ansi')):
            _vpa = u'\x1b[6d'

        expected_output = u''.join(
            (unicode_cap('sc') or u'\x1b[s',
             _vpa,
             unicode_cap('rc') or u'\x1b[u'))
        assert (t.stream.getvalue() == expected_output)

    child(all_terms)


def test_inject_move_x():
    """Test injection of hpa attribute for screen/ansi (issue #55)."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind, stream=six.StringIO(), force_styling=True)
        COL = 5
        with t.location(x=COL):
            pass
        expected_output = u''.join(
            (unicode_cap('sc') or u'\x1b[s',
             u'\x1b[{0}G'.format(COL + 1),
             unicode_cap('rc') or u'\x1b[u'))
        assert (t.stream.getvalue() == expected_output)
        assert (t.move_x(COL) == u'\x1b[{0}G'.format(COL + 1))

    child('screen')
    child('screen-256color')
    child('ansi')


def test_inject_move_y():
    """Test injection of vpa attribute for screen/ansi (issue #55)."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind, stream=six.StringIO(), force_styling=True)
        ROW = 5
        with t.location(y=ROW):
            pass
        expected_output = u''.join(
            (unicode_cap('sc') or u'\x1b[s',
             u'\x1b[{0}d'.format(ROW + 1),
             unicode_cap('rc') or u'\x1b[u'))
        assert (t.stream.getvalue() == expected_output)
        assert (t.move_y(ROW) == u'\x1b[{0}d'.format(ROW + 1))

    child('screen')
    child('screen-256color')
    child('ansi')


def test_inject_civis_and_cnorm_for_ansi():
    """Test injection of cvis attribute for ansi."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind, stream=six.StringIO(), force_styling=True)
        with t.hidden_cursor():
            pass
        expected_output = u'\x1b[?25l\x1b[?25h'
        assert (t.stream.getvalue() == expected_output)

    child('ansi')


def test_inject_sc_and_rc_for_ansi():
    """Test injection of sc and rc (save and restore cursor) for ansi."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind, stream=six.StringIO(), force_styling=True)
        with t.location():
            pass
        expected_output = u'\x1b[s\x1b[u'
        assert (t.stream.getvalue() == expected_output)

    child('ansi')


def test_zero_location(all_terms):
    """Make sure ``location()`` pays attention to 0-valued args."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind, stream=six.StringIO(), force_styling=True)
        with t.location(0, 0):
            pass
        expected_output = u''.join(
            (unicode_cap('sc') or u'\x1b[s',
             unicode_parm('cup', 0, 0),
             unicode_cap('rc') or u'\x1b[u'))
        assert (t.stream.getvalue() == expected_output)

    child(all_terms)


def test_mnemonic_colors(all_terms):
    """Make sure color shortcuts work."""
    @as_subprocess
    def child(kind):
        def color(t, num):
            return t.number_of_colors and unicode_parm('setaf', num) or ''

        def on_color(t, num):
            return t.number_of_colors and unicode_parm('setab', num) or ''

        # Avoid testing red, blue, yellow, and cyan, since they might someday
        # change depending on terminal type.
        t = TestTerminal(kind=kind)
        assert (t.white == color(t, 7))
        assert (t.green == color(t, 2))  # Make sure it's different than white.
        assert (t.on_black == on_color(t, 0))
        assert (t.on_green == on_color(t, 2))
        assert (t.bright_black == color(t, 8))
        assert (t.bright_green == color(t, 10))
        assert (t.on_bright_black == on_color(t, 8))
        assert (t.on_bright_green == on_color(t, 10))

    child(all_terms)


def test_callable_numeric_colors(all_terms):
    """``color(n)`` should return a formatting wrapper."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind)
        if t.magenta:
            assert t.color(5)('smoo') == t.magenta + 'smoo' + t.normal
        else:
            assert t.color(5)('smoo') == 'smoo'

        if t.on_magenta:
            assert t.on_color(5)('smoo') == t.on_magenta + 'smoo' + t.normal
        else:
            assert t.color(5)(u'smoo') == 'smoo'

        if t.color(4):
            assert t.color(4)(u'smoo') == t.color(4) + u'smoo' + t.normal
        else:
            assert t.color(4)(u'smoo') == 'smoo'

        if t.on_green:
            assert t.on_color(2)('smoo') == t.on_green + u'smoo' + t.normal
        else:
            assert t.on_color(2)('smoo') == 'smoo'

        if t.on_color(6):
            assert t.on_color(6)('smoo') == t.on_color(6) + u'smoo' + t.normal
        else:
            assert t.on_color(6)('smoo') == 'smoo'

    child(all_terms)


def test_null_callable_numeric_colors(all_terms):
    """``color(n)`` should be a no-op on null terminals."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(stream=six.StringIO(), kind=kind)
        assert (t.color(5)('smoo') == 'smoo')
        assert (t.on_color(6)('smoo') == 'smoo')

    child(all_terms)


def test_naked_color_cap(all_terms):
    """``term.color`` should return a stringlike capability."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind)
        assert (t.color + '' == t.setaf + '')

    child(all_terms)


def test_formatting_functions(all_terms):
    """Test simple and compound formatting wrappers."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind)
        # test simple sugar,
        if t.bold:
            expected_output = u''.join((t.bold, u'hi', t.normal))
        else:
            expected_output = u'hi'
        assert t.bold(u'hi') == expected_output
        # Plain strs for Python 2.x
        if t.green:
            expected_output = u''.join((t.green, 'hi', t.normal))
        else:
            expected_output = u'hi'
        assert t.green('hi') == expected_output
        # Test unicode
        if t.underline:
            expected_output = u''.join((t.underline, u'boö', t.normal))
        else:
            expected_output = u'boö'
        assert (t.underline(u'boö') == expected_output)

        if t.subscript:
            expected_output = u''.join((t.subscript, u'[1]', t.normal))
        else:
            expected_output = u'[1]'

        assert (t.subscript(u'[1]') == expected_output)

    child(all_terms)


def test_compound_formatting(all_terms):
    """Test simple and compound formatting wrappers."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind)
        if any((t.bold, t.green)):
            expected_output = u''.join((t.bold, t.green, u'boö', t.normal))
        else:
            expected_output = u'boö'
        assert t.bold_green(u'boö') == expected_output

        if any((t.on_bright_red, t.bold, t.bright_green, t.underline)):
            expected_output = u''.join(
                (t.on_bright_red, t.bold, t.bright_green, t.underline, u'meh',
                 t.normal))
        else:
            expected_output = u'meh'
        assert (t.on_bright_red_bold_bright_green_underline('meh')
                == expected_output)

    child(all_terms)


def test_nested_formatting(all_terms):
    """Test complex nested compound formatting, wow!"""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind)

        # Test deeply nested styles
        given = t.green('-a-', t.bold('-b-', t.underline('-c-'),
                                      '-d-'),
                        '-e-')
        expected = u''.join((
            t.green, '-a-', t.bold, '-b-', t.underline, '-c-', t.normal,
            t.green, t.bold, '-d-',
            t.normal, t.green, '-e-', t.normal))
        assert given == expected

        # Test off-and-on nested styles
        given = t.green('off ', t.underline('ON'),
                        ' off ', t.underline('ON'),
                        ' off')
        expected = u''.join((
            t.green, 'off ', t.underline, 'ON',
            t.normal, t.green , ' off ', t.underline, 'ON',
            t.normal, t.green, ' off', t.normal))
        assert given == expected


def test_formatting_functions_without_tty(all_terms):
    """Test crazy-ass formatting wrappers when there's no tty."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind, stream=six.StringIO(), force_styling=False)
        assert (t.bold(u'hi') == u'hi')
        assert (t.green('hi') == u'hi')
        # Test non-ASCII chars, no longer really necessary:
        assert (t.bold_green(u'boö') == u'boö')
        assert (t.bold_underline_green_on_red('loo') == u'loo')

        # Test deeply nested styles
        given = t.green('-a-', t.bold('-b-', t.underline('-c-'),
                                      '-d-'),
                        '-e-')
        expected = u'-a--b--c--d--e-'
        assert given == expected

        # Test off-and-on nested styles
        given = t.green('off ', t.underline('ON'),
                        ' off ', t.underline('ON'),
                        ' off')
        expected = u'off ON off ON off'
        assert given == expected
        assert (t.on_bright_red_bold_bright_green_underline('meh') == u'meh')

    child(all_terms)


def test_nice_formatting_errors(all_terms):
    """Make sure you get nice hints if you misspell a formatting wrapper."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind)
        try:
            t.bold_misspelled('hey')
            assert not t.is_a_tty or False, 'Should have thrown exception'
        except TypeError:
            e = sys.exc_info()[1]
            assert 'probably misspelled' in e.args[0]
        try:
            t.bold_misspelled(u'hey')  # unicode
            assert not t.is_a_tty or False, 'Should have thrown exception'
        except TypeError:
            e = sys.exc_info()[1]
            assert 'probably misspelled' in e.args[0]

        try:
            t.bold_misspelled(None)  # an arbitrary non-string
            assert not t.is_a_tty or False, 'Should have thrown exception'
        except TypeError:
            e = sys.exc_info()[1]
            assert 'probably misspelled' not in e.args[0]

        if platform.python_implementation() != 'PyPy':
            # PyPy fails to toss an exception, Why?!
            try:
                t.bold_misspelled('a', 'b')  # >1 string arg
                assert not t.is_a_tty or False, 'Should have thrown exception'
            except TypeError:
                e = sys.exc_info()[1]
                assert 'probably misspelled' in e.args[0], e.args

    child(all_terms)


def test_null_callable_string(all_terms):
    """Make sure NullCallableString tolerates all kinds of args."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(stream=six.StringIO(), kind=kind)
        assert (t.clear == '')
        assert (t.move(1 == 2) == '')
        assert (t.move_x(1) == '')
        assert (t.bold() == '')
        assert (t.bold('', 'x', 'huh?') == 'xhuh?')
        assert (t.clear('x') == 'x')

    child(all_terms)


def test_padd():
    """ Test Terminal.padd(seq). """
    @as_subprocess
    def child():
        from blessed.sequences import Sequence
        from blessed import Terminal
        term = Terminal('xterm-256color')
        assert Sequence('xyz\b', term).padd() == u'xy'
        assert Sequence('xyz\b-', term).padd() == u'xy-'
        assert Sequence('xxxx\x1b[3Dzz', term).padd() == u'xzz'
        assert Sequence('\x1b[3D', term).padd() == u''  # "Trim left"

    child()

def test_split_seqs(all_terms):
    """Test Terminal.split_seqs."""
    @as_subprocess
    def child(kind):
        from blessed import Terminal
        term = Terminal(kind)

        if term.sc and term.rc:
            given_text = term.sc + 'AB' + term.rc + 'CD'
            expected = [term.sc, 'A', 'B', term.rc, 'C', 'D']
            result = list(term.split_seqs(given_text))
            assert result == expected

        if term.bold:
            given_text = term.bold + 'bbq'
            expected = [term.bold, 'b', 'b', 'q']
            result = list(term.split_seqs(given_text))
            assert result == expected

    child(all_terms)
