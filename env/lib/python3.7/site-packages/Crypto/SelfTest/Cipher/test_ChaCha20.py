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

import os
import re
import unittest
from binascii import hexlify, unhexlify

from Crypto.Util.py3compat import b, tobytes, bchr, _memoryview
from Crypto.Util.strxor import strxor_c
from Crypto.SelfTest.st_common import list_test_cases

from Crypto.Cipher import ChaCha20


class ChaCha20Test(unittest.TestCase):

    def test_new_positive(self):
        cipher = ChaCha20.new(key=b("0")*32, nonce=b"0"*8)
        self.assertEqual(cipher.nonce, b"0" * 8)
        cipher = ChaCha20.new(key=b("0")*32, nonce=b"0"*12)
        self.assertEqual(cipher.nonce, b"0" * 12)

    def test_new_negative(self):
        new = ChaCha20.new
        self.assertRaises(TypeError, new)
        self.assertRaises(TypeError, new, nonce=b("0"))
        self.assertRaises(ValueError, new, nonce=b("0")*8, key=b("0"))
        self.assertRaises(ValueError, new, nonce=b("0"), key=b("0")*32)

    def test_default_nonce(self):
        cipher1 = ChaCha20.new(key=bchr(1) * 32)
        cipher2 = ChaCha20.new(key=bchr(1) * 32)
        self.assertEquals(len(cipher1.nonce), 8)
        self.assertNotEqual(cipher1.nonce, cipher2.nonce)

    def test_eiter_encrypt_or_decrypt(self):
        """Verify that a cipher cannot be used for both decrypting and encrypting"""

        c1 = ChaCha20.new(key=b("5") * 32, nonce=b("6") * 8)
        c1.encrypt(b("8"))
        self.assertRaises(TypeError, c1.decrypt, b("9"))

        c2 = ChaCha20.new(key=b("5") * 32, nonce=b("6") * 8)
        c2.decrypt(b("8"))
        self.assertRaises(TypeError, c2.encrypt, b("9"))

    def test_round_trip(self):
        pt = b("A") * 1024
        c1 = ChaCha20.new(key=b("5") * 32, nonce=b("6") * 8)
        c2 = ChaCha20.new(key=b("5") * 32, nonce=b("6") * 8)
        ct = c1.encrypt(pt)
        self.assertEqual(c2.decrypt(ct), pt)

        self.assertEqual(c1.encrypt(b("")), b(""))
        self.assertEqual(c2.decrypt(b("")), b(""))

    def test_streaming(self):
        """Verify that an arbitrary number of bytes can be encrypted/decrypted"""
        from Crypto.Hash import SHA1

        segments = (1, 3, 5, 7, 11, 17, 23)
        total = sum(segments)

        pt = b("")
        while len(pt) < total:
            pt += SHA1.new(pt).digest()

        cipher1 = ChaCha20.new(key=b("7") * 32, nonce=b("t") * 8)
        ct = cipher1.encrypt(pt)

        cipher2 = ChaCha20.new(key=b("7") * 32, nonce=b("t") * 8)
        cipher3 = ChaCha20.new(key=b("7") * 32, nonce=b("t") * 8)
        idx = 0
        for segment in segments:
            self.assertEqual(cipher2.decrypt(ct[idx:idx+segment]), pt[idx:idx+segment])
            self.assertEqual(cipher3.encrypt(pt[idx:idx+segment]), ct[idx:idx+segment])
            idx += segment

    def test_seek(self):
        cipher1 = ChaCha20.new(key=b("9") * 32, nonce=b("e") * 8)

        offset = 64 * 900 + 7
        pt = b("1") * 64

        cipher1.encrypt(b("0") * offset)
        ct1 = cipher1.encrypt(pt)

        cipher2 = ChaCha20.new(key=b("9") * 32, nonce=b("e") * 8)
        cipher2.seek(offset)
        ct2 = cipher2.encrypt(pt)

        self.assertEquals(ct1, ct2)

    def test_seek_tv(self):
        # Test Vector #4, A.1 from
        # http://tools.ietf.org/html/draft-nir-cfrg-chacha20-poly1305-04
        key = bchr(0) + bchr(255) + bchr(0) * 30
        nonce = bchr(0) * 8
        cipher = ChaCha20.new(key=key, nonce=nonce)
        cipher.seek(64 * 2)
        expected_key_stream = unhexlify(b(
            "72d54dfbf12ec44b362692df94137f32"
            "8fea8da73990265ec1bbbea1ae9af0ca"
            "13b25aa26cb4a648cb9b9d1be65b2c09"
            "24a66c54d545ec1b7374f4872e99f096"
            ))
        ct = cipher.encrypt(bchr(0) * len(expected_key_stream))
        self.assertEqual(expected_key_stream, ct)

    def test_rfc7539(self):
        # from https://tools.ietf.org/html/rfc7539 Annex A.1
        # Each item is: key, nonce, block #, plaintext, ciphertext
        tvs = [
                # Test Vector #1
                (
                    "00"*32,
                    "00"*12,
                    0,
                    "00"*16*4,
                    "76b8e0ada0f13d90405d6ae55386bd28"
                    "bdd219b8a08ded1aa836efcc8b770dc7"
                    "da41597c5157488d7724e03fb8d84a37"
                    "6a43b8f41518a11cc387b669b2ee6586"
                ),
                # Test Vector #2
                (
                    "00"*31 + "01",
                    "00"*11 + "02",
                    1,
                    "416e79207375626d697373696f6e2074"
                    "6f20746865204945544620696e74656e"
                    "6465642062792074686520436f6e7472"
                    "696275746f7220666f72207075626c69"
                    "636174696f6e20617320616c6c206f72"
                    "2070617274206f6620616e2049455446"
                    "20496e7465726e65742d447261667420"
                    "6f722052464320616e6420616e792073"
                    "746174656d656e74206d616465207769"
                    "7468696e2074686520636f6e74657874"
                    "206f6620616e20494554462061637469"
                    "7669747920697320636f6e7369646572"
                    "656420616e20224945544620436f6e74"
                    "7269627574696f6e222e205375636820"
                    "73746174656d656e747320696e636c75"
                    "6465206f72616c2073746174656d656e"
                    "747320696e2049455446207365737369"
                    "6f6e732c2061732077656c6c20617320"
                    "7772697474656e20616e6420656c6563"
                    "74726f6e696320636f6d6d756e696361"
                    "74696f6e73206d61646520617420616e"
                    "792074696d65206f7220706c6163652c"
                    "20776869636820617265206164647265"
                    "7373656420746f",
                    "a3fbf07df3fa2fde4f376ca23e827370"
                    "41605d9f4f4f57bd8cff2c1d4b7955ec"
                    "2a97948bd3722915c8f3d337f7d37005"
                    "0e9e96d647b7c39f56e031ca5eb6250d"
                    "4042e02785ececfa4b4bb5e8ead0440e"
                    "20b6e8db09d881a7c6132f420e527950"
                    "42bdfa7773d8a9051447b3291ce1411c"
                    "680465552aa6c405b7764d5e87bea85a"
                    "d00f8449ed8f72d0d662ab052691ca66"
                    "424bc86d2df80ea41f43abf937d3259d"
                    "c4b2d0dfb48a6c9139ddd7f76966e928"
                    "e635553ba76c5c879d7b35d49eb2e62b"
                    "0871cdac638939e25e8a1e0ef9d5280f"
                    "a8ca328b351c3c765989cbcf3daa8b6c"
                    "cc3aaf9f3979c92b3720fc88dc95ed84"
                    "a1be059c6499b9fda236e7e818b04b0b"
                    "c39c1e876b193bfe5569753f88128cc0"
                    "8aaa9b63d1a16f80ef2554d7189c411f"
                    "5869ca52c5b83fa36ff216b9c1d30062"
                    "bebcfd2dc5bce0911934fda79a86f6e6"
                    "98ced759c3ff9b6477338f3da4f9cd85"
                    "14ea9982ccafb341b2384dd902f3d1ab"
                    "7ac61dd29c6f21ba5b862f3730e37cfd"
                    "c4fd806c22f221"
                ),
                # Test Vector #3
                (
                    "1c9240a5eb55d38af333888604f6b5f0"
                    "473917c1402b80099dca5cbc207075c0",
                    "00"*11 + "02",
                    42,
                    "2754776173206272696c6c69672c2061"
                    "6e642074686520736c6974687920746f"
                    "7665730a446964206779726520616e64"
                    "2067696d626c6520696e207468652077"
                    "6162653a0a416c6c206d696d73792077"
                    "6572652074686520626f726f676f7665"
                    "732c0a416e6420746865206d6f6d6520"
                    "7261746873206f757467726162652e",
                    "62e6347f95ed87a45ffae7426f27a1df"
                    "5fb69110044c0d73118effa95b01e5cf"
                    "166d3df2d721caf9b21e5fb14c616871"
                    "fd84c54f9d65b283196c7fe4f60553eb"
                    "f39c6402c42234e32a356b3e764312a6"
                    "1a5532055716ead6962568f87d3f3f77"
                    "04c6a8d1bcd1bf4d50d6154b6da731b1"
                    "87b58dfd728afa36757a797ac188d1"
                )
        ]

        for tv in tvs:
            key = unhexlify(tv[0])
            nonce = unhexlify(tv[1])
            offset = tv[2] * 64
            pt = unhexlify(tv[3])
            ct_expect = unhexlify(tv[4])

            cipher = ChaCha20.new(key=key, nonce=nonce)
            if offset != 0:
                cipher.seek(offset)
            ct = cipher.encrypt(pt)
            assert(ct == ct_expect)


class ByteArrayTest(unittest.TestCase):
    """Verify we can encrypt or decrypt bytearrays"""

    def runTest(self):

        data = b"0123"
        key = b"9" * 32
        nonce = b"t" * 8

        # Encryption
        data_ba = bytearray(data)
        key_ba = bytearray(key)
        nonce_ba = bytearray(nonce)

        cipher1 = ChaCha20.new(key=key, nonce=nonce)
        ct = cipher1.encrypt(data)

        cipher2 = ChaCha20.new(key=key_ba, nonce=nonce_ba)
        key_ba[:1] = b'\xFF'
        nonce_ba[:1] = b'\xFF'
        ct_test = cipher2.encrypt(data_ba)

        self.assertEqual(ct, ct_test)
        self.assertEqual(cipher1.nonce, cipher2.nonce)

        # Decryption
        key_ba = bytearray(key)
        nonce_ba = bytearray(nonce)
        ct_ba = bytearray(ct)

        cipher3 = ChaCha20.new(key=key_ba, nonce=nonce_ba)
        key_ba[:1] = b'\xFF'
        nonce_ba[:1] = b'\xFF'
        pt_test = cipher3.decrypt(ct_ba)

        self.assertEqual(data, pt_test)


class MemoryviewTest(unittest.TestCase):
    """Verify we can encrypt or decrypt bytearrays"""

    def runTest(self):

        data = b"0123"
        key = b"9" * 32
        nonce = b"t" * 8

        # Encryption
        data_mv = memoryview(bytearray(data))
        key_mv = memoryview(bytearray(key))
        nonce_mv = memoryview(bytearray(nonce))

        cipher1 = ChaCha20.new(key=key, nonce=nonce)
        ct = cipher1.encrypt(data)

        cipher2 = ChaCha20.new(key=key_mv, nonce=nonce_mv)
        key_mv[:1] = b'\xFF'
        nonce_mv[:1] = b'\xFF'
        ct_test = cipher2.encrypt(data_mv)

        self.assertEqual(ct, ct_test)
        self.assertEqual(cipher1.nonce, cipher2.nonce)

        # Decryption
        key_mv = memoryview(bytearray(key))
        nonce_mv = memoryview(bytearray(nonce))
        ct_mv = memoryview(bytearray(ct))

        cipher3 = ChaCha20.new(key=key_mv, nonce=nonce_mv)
        key_mv[:1] = b'\xFF'
        nonce_mv[:1] = b'\xFF'
        pt_test = cipher3.decrypt(ct_mv)

        self.assertEqual(data, pt_test)


class ChaCha20_AGL_NIR(unittest.TestCase):

    # From http://tools.ietf.org/html/draft-agl-tls-chacha20poly1305-04
    # and http://tools.ietf.org/html/draft-nir-cfrg-chacha20-poly1305-04
    tv = [
          ( "00" * 32,
            "00" * 8,
            "76b8e0ada0f13d90405d6ae55386bd28bdd219b8a08ded1aa836efcc"
            "8b770dc7da41597c5157488d7724e03fb8d84a376a43b8f41518a11c"
            "c387b669b2ee6586"
            "9f07e7be5551387a98ba977c732d080d"
            "cb0f29a048e3656912c6533e32ee7aed"
            "29b721769ce64e43d57133b074d839d5"
            "31ed1f28510afb45ace10a1f4b794d6f"
          ),
          ( "00" * 31 + "01",
            "00" * 8,
            "4540f05a9f1fb296d7736e7b208e3c96eb4fe1834688d2604f450952"
            "ed432d41bbe2a0b6ea7566d2a5d1e7e20d42af2c53d792b1c43fea81"
            "7e9ad275ae546963"
            "3aeb5224ecf849929b9d828db1ced4dd"
            "832025e8018b8160b82284f3c949aa5a"
            "8eca00bbb4a73bdad192b5c42f73f2fd"
            "4e273644c8b36125a64addeb006c13a0"
          ),
          ( "00" * 32,
            "00" * 7 + "01",
            "de9cba7bf3d69ef5e786dc63973f653a0b49e015adbff7134fcb7df1"
            "37821031e85a050278a7084527214f73efc7fa5b5277062eb7a0433e"
            "445f41e3"
          ),
          ( "00" * 32,
            "01" + "00" * 7,
            "ef3fdfd6c61578fbf5cf35bd3dd33b8009631634d21e42ac33960bd1"
            "38e50d32111e4caf237ee53ca8ad6426194a88545ddc497a0b466e7d"
            "6bbdb0041b2f586b"
          ),
          ( "000102030405060708090a0b0c0d0e0f101112131415161718191a1b"
            "1c1d1e1f",
            "0001020304050607",
            "f798a189f195e66982105ffb640bb7757f579da31602fc93ec01ac56"
            "f85ac3c134a4547b733b46413042c9440049176905d3be59ea1c53f1"
            "5916155c2be8241a38008b9a26bc35941e2444177c8ade6689de9526"
            "4986d95889fb60e84629c9bd9a5acb1cc118be563eb9b3a4a472f82e"
            "09a7e778492b562ef7130e88dfe031c79db9d4f7c7a899151b9a4750"
            "32b63fc385245fe054e3dd5a97a5f576fe064025d3ce042c566ab2c5"
            "07b138db853e3d6959660996546cc9c4a6eafdc777c040d70eaf46f7"
            "6dad3979e5c5360c3317166a1c894c94a371876a94df7628fe4eaaf2"
            "ccb27d5aaae0ad7ad0f9d4b6ad3b54098746d4524d38407a6deb3ab7"
            "8fab78c9"
          ),
          ( "00" * 32,
            "00" * 7 + "02",
            "c2c64d378cd536374ae204b9ef933fcd"
            "1a8b2288b3dfa49672ab765b54ee27c7"
            "8a970e0e955c14f3a88e741b97c286f7"
            "5f8fc299e8148362fa198a39531bed6d"
          ),
         ]

    def runTest(self):
        for (key, nonce, stream) in self.tv:
            c = ChaCha20.new(key=unhexlify(b(key)), nonce=unhexlify(b(nonce)))
            ct = unhexlify(b(stream))
            pt = b("\x00") * len(ct)
            self.assertEqual(c.encrypt(pt), ct)


class TestOutput(unittest.TestCase):

    def runTest(self):
        # Encrypt/Decrypt data and test output parameter

        key = b'4' * 32
        nonce = b'5' * 8
        cipher = ChaCha20.new(key=key, nonce=nonce)

        pt = b'5' * 16
        ct = cipher.encrypt(pt)

        output = bytearray(16)
        cipher = ChaCha20.new(key=key, nonce=nonce)
        res = cipher.encrypt(pt, output=output)
        self.assertEqual(ct, output)
        self.assertEqual(res, None)
        
        cipher = ChaCha20.new(key=key, nonce=nonce)
        res = cipher.decrypt(ct, output=output)
        self.assertEqual(pt, output)
        self.assertEqual(res, None)

        import sys
        if sys.version[:3] != '2.6':
            output = memoryview(bytearray(16))
            cipher = ChaCha20.new(key=key, nonce=nonce)
            cipher.encrypt(pt, output=output)
            self.assertEqual(ct, output)
        
            cipher = ChaCha20.new(key=key, nonce=nonce)
            cipher.decrypt(ct, output=output)
            self.assertEqual(pt, output)

        cipher = ChaCha20.new(key=key, nonce=nonce)
        self.assertRaises(TypeError, cipher.encrypt, pt, output=b'0'*16)
        
        cipher = ChaCha20.new(key=key, nonce=nonce)
        self.assertRaises(TypeError, cipher.decrypt, ct, output=b'0'*16)

        shorter_output = bytearray(7)
        
        cipher = ChaCha20.new(key=key, nonce=nonce)
        self.assertRaises(ValueError, cipher.encrypt, pt, output=shorter_output)
        
        cipher = ChaCha20.new(key=key, nonce=nonce)
        self.assertRaises(ValueError, cipher.decrypt, ct, output=shorter_output)


def get_tests(config={}):
    tests = []
    tests += list_test_cases(ChaCha20Test)
    tests.append(ChaCha20_AGL_NIR())
    tests.append(ByteArrayTest())

    import sys
    if sys.version[:3] != "2.6":
        tests.append(MemoryviewTest())

    tests.append(TestOutput())

    return tests


if __name__ == '__main__':
    import unittest
    suite = lambda: unittest.TestSuite(get_tests())
    unittest.main(defaultTest='suite')
