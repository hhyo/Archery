# -*- coding: utf-8 -*-
"Tests for keyboard support."
# std imports
import functools
import tempfile
import signal
import curses
#import time
import math
import tty   # NOQA
import pty
import sys
import os

# local
from .accessories import (
    init_subproc_coverage,
    read_until_eof,
    read_until_semaphore,
    SEND_SEMAPHORE,
    RECV_SEMAPHORE,
    as_subprocess,
    TestTerminal,
    SEMAPHORE,
    all_terms,
    echo_off,
)

# 3rd-party
import pytest
import mock
import six

if sys.version_info[0] == 3:
    unichr = chr


#@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
#                    reason="TEST_QUICK specified")
#def test_kbhit_interrupted():
#    "kbhit() should not be interrupted with a signal handler."
#    pid, master_fd = pty.fork()
#    if pid == 0:
#        cov = init_subproc_coverage('test_kbhit_interrupted')
#
#        # child pauses, writes semaphore and begins awaiting input
#        global got_sigwinch
#        got_sigwinch = False
#
#        def on_resize(sig, action):
#            global got_sigwinch
#            got_sigwinch = True
#
#        term = TestTerminal()
#        signal.signal(signal.SIGWINCH, on_resize)
#        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
#        os.write(sys.__stdout__.fileno(), SEMAPHORE)
#        with term.raw():
#            assert term.inkey(timeout=1.05) == u''
#        os.write(sys.__stdout__.fileno(), b'complete')
#        assert got_sigwinch
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        os.write(master_fd, SEND_SEMAPHORE)
#        read_until_semaphore(master_fd)
#        stime = time.time()
#        os.kill(pid, signal.SIGWINCH)
#        output = read_until_eof(master_fd)
#
#    pid, status = os.waitpid(pid, 0)
#    assert output == u'complete'
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 1.0
#
#
#@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
#                    reason="TEST_QUICK specified")
#def test_kbhit_interrupted_nonetype():
#    "kbhit() should also allow interruption with timeout of None."
#    pid, master_fd = pty.fork()
#    if pid == 0:
#        cov = init_subproc_coverage('test_kbhit_interrupted_nonetype')
#
#        # child pauses, writes semaphore and begins awaiting input
#        global got_sigwinch
#        got_sigwinch = False
#
#        def on_resize(sig, action):
#            global got_sigwinch
#            got_sigwinch = True
#
#        term = TestTerminal()
#        signal.signal(signal.SIGWINCH, on_resize)
#        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
#        os.write(sys.__stdout__.fileno(), SEMAPHORE)
#        with term.raw():
#            term.inkey(timeout=1)
#        os.write(sys.__stdout__.fileno(), b'complete')
#        assert got_sigwinch
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        os.write(master_fd, SEND_SEMAPHORE)
#        read_until_semaphore(master_fd)
#        stime = time.time()
#        time.sleep(0.05)
#        os.kill(pid, signal.SIGWINCH)
#        output = read_until_eof(master_fd)
#
#    pid, status = os.waitpid(pid, 0)
#    assert output == u'complete'
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 1.0


def test_break_input_no_kb():
    "cbreak() should not call tty.setcbreak() without keyboard."
    @as_subprocess
    def child():
        with tempfile.NamedTemporaryFile() as stream:
            term = TestTerminal(stream=stream)
            with mock.patch("tty.setcbreak") as mock_setcbreak:
                with term.cbreak():
                    assert not mock_setcbreak.called
                assert term._keyboard_fd is None
    child()


def test_raw_input_no_kb():
    "raw should not call tty.setraw() without keyboard."
    @as_subprocess
    def child():
        with tempfile.NamedTemporaryFile() as stream:
            term = TestTerminal(stream=stream)
            with mock.patch("tty.setraw") as mock_setraw:
                with term.raw():
                    assert not mock_setraw.called
            assert term._keyboard_fd is None
    child()


def test_raw_input_with_kb():
    "raw should call tty.setraw() when with keyboard."
    @as_subprocess
    def child():
        term = TestTerminal()
        assert term._keyboard_fd is not None
        with mock.patch("tty.setraw") as mock_setraw:
            with term.raw():
                assert mock_setraw.called
    child()


def test_notty_kb_is_None():
    "term._keyboard_fd should be None when os.isatty returns False."
    # in this scenerio, stream is sys.__stdout__,
    # but os.isatty(0) is False,
    # such as when piping output to less(1)
    @as_subprocess
    def child():
        with mock.patch("os.isatty") as mock_isatty:
            mock_isatty.return_value = False
            term = TestTerminal()
            assert term._keyboard_fd is None
    child()


#def test_kbhit_no_kb():
#    "kbhit() always immediately returns False without a keyboard."
#    @as_subprocess
#    def child():
#        term = TestTerminal(stream=six.StringIO())
#        stime = time.time()
#        assert term._keyboard_fd is None
#        assert not term.kbhit(timeout=1.1)
#        assert math.floor(time.time() - stime) == 1.0
#    child()
#
#
#def test_keystroke_0s_cbreak_noinput():
#    "0-second keystroke without input; '' should be returned."
#    @as_subprocess
#    def child():
#        term = TestTerminal()
#        with term.cbreak():
#            stime = time.time()
#            inp = term.inkey(timeout=0)
#            assert (inp == u'')
#            assert (math.floor(time.time() - stime) == 0.0)
#    child()
#
#
#def test_keystroke_0s_cbreak_noinput_nokb():
#    "0-second keystroke without data in input stream and no keyboard/tty."
#    @as_subprocess
#    def child():
#        term = TestTerminal(stream=six.StringIO())
#        with term.cbreak():
#            stime = time.time()
#            inp = term.inkey(timeout=0)
#            assert (inp == u'')
#            assert (math.floor(time.time() - stime) == 0.0)
#    child()
#
#
#@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
#                    reason="TEST_QUICK specified")
#def test_keystroke_1s_cbreak_noinput():
#    "1-second keystroke without input; '' should be returned after ~1 second."
#    @as_subprocess
#    def child():
#        term = TestTerminal()
#        with term.cbreak():
#            stime = time.time()
#            inp = term.inkey(timeout=1)
#            assert (inp == u'')
#            assert (math.floor(time.time() - stime) == 1.0)
#    child()
#
#
#@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
#                    reason="TEST_QUICK specified")
#def test_keystroke_1s_cbreak_noinput_nokb():
#    "1-second keystroke without input or keyboard."
#    @as_subprocess
#    def child():
#        term = TestTerminal(stream=six.StringIO())
#        with term.cbreak():
#            stime = time.time()
#            inp = term.inkey(timeout=1)
#            assert (inp == u'')
#            assert (math.floor(time.time() - stime) == 1.0)
#    child()
#
#
#def test_keystroke_0s_cbreak_with_input():
#    "0-second keystroke with input; Keypress should be immediately returned."
#    pid, master_fd = pty.fork()
#    if pid == 0:
#        cov = init_subproc_coverage('test_keystroke_0s_cbreak_with_input')
#        # child pauses, writes semaphore and begins awaiting input
#        term = TestTerminal()
#        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
#        os.write(sys.__stdout__.fileno(), SEMAPHORE)
#        with term.cbreak():
#            inp = term.inkey(timeout=0)
#            os.write(sys.__stdout__.fileno(), inp.encode('utf-8'))
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        os.write(master_fd, SEND_SEMAPHORE)
#        os.write(master_fd, u'x'.encode('ascii'))
#        read_until_semaphore(master_fd)
#        stime = time.time()
#        output = read_until_eof(master_fd)
#
#    pid, status = os.waitpid(pid, 0)
#    assert output == u'x'
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 0.0
#
#
#def test_keystroke_cbreak_with_input_slowly():
#    "0-second keystroke with input; Keypress should be immediately returned."
#    pid, master_fd = pty.fork()
#    if pid == 0:
#        cov = init_subproc_coverage('test_keystroke_cbreak_with_input_slowly')
#        # child pauses, writes semaphore and begins awaiting input
#        term = TestTerminal()
#        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
#        os.write(sys.__stdout__.fileno(), SEMAPHORE)
#        with term.cbreak():
#            while True:
#                inp = term.inkey(timeout=0.5)
#                os.write(sys.__stdout__.fileno(), inp.encode('utf-8'))
#                if inp == 'X':
#                    break
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        os.write(master_fd, SEND_SEMAPHORE)
#        os.write(master_fd, u'a'.encode('ascii'))
#        time.sleep(0.1)
#        os.write(master_fd, u'b'.encode('ascii'))
#        time.sleep(0.1)
#        os.write(master_fd, u'cdefgh'.encode('ascii'))
#        time.sleep(0.1)
#        os.write(master_fd, u'X'.encode('ascii'))
#        read_until_semaphore(master_fd)
#        stime = time.time()
#        output = read_until_eof(master_fd)
#
#    pid, status = os.waitpid(pid, 0)
#    assert output == u'abcdefghX'
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 0.0
#
#
#def test_keystroke_0s_cbreak_multibyte_utf8():
#    "0-second keystroke with multibyte utf-8 input; should decode immediately."
#    # utf-8 bytes represent "latin capital letter upsilon".
#    pid, master_fd = pty.fork()
#    if pid == 0:  # child
#        cov = init_subproc_coverage('test_keystroke_0s_cbreak_multibyte_utf8')
#        term = TestTerminal()
#        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
#        os.write(sys.__stdout__.fileno(), SEMAPHORE)
#        with term.cbreak():
#            inp = term.inkey(timeout=0)
#            os.write(sys.__stdout__.fileno(), inp.encode('utf-8'))
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        os.write(master_fd, SEND_SEMAPHORE)
#        os.write(master_fd, u'\u01b1'.encode('utf-8'))
#        read_until_semaphore(master_fd)
#        stime = time.time()
#        output = read_until_eof(master_fd)
#    pid, status = os.waitpid(pid, 0)
#    assert output == u'Ʊ'
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 0.0
#
#
#@pytest.mark.skipif(os.environ.get('TRAVIS', None) is not None,
#                    reason="travis-ci does not handle ^C very well.")
#def test_keystroke_0s_raw_input_ctrl_c():
#    "0-second keystroke with raw allows receiving ^C."
#    pid, master_fd = pty.fork()
#    if pid == 0:  # child
#        cov = init_subproc_coverage('test_keystroke_0s_raw_input_ctrl_c')
#        term = TestTerminal()
#        read_until_semaphore(sys.__stdin__.fileno(), semaphore=SEMAPHORE)
#        with term.raw():
#            os.write(sys.__stdout__.fileno(), RECV_SEMAPHORE)
#            inp = term.inkey(timeout=0)
#            os.write(sys.__stdout__.fileno(), inp.encode('latin1'))
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        os.write(master_fd, SEND_SEMAPHORE)
#        # ensure child is in raw mode before sending ^C,
#        read_until_semaphore(master_fd)
#        os.write(master_fd, u'\x03'.encode('latin1'))
#        stime = time.time()
#        output = read_until_eof(master_fd)
#    pid, status = os.waitpid(pid, 0)
#    assert (output == u'\x03' or
#            output == u'' and not os.isatty(0))
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 0.0
#
#
#def test_keystroke_0s_cbreak_sequence():
#    "0-second keystroke with multibyte sequence; should decode immediately."
#    pid, master_fd = pty.fork()
#    if pid == 0:  # child
#        cov = init_subproc_coverage('test_keystroke_0s_cbreak_sequence')
#        term = TestTerminal()
#        os.write(sys.__stdout__.fileno(), SEMAPHORE)
#        with term.cbreak():
#            inp = term.inkey(timeout=0)
#            os.write(sys.__stdout__.fileno(), inp.name.encode('ascii'))
#            sys.stdout.flush()
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        os.write(master_fd, u'\x1b[D'.encode('ascii'))
#        read_until_semaphore(master_fd)
#        stime = time.time()
#        output = read_until_eof(master_fd)
#    pid, status = os.waitpid(pid, 0)
#    assert output == u'KEY_LEFT'
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 0.0
#
#
#@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
#                    reason="TEST_QUICK specified")
#def test_keystroke_1s_cbreak_with_input():
#    "1-second keystroke w/multibyte sequence; should return after ~1 second."
#    pid, master_fd = pty.fork()
#    if pid == 0:  # child
#        cov = init_subproc_coverage('test_keystroke_1s_cbreak_with_input')
#        term = TestTerminal()
#        os.write(sys.__stdout__.fileno(), SEMAPHORE)
#        with term.cbreak():
#            inp = term.inkey(timeout=3)
#            os.write(sys.__stdout__.fileno(), inp.name.encode('utf-8'))
#            sys.stdout.flush()
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        read_until_semaphore(master_fd)
#        stime = time.time()
#        time.sleep(1)
#        os.write(master_fd, u'\x1b[C'.encode('ascii'))
#        output = read_until_eof(master_fd)
#
#    pid, status = os.waitpid(pid, 0)
#    assert output == u'KEY_RIGHT'
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 1.0
#
#
#@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
#                    reason="TEST_QUICK specified")
#def test_esc_delay_cbreak_035():
#    "esc_delay will cause a single ESC (\\x1b) to delay for 0.35."
#    pid, master_fd = pty.fork()
#    if pid == 0:  # child
#        cov = init_subproc_coverage('test_esc_delay_cbreak_035')
#        term = TestTerminal()
#        os.write(sys.__stdout__.fileno(), SEMAPHORE)
#        with term.cbreak():
#            stime = time.time()
#            inp = term.inkey(timeout=5)
#            measured_time = (time.time() - stime) * 100
#            os.write(sys.__stdout__.fileno(), (
#                '%s %i' % (inp.name, measured_time,)).encode('ascii'))
#            sys.stdout.flush()
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        read_until_semaphore(master_fd)
#        stime = time.time()
#        os.write(master_fd, u'\x1b'.encode('ascii'))
#        key_name, duration_ms = read_until_eof(master_fd).split()
#
#    pid, status = os.waitpid(pid, 0)
#    assert key_name == u'KEY_ESCAPE'
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 0.0
#    assert 34 <= int(duration_ms) <= 45, duration_ms
#
#
#@pytest.mark.skipif(os.environ.get('TEST_QUICK', None) is not None,
#                    reason="TEST_QUICK specified")
#def test_esc_delay_cbreak_135():
#    "esc_delay=1.35 will cause a single ESC (\\x1b) to delay for 1.35."
#    pid, master_fd = pty.fork()
#    if pid == 0:  # child
#        cov = init_subproc_coverage('test_esc_delay_cbreak_135')
#        term = TestTerminal()
#        os.write(sys.__stdout__.fileno(), SEMAPHORE)
#        with term.cbreak():
#            stime = time.time()
#            inp = term.inkey(timeout=5, esc_delay=1.35)
#            measured_time = (time.time() - stime) * 100
#            os.write(sys.__stdout__.fileno(), (
#                '%s %i' % (inp.name, measured_time,)).encode('ascii'))
#            sys.stdout.flush()
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        read_until_semaphore(master_fd)
#        stime = time.time()
#        os.write(master_fd, u'\x1b'.encode('ascii'))
#        key_name, duration_ms = read_until_eof(master_fd).split()
#
#    pid, status = os.waitpid(pid, 0)
#    assert key_name == u'KEY_ESCAPE'
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 1.0
#    assert 134 <= int(duration_ms) <= 145, int(duration_ms)
#
#
#def test_esc_delay_cbreak_timout_0():
#    """esc_delay still in effect with timeout of 0 ("nonblocking")."""
#    pid, master_fd = pty.fork()
#    if pid == 0:  # child
#        cov = init_subproc_coverage('test_esc_delay_cbreak_timout_0')
#        term = TestTerminal()
#        os.write(sys.__stdout__.fileno(), SEMAPHORE)
#        with term.cbreak():
#            stime = time.time()
#            inp = term.inkey(timeout=0)
#            measured_time = (time.time() - stime) * 100
#            os.write(sys.__stdout__.fileno(), (
#                '%s %i' % (inp.name, measured_time,)).encode('ascii'))
#            sys.stdout.flush()
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        os.write(master_fd, u'\x1b'.encode('ascii'))
#        read_until_semaphore(master_fd)
#        stime = time.time()
#        key_name, duration_ms = read_until_eof(master_fd).split()
#
#    pid, status = os.waitpid(pid, 0)
#    assert key_name == u'KEY_ESCAPE'
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 0.0
#    assert 34 <= int(duration_ms) <= 45, int(duration_ms)
#
#
#def test_esc_delay_cbreak_nonprefix_sequence():
#    "ESC a (\\x1ba) will return an ESC immediately"
#    pid, master_fd = pty.fork()
#    if pid is 0:  # child
#        cov = init_subproc_coverage('test_esc_delay_cbreak_nonprefix_sequence')
#        term = TestTerminal()
#        os.write(sys.__stdout__.fileno(), SEMAPHORE)
#        with term.cbreak():
#            stime = time.time()
#            esc = term.inkey(timeout=5)
#            inp = term.inkey(timeout=5)
#            measured_time = (time.time() - stime) * 100
#            os.write(sys.__stdout__.fileno(), (
#                '%s %s %i' % (esc.name, inp, measured_time,)).encode('ascii'))
#            sys.stdout.flush()
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        read_until_semaphore(master_fd)
#        stime = time.time()
#        os.write(master_fd, u'\x1ba'.encode('ascii'))
#        key1_name, key2, duration_ms = read_until_eof(master_fd).split()
#
#    pid, status = os.waitpid(pid, 0)
#    assert key1_name == u'KEY_ESCAPE'
#    assert key2 == u'a'
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 0.0
#    assert -1 <= int(duration_ms) <= 15, duration_ms
#
#
#def test_esc_delay_cbreak_prefix_sequence():
#    "An unfinished multibyte sequence (\\x1b[) will delay an ESC by .35 "
#    pid, master_fd = pty.fork()
#    if pid is 0:  # child
#        cov = init_subproc_coverage('test_esc_delay_cbreak_prefix_sequence')
#        term = TestTerminal()
#        os.write(sys.__stdout__.fileno(), SEMAPHORE)
#        with term.cbreak():
#            stime = time.time()
#            esc = term.inkey(timeout=5)
#            inp = term.inkey(timeout=5)
#            measured_time = (time.time() - stime) * 100
#            os.write(sys.__stdout__.fileno(), (
#                '%s %s %i' % (esc.name, inp, measured_time,)).encode('ascii'))
#            sys.stdout.flush()
#        if cov is not None:
#            cov.stop()
#            cov.save()
#        os._exit(0)
#
#    with echo_off(master_fd):
#        read_until_semaphore(master_fd)
#        stime = time.time()
#        os.write(master_fd, u'\x1b['.encode('ascii'))
#        key1_name, key2, duration_ms = read_until_eof(master_fd).split()
#
#    pid, status = os.waitpid(pid, 0)
#    assert key1_name == u'KEY_ESCAPE'
#    assert key2 == u'['
#    assert os.WEXITSTATUS(status) == 0
#    assert math.floor(time.time() - stime) == 0.0
#    assert 34 <= int(duration_ms) <= 45, duration_ms
#
#
#def test_get_location_0s():
#    "0-second get_location call without response."
#    @as_subprocess
#    def child():
#        term = TestTerminal(stream=six.StringIO())
#        stime = time.time()
#        y, x = term.get_location(timeout=0)
#        assert (math.floor(time.time() - stime) == 0.0)
#        assert (y, x) == (-1, -1)
#    child()
#
#
#def test_get_location_0s_under_raw():
#    "0-second get_location call without response under raw mode."
#    @as_subprocess
#    def child():
#        term = TestTerminal(stream=six.StringIO())
#        with term.raw():
#            stime = time.time()
#            y, x = term.get_location(timeout=0)
#            assert (math.floor(time.time() - stime) == 0.0)
#            assert (y, x) == (-1, -1)
#    child()
#
#
#def test_get_location_0s_reply_via_ungetch():
#    "0-second get_location call with response."
#    @as_subprocess
#    def child():
#        term = TestTerminal(stream=six.StringIO())
#        stime = time.time()
#        # monkey patch in an invalid response !
#        term.ungetch(u'\x1b[10;10R')
#
#        y, x = term.get_location(timeout=0.01)
#        assert (math.floor(time.time() - stime) == 0.0)
#        assert (y, x) == (10, 10)
#    child()
#
#
#def test_get_location_0s_reply_via_ungetch_under_raw():
#    "0-second get_location call with response under raw mode."
#    @as_subprocess
#    def child():
#        term = TestTerminal(stream=six.StringIO())
#        with term.raw():
#            stime = time.time()
#            # monkey patch in an invalid response !
#            term.ungetch(u'\x1b[10;10R')
#
#            y, x = term.get_location(timeout=0.01)
#            assert (math.floor(time.time() - stime) == 0.0)
#            assert (y, x) == (10, 10)
#    child()


def test_keystroke_default_args():
    "Test keyboard.Keystroke constructor with default arguments."
    from blessed.keyboard import Keystroke
    ks = Keystroke()
    assert ks._name is None
    assert ks.name == ks._name
    assert ks._code is None
    assert ks.code == ks._code
    assert u'x' == u'x' + ks
    assert not ks.is_sequence
    assert repr(ks) in ("u''",  # py26, 27
                        "''",)  # py33


def test_a_keystroke():
    "Test keyboard.Keystroke constructor with set arguments."
    from blessed.keyboard import Keystroke
    ks = Keystroke(ucs=u'x', code=1, name=u'the X')
    assert ks._name == u'the X'
    assert ks.name == ks._name
    assert ks._code == 1
    assert ks.code == ks._code
    assert u'xx' == u'x' + ks
    assert ks.is_sequence
    assert repr(ks) == "the X"


def test_get_keyboard_codes():
    "Test all values returned by get_keyboard_codes are from curses."
    from blessed.keyboard import (
        get_keyboard_codes,
        CURSES_KEYCODE_OVERRIDE_MIXIN,
    )
    exemptions = dict(CURSES_KEYCODE_OVERRIDE_MIXIN)
    for value, keycode in get_keyboard_codes().items():
        if keycode in exemptions:
            assert value == exemptions[keycode]
            continue
        assert hasattr(curses, keycode)
        assert getattr(curses, keycode) == value


def test_alternative_left_right():
    "Test _alternative_left_right behavior for space/backspace."
    from blessed.keyboard import _alternative_left_right
    term = mock.Mock()
    term._cuf1 = u''
    term._cub1 = u''
    assert not bool(_alternative_left_right(term))
    term._cuf1 = u' '
    term._cub1 = u'\b'
    assert not bool(_alternative_left_right(term))
    term._cuf1 = u'seq-right'
    term._cub1 = u'seq-left'
    assert (_alternative_left_right(term) == {
        u'seq-right': curses.KEY_RIGHT,
        u'seq-left': curses.KEY_LEFT})


def test_cuf1_and_cub1_as_RIGHT_LEFT(all_terms):
    "Test that cuf1 and cub1 are assigned KEY_RIGHT and KEY_LEFT."
    from blessed.keyboard import get_keyboard_sequences

    @as_subprocess
    def child(kind):
        term = TestTerminal(kind=kind, force_styling=True)
        keymap = get_keyboard_sequences(term)
        if term._cuf1:
            assert term._cuf1 in keymap
            assert keymap[term._cuf1] == term.KEY_RIGHT
        if term._cub1:
            assert term._cub1 in keymap
            if term._cub1 == '\b':
                assert keymap[term._cub1] == term.KEY_BACKSPACE
            else:
                assert keymap[term._cub1] == term.KEY_LEFT

    child(all_terms)


def test_get_keyboard_sequences_sort_order():
    "ordereddict ensures sequences are ordered longest-first."
    @as_subprocess
    def child(kind):
        term = TestTerminal(kind=kind, force_styling=True)
        maxlen = None
        for sequence, code in term._keymap.items():
            if maxlen is not None:
                assert len(sequence) <= maxlen
            assert sequence
            maxlen = len(sequence)
    child(kind='xterm-256color')


def test_get_keyboard_sequence(monkeypatch):
    "Test keyboard.get_keyboard_sequence. "
    import blessed.keyboard

    (KEY_SMALL, KEY_LARGE, KEY_MIXIN) = range(3)
    (CAP_SMALL, CAP_LARGE) = 'cap-small cap-large'.split()
    (SEQ_SMALL, SEQ_LARGE, SEQ_MIXIN, SEQ_ALT_CUF1, SEQ_ALT_CUB1) = (
        b'seq-small-a',
        b'seq-large-abcdefg',
        b'seq-mixin',
        b'seq-alt-cuf1',
        b'seq-alt-cub1_')

    # patch curses functions
    monkeypatch.setattr(curses, 'tigetstr',
                        lambda cap: {CAP_SMALL: SEQ_SMALL,
                                     CAP_LARGE: SEQ_LARGE}[cap])

    monkeypatch.setattr(blessed.keyboard, 'capability_names',
                        dict(((KEY_SMALL, CAP_SMALL,),
                              (KEY_LARGE, CAP_LARGE,))))

    # patch global sequence mix-in
    monkeypatch.setattr(blessed.keyboard,
                        'DEFAULT_SEQUENCE_MIXIN', (
                            (SEQ_MIXIN.decode('latin1'), KEY_MIXIN),))

    # patch for _alternative_left_right
    term = mock.Mock()
    term._cuf1 = SEQ_ALT_CUF1.decode('latin1')
    term._cub1 = SEQ_ALT_CUB1.decode('latin1')
    keymap = blessed.keyboard.get_keyboard_sequences(term)

    assert list(keymap.items()) == [
        (SEQ_LARGE.decode('latin1'), KEY_LARGE),
        (SEQ_ALT_CUB1.decode('latin1'), curses.KEY_LEFT),
        (SEQ_ALT_CUF1.decode('latin1'), curses.KEY_RIGHT),
        (SEQ_SMALL.decode('latin1'), KEY_SMALL),
        (SEQ_MIXIN.decode('latin1'), KEY_MIXIN)]


def test_resolve_sequence():
    "Test resolve_sequence for order-dependent mapping."
    from blessed.keyboard import resolve_sequence, OrderedDict
    mapper = OrderedDict(((u'SEQ1', 1),
                          (u'SEQ2', 2),
                          # takes precedence over LONGSEQ, first-match
                          (u'KEY_LONGSEQ_longest', 3),
                          (u'LONGSEQ', 4),
                          # wont match, LONGSEQ is first-match in this order
                          (u'LONGSEQ_longer', 5),
                          # falls through for L{anything_else}
                          (u'L', 6)))
    codes = {1: u'KEY_SEQ1',
             2: u'KEY_SEQ2',
             3: u'KEY_LONGSEQ_longest',
             4: u'KEY_LONGSEQ',
             5: u'KEY_LONGSEQ_longer',
             6: u'KEY_L'}
    ks = resolve_sequence(u'', mapper, codes)
    assert ks == u''
    assert ks.name is None
    assert ks.code == None
    assert not ks.is_sequence
    assert repr(ks) in ("u''",  # py26, 27
                        "''",)  # py33

    ks = resolve_sequence(u'notfound', mapper=mapper, codes=codes)
    assert ks == u'n'
    assert ks.name is None
    assert ks.code is None
    assert not ks.is_sequence
    assert repr(ks) in (u"u'n'", "'n'",)

    ks = resolve_sequence(u'SEQ1', mapper, codes)
    assert ks == u'SEQ1'
    assert ks.name == u'KEY_SEQ1'
    assert ks.code == 1
    assert ks.is_sequence
    assert repr(ks) in (u"KEY_SEQ1", "KEY_SEQ1")

    ks = resolve_sequence(u'LONGSEQ_longer', mapper, codes)
    assert ks == u'LONGSEQ'
    assert ks.name == u'KEY_LONGSEQ'
    assert ks.code == 4
    assert ks.is_sequence
    assert repr(ks) in (u"KEY_LONGSEQ", "KEY_LONGSEQ")

    ks = resolve_sequence(u'LONGSEQ', mapper, codes)
    assert ks == u'LONGSEQ'
    assert ks.name == u'KEY_LONGSEQ'
    assert ks.code == 4
    assert ks.is_sequence
    assert repr(ks) in (u"KEY_LONGSEQ", "KEY_LONGSEQ")

    ks = resolve_sequence(u'Lxxxxx', mapper, codes)
    assert ks == u'L'
    assert ks.name == u'KEY_L'
    assert ks.code == 6
    assert ks.is_sequence
    assert repr(ks) in (u"KEY_L", "KEY_L")


def test_keyboard_prefixes():
    "Test keyboard.prefixes"
    from blessed.keyboard import get_leading_prefixes
    keys = ['abc', 'abdf', 'e', 'jkl']
    pfs = get_leading_prefixes(keys)
    assert pfs == set([u'a', u'ab', u'abd', u'j', u'jk'])


def test_keypad_mixins_and_aliases():
    """ Test PC-Style function key translations when in ``keypad`` mode."""
    # Key     plain   app     modified
    # Up      ^[[A    ^[OA    ^[[1;mA
    # Down    ^[[B    ^[OB    ^[[1;mB
    # Right   ^[[C    ^[OC    ^[[1;mC
    # Left    ^[[D    ^[OD    ^[[1;mD
    # End     ^[[F    ^[OF    ^[[1;mF
    # Home    ^[[H    ^[OH    ^[[1;mH
    @as_subprocess
    def child(kind):
        term = TestTerminal(kind=kind, force_styling=True)
        from blessed.keyboard import resolve_sequence

        resolve = functools.partial(resolve_sequence,
                                    mapper=term._keymap,
                                    codes=term._keycodes)

        assert resolve(unichr(10)).name == "KEY_ENTER"
        assert resolve(unichr(13)).name == "KEY_ENTER"
        assert resolve(unichr(8)).name == "KEY_BACKSPACE"
        assert resolve(unichr(9)).name == "KEY_TAB"
        assert resolve(unichr(27)).name == "KEY_ESCAPE"
        assert resolve(unichr(127)).name == "KEY_DELETE"
        assert resolve(u"\x1b[A").name == "KEY_UP"
        assert resolve(u"\x1b[B").name == "KEY_DOWN"
        assert resolve(u"\x1b[C").name == "KEY_RIGHT"
        assert resolve(u"\x1b[D").name == "KEY_LEFT"
        assert resolve(u"\x1b[U").name == "KEY_PGDOWN"
        assert resolve(u"\x1b[V").name == "KEY_PGUP"
        assert resolve(u"\x1b[H").name == "KEY_HOME"
        assert resolve(u"\x1b[F").name == "KEY_END"
        assert resolve(u"\x1b[K").name == "KEY_END"
        assert resolve(u"\x1bOM").name == "KEY_ENTER"
        assert resolve(u"\x1bOj").name == "KEY_KP_MULTIPLY"
        assert resolve(u"\x1bOk").name == "KEY_KP_ADD"
        assert resolve(u"\x1bOl").name == "KEY_KP_SEPARATOR"
        assert resolve(u"\x1bOm").name == "KEY_KP_SUBTRACT"
        assert resolve(u"\x1bOn").name == "KEY_KP_DECIMAL"
        assert resolve(u"\x1bOo").name == "KEY_KP_DIVIDE"
        assert resolve(u"\x1bOX").name == "KEY_KP_EQUAL"
        assert resolve(u"\x1bOp").name == "KEY_KP_0"
        assert resolve(u"\x1bOq").name == "KEY_KP_1"
        assert resolve(u"\x1bOr").name == "KEY_KP_2"
        assert resolve(u"\x1bOs").name == "KEY_KP_3"
        assert resolve(u"\x1bOt").name == "KEY_KP_4"
        assert resolve(u"\x1bOu").name == "KEY_KP_5"
        assert resolve(u"\x1bOv").name == "KEY_KP_6"
        assert resolve(u"\x1bOw").name == "KEY_KP_7"
        assert resolve(u"\x1bOx").name == "KEY_KP_8"
        assert resolve(u"\x1bOy").name == "KEY_KP_9"
        assert resolve(u"\x1b[1~").name == "KEY_FIND"
        assert resolve(u"\x1b[2~").name == "KEY_INSERT"
        assert resolve(u"\x1b[3~").name == "KEY_DELETE"
        assert resolve(u"\x1b[4~").name == "KEY_SELECT"
        assert resolve(u"\x1b[5~").name == "KEY_PGUP"
        assert resolve(u"\x1b[6~").name == "KEY_PGDOWN"
        assert resolve(u"\x1b[7~").name == "KEY_HOME"
        assert resolve(u"\x1b[8~").name == "KEY_END"
        assert resolve(u"\x1b[OA").name == "KEY_UP"
        assert resolve(u"\x1b[OB").name == "KEY_DOWN"
        assert resolve(u"\x1b[OC").name == "KEY_RIGHT"
        assert resolve(u"\x1b[OD").name == "KEY_LEFT"
        assert resolve(u"\x1b[OF").name == "KEY_END"
        assert resolve(u"\x1b[OH").name == "KEY_HOME"
        assert resolve(u"\x1bOP").name == "KEY_F1"
        assert resolve(u"\x1bOQ").name == "KEY_F2"
        assert resolve(u"\x1bOR").name == "KEY_F3"
        assert resolve(u"\x1bOS").name == "KEY_F4"

    child('xterm')
