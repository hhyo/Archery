#
#  SelfTest/Protocol/test_secret_sharing.py: Self-test for secret sharing protocols
#
# ===================================================================
#
# Copyright (c) 2014, Legrandin <helderijs@gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# ===================================================================

from unittest import main, TestCase, TestSuite
from binascii import unhexlify, hexlify

from Crypto.Util.py3compat import *
from Crypto.SelfTest.st_common import list_test_cases

from Crypto.Protocol.SecretSharing import Shamir, _Element, \
                                          _mult_gf2, _div_gf2

class GF2_Tests(TestCase):

    def test_mult_gf2(self):
        # Prove mult by zero
        x = _mult_gf2(0,0)
        self.assertEqual(x, 0)

        # Prove mult by unity
        x = _mult_gf2(34, 1)
        self.assertEqual(x, 34)

        z = 3                       # (x+1)
        y = _mult_gf2(z, z)
        self.assertEqual(y, 5)      # (x+1)^2 = x^2 + 1
        y = _mult_gf2(y, z)
        self.assertEqual(y, 15)     # (x+1)^3 = x^3 + x^2 + x + 1
        y = _mult_gf2(y, z)
        self.assertEqual(y, 17)     # (x+1)^4 = x^4 + 1

        # Prove linearity works
        comps = [1, 4, 128, 2**34]
        sum_comps = 1+4+128+2**34
        y = 908
        z = _mult_gf2(sum_comps, y)
        w = 0
        for x in comps:
            w ^= _mult_gf2(x, y)
        self.assertEqual(w, z)

    def test_div_gf2(self):
        from Crypto.Util.number import size as deg

        x, y = _div_gf2(567, 7)
        self.failUnless(deg(y) < deg(7))

        w = _mult_gf2(x, 7) ^ y
        self.assertEqual(567, w)

        x, y = _div_gf2(7, 567)
        self.assertEqual(x, 0)
        self.assertEqual(y, 7)

class Element_Tests(TestCase):

    def test1(self):
        # Test encondings
        e = _Element(256)
        self.assertEqual(int(e), 256)
        self.assertEqual(e.encode(), bchr(0)*14 + b("\x01\x00"))

        e = _Element(bchr(0)*14 + b("\x01\x10"))
        self.assertEqual(int(e), 0x110)
        self.assertEqual(e.encode(), bchr(0)*14 + b("\x01\x10"))

        # Only 16 byte string are a valid encoding
        self.assertRaises(ValueError, _Element, bchr(0))

    def test2(self):
        # Test addition
        e = _Element(0x10)
        f = _Element(0x0A)
        self.assertEqual(int(e+f), 0x1A)

    def test3(self):
        # Test multiplication
        zero = _Element(0)
        one = _Element(1)
        two = _Element(2)

        x = _Element(6) * zero
        self.assertEqual(int(x), 0)

        x = _Element(6) * one
        self.assertEqual(int(x), 6)

        x = _Element(2**127) * two
        self.assertEqual(int(x), 1 + 2 + 4 + 128)

    def test4(self):
        # Test inversion
        one = _Element(1)

        x = one.inverse()
        self.assertEqual(int(x), 1)

        x = _Element(82323923)
        y = x.inverse()
        self.assertEqual(int(x * y), 1)

class Shamir_Tests(TestCase):

    def test1(self):
        # Test splitting
        shares = Shamir.split(2, 3, bchr(90)*16)
        self.assertEqual(len(shares), 3)
        for index in range(3):
            self.assertEqual(shares[index][0], index+1)
            self.assertEqual(len(shares[index][1]), 16)

    def test2(self):
        # Test recombine

        # These shares were obtained with ssss v0.5:
        # ssss-split -t 2 -n 3 -s 128 -D -x
        secret = b("000102030405060708090a0b0c0d0e0f")
        shares = (
            (1,"0b8cbb92e2a750defa563537d72942a2"),
            (2,"171a7120c941abb4ecb77472ba459753"),
            (3,"1c97c8b12fe3fd6d1ee84b4e6161dbfe")
            )

        bin_shares = []
        for share in shares:
            bin_shares.append((share[0], unhexlify(b(share[1]))))
        result = Shamir.combine(bin_shares)
        self.assertEqual(hexlify(result), secret)

    def test3(self):
        # Loopback split/recombine
        secret = unhexlify(b("000102030405060708090a0b0c0d0e0f"))

        shares = Shamir.split(2, 3, secret)

        secret2 = Shamir.combine(shares[:2])
        self.assertEqual(secret, secret2)

        secret3 = Shamir.combine([ shares[0], shares[2] ])
        self.assertEqual(secret, secret3)

        secret4 = Shamir.combine(shares)
        self.assertEqual(secret, secret4) # One share too many


def get_tests(config={}):
    tests = []
    tests += list_test_cases(GF2_Tests)
    tests += list_test_cases(Element_Tests)
    tests += list_test_cases(Shamir_Tests)
    return tests

if __name__ == '__main__':
    suite = lambda: TestSuite(get_tests())
    main(defaultTest='suite')

