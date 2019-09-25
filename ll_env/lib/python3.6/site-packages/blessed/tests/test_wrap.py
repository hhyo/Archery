# std
import os
import textwrap

# local
from .accessories import (
    as_subprocess,
    TestTerminal,
    many_columns,
)

# 3rd party
import pytest

TEXTWRAP_KEYWORD_COMBINATIONS = [
    dict(break_long_words=False,
         drop_whitespace=False,
         subsequent_indent=''),
    dict(break_long_words=False,
         drop_whitespace=True,
         subsequent_indent=''),
    dict(break_long_words=False,
         drop_whitespace=False,
         subsequent_indent=' '),
    dict(break_long_words=False,
         drop_whitespace=True,
         subsequent_indent=' '),
    dict(break_long_words=True,
         drop_whitespace=False,
         subsequent_indent=''),
    dict(break_long_words=True,
         drop_whitespace=True,
         subsequent_indent=''),
    dict(break_long_words=True,
         drop_whitespace=False,
         subsequent_indent=' '),
    dict(break_long_words=True,
         drop_whitespace=True,
         subsequent_indent=' '),
]
if os.environ.get('TEST_QUICK', None) is not None:
    # test only one feature: everything on
    TEXTWRAP_KEYWORD_COMBINATIONS = [
        dict(break_long_words=True,
             drop_whitespace=True,
             subsequent_indent=' ')
    ]


def test_SequenceWrapper_invalid_width():
    """Test exception thrown from invalid width"""
    WIDTH = -3

    @as_subprocess
    def child():
        term = TestTerminal()
        try:
            my_wrapped = term.wrap(u'------- -------------', WIDTH)
        except ValueError as err:
            assert err.args[0] == (
                "invalid width %r(%s) (must be integer > 0)" % (
                    WIDTH, type(WIDTH)))
        else:
            assert False, 'Previous stmt should have raised exception.'
            del my_wrapped  # assigned but never used

    child()


@pytest.mark.parametrize("kwargs", TEXTWRAP_KEYWORD_COMBINATIONS)
def test_SequenceWrapper(many_columns, kwargs):
    """Test that text wrapping matches internal extra options."""
    @as_subprocess
    def child(width, pgraph, kwargs):
        # build a test paragraph, along with a very colorful version
        term = TestTerminal()
        attributes = ('bright_red', 'on_bright_blue', 'underline', 'reverse',
                      'red_reverse', 'red_on_white', 'superscript',
                      'subscript', 'on_bright_white')
        term.bright_red('x')
        term.on_bright_blue('x')
        term.underline('x')
        term.reverse('x')
        term.red_reverse('x')
        term.red_on_white('x')
        term.superscript('x')
        term.subscript('x')
        term.on_bright_white('x')

        pgraph_colored = u''.join([
            getattr(term, (attributes[idx % len(attributes)]))(char)
            if char != u' ' else u' '
            for idx, char in enumerate(pgraph)])

        internal_wrapped = textwrap.wrap(pgraph, width=width, **kwargs)
        my_wrapped = term.wrap(pgraph, width=width, **kwargs)
        my_wrapped_colored = term.wrap(pgraph_colored, width=width, **kwargs)

        # ensure we textwrap ascii the same as python
        assert internal_wrapped == my_wrapped

        # ensure content matches for each line, when the sequences are
        # stripped back off of each line
        for line_no, (left, right) in enumerate(
                zip(internal_wrapped, my_wrapped_colored)):
            assert left == term.strip_seqs(right)

        # ensure our colored textwrap is the same paragraph length
        assert (len(internal_wrapped) == len(my_wrapped_colored))

    child(width=many_columns, kwargs=kwargs,
          pgraph=u' Z! a bc defghij klmnopqrstuvw<<>>xyz012345678900 '*2)
    child(width=many_columns, kwargs=kwargs, pgraph=u'a bb ccc')


def test_multiline():
    """Test that text wrapping matches internal extra options."""

    @as_subprocess
    def child():
        # build a test paragraph, along with a very colorful version
        term = TestTerminal()
        given_string = ('\n' + (32 * 'A') + '\n' +
                        (32 * 'B') + '\n' +
                        (32 * 'C') + '\n\n')
        expected = [
            '',
            'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
            'AA',
            'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
            'BB',
            'CCCCCCCCCCCCCCCCCCCCCCCCCCCCCC',
            'CC',
            '',
        ]
        result = term.wrap(given_string, width=30)
        assert expected == result

    child()
