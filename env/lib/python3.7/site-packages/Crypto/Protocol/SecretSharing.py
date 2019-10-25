#
# SecretSharing.py : distribute a secret amongst a group of participants
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

from Crypto.Util.py3compat import is_native_int
from Crypto.Util import number
from Crypto.Util.number import long_to_bytes, bytes_to_long
from Crypto.Random import get_random_bytes as rng

def _mult_gf2(f1, f2):
    """Multiply two polynomials in GF(2)"""

    # Ensure f2 is the smallest
    if f2 > f1:
        f1, f2 = f2, f1
    z = 0
    while f2:
        if f2 & 1:
            z ^= f1
        f1 <<= 1
        f2 >>= 1
    return z


def _div_gf2(a, b):
    """
    Compute division of polynomials over GF(2).
    Given a and b, it finds two polynomials q and r such that:

    a = b*q + r with deg(r)<deg(b)
    """

    if (a < b):
        return 0, a

    deg = number.size
    q = 0
    r = a
    d = deg(b)
    while deg(r) >= d:
        s = 1 << (deg(r) - d)
        q ^= s
        r ^= _mult_gf2(b, s)
    return (q, r)


class _Element(object):
    """Element of GF(2^128) field"""

    # The irreducible polynomial defining this field is 1+x+x^2+x^7+x^128
    irr_poly = 1 + 2 + 4 + 128 + 2 ** 128

    def __init__(self, encoded_value):
        """Initialize the element to a certain value.

        The value passed as parameter is internally encoded as
        a 128-bit integer, where each bit represents a polynomial
        coefficient. The LSB is the constant coefficient.
        """

        if is_native_int(encoded_value):
            self._value = encoded_value
        elif len(encoded_value) == 16:
            self._value = bytes_to_long(encoded_value)
        else:
            raise ValueError("The encoded value must be an integer or a 16 byte string")

    def __int__(self):
        """Return the field element, encoded as a 128-bit integer."""

        return self._value

    def encode(self):
        """Return the field element, encoded as a 16 byte string."""

        return long_to_bytes(self._value, 16)

    def __mul__(self, factor):

        f1 = self._value
        f2 = factor._value

        # Make sure that f2 is the smallest, to speed up the loop
        if f2 > f1:
            f1, f2 = f2, f1

        if self.irr_poly in (f1, f2):
            return _Element(0)
        mask1 = 2 ** 128
        v, z = f1, 0
        while f2:
            if f2 & 1:
                z ^= v
            v <<= 1
            if v & mask1:
                v ^= self.irr_poly
            f2 >>= 1
        return _Element(z)

    def __add__(self, term):
        return _Element(self._value ^ term._value)

    def inverse(self):
        """Return the inverse of this element in GF(2^128)."""

        # We use the Extended GCD algorithm
        # http://en.wikipedia.org/wiki/Polynomial_greatest_common_divisor

        r0, r1 = self._value, self.irr_poly
        s0, s1 = 1, 0
        while r1 > 0:
            q = _div_gf2(r0, r1)[0]
            r0, r1 = r1, r0 ^ _mult_gf2(q, r1)
            s0, s1 = s1, s0 ^ _mult_gf2(q, s1)
        return _Element(s0)


class Shamir(object):
    """Shamir's secret sharing scheme.

    This class implements the Shamir's secret sharing protocol
    described in his original paper `"How to share a secret"`__.

    All shares are points over a 2-dimensional curve. At least
    *k* points (that is, shares) are required to reconstruct the curve,
    and therefore the secret.

    This implementation is primarilly meant to protect AES128 keys.
    To that end, the secret is associated to a curve in
    the field GF(2^128) defined by the irreducible polynomial
    :math:`x^{128} + x^7 + x^2 + x + 1` (the same used in AES-GCM).
    The shares are always 16 bytes long.

    Data produced by this implementation are compatible to the popular
    `ssss`_ tool if used with 128 bit security (parameter *"-s 128"*)
    and no dispersion (parameter *"-D"*).

    As an example, the following code shows how to protect a file meant
    for 5 people, in such a way that 2 of the 5 are required to
    reassemble it::

        >>> from binascii import hexlify
        >>> from Crypto.Cipher import AES
        >>> from Crypto.Random import get_random_bytes
        >>> from Crypto.Protocol.secret_sharing import Shamir
        >>>
        >>> key = get_random_bytes(16)
        >>> shares = Shamir.split(2, 5, key)
        >>> for idx, share in shares:
        >>>     print "Index #%d: %s" % (idx, hexlify(share))
        >>>
        >>> fi = open("clear_file.txt", "rb")
        >>> fo = open("enc_file.txt", "wb")
        >>>
        >>> cipher = AES.new(key, AES.MODE_EAX)
        >>> ct, tag = cipher.encrypt(fi.read()), cipher.digest()
        >>> fo.write(nonce + tag + ct)

    Each person can be given one share and the encrypted file.

    When 2 people gather together with their shares, the can
    decrypt the file::

        >>> from binascii import unhexlify
        >>> from Crypto.Cipher import AES
        >>> from Crypto.Protocol.secret_sharing import Shamir
        >>>
        >>> shares = []
        >>> for x in range(2):
        >>>     in_str = raw_input("Enter index and share separated by comma: ")
        >>>     idx, share = [ strip(s) for s in in_str.split(",") ]
        >>>     shares.append((idx, unhexlify(share)))
        >>> key = Shamir.combine(shares)
        >>>
        >>> fi = open("enc_file.txt", "rb")
        >>> nonce, tag = [ fi.read(16) for x in range(2) ]
        >>> cipher = AES.new(key, AES.MODE_EAX, nonce)
        >>> try:
        >>>     result = cipher.decrypt(fi.read())
        >>>     cipher.verify(tag)
        >>>     with open("clear_file2.txt", "wb") as fo:
        >>>         fo.write(result)
        >>> except ValueError:
        >>>     print "The shares were incorrect"

    .. attention::
        Reconstruction does not guarantee that the result is authentic.
        In particular, a malicious participant in the scheme has the
        ability to force an algebric transformation on the result by
        manipulating her share.

        It is important to use the scheme in combination with an
        authentication mechanism (the EAX cipher mode in the example).

    .. __: http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.80.8910&rep=rep1&type=pdf
    .. _ssss: http://point-at-infinity.org/ssss/
    """

    @staticmethod
    def split(k, n, secret):
        """Split a secret into *n* shares.

        The secret can be reconstructed later when *k* shares
        out of the original *n* are recombined. Each share
        must be kept confidential to the person it was
        assigned to.

        Each share is associated to an index (starting from 1),
        which must be presented when the secret is recombined.

        Args:
          k (integer):
            The number of shares that must be present in order to reconstruct
            the secret.
          n (integer):
            The total number of shares to create (larger than *k*).
          secret (byte string):
            The 16 byte string (e.g. the AES128 key) to split.

        Return:
            *n* tuples, each containing the unique index (an integer) and
            the share (a byte string, 16 bytes long) meant for a
            participant.
        """

        #
        # We create a polynomial with random coefficients in GF(2^128):
        #
        # p(x) = \sum_{i=0}^{k-1} c_i * x^i
        #
        # c_0 is the encoded secret
        #

        coeffs = [_Element(rng(16)) for i in range(k - 1)]
        coeffs.insert(0, _Element(secret))

        # Each share is y_i = p(x_i) where x_i is the public index
        # associated to each of the n users.

        def make_share(user, coeffs):
            share, x, idx = [_Element(p) for p in (0, 1, user)]
            for coeff in coeffs:
                share += coeff * x
                x *= idx
            return share.encode()

        return [(i, make_share(i, coeffs)) for i in range(1, n + 1)]

    @staticmethod
    def combine(shares):
        """Recombine a secret, if enough shares are presented.

        Args:
          shares (tuples):
            At least *k* tuples, each containin the index (an integer) and
            the share (a byte string, 16 bytes long) that were assigned to
            a participant.

        Return:
            The original secret, as a byte string (16 bytes long).
        """

        #
        # Given k points (x,y), the interpolation polynomial of degree k-1 is:
        #
        # L(x) = \sum_{j=0}^{k-1} y_i * l_j(x)
        #
        # where:
        #
        # l_j(x) = \prod_{ \overset{0 \le m \le k-1}{m \ne j} }
        #          \frac{x - x_m}{x_j - x_m}
        #
        # However, in this case we are purely intersted in the constant
        # coefficient of L(x).
        #

        shares = [[_Element(y) for y in x] for x in shares]

        result = _Element(0)
        k = len(shares)
        for j in range(k):
            x_j, y_j = shares[j]

            coeff_0_l = _Element(0)
            while not int(coeff_0_l):
                coeff_0_l = _Element(rng(16))
            inv = coeff_0_l.inverse()

            for m in range(k):
                x_m = shares[m][0]
                if m != j:
                    t = x_m * (x_j + x_m).inverse()
                    coeff_0_l *= t
            result += y_j * coeff_0_l * inv
        return result.encode()
