# ===================================================================
#
# Copyright (c) 2016, Legrandin <helderijs@gmail.com>
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

import re
import sys
import binascii

from Crypto.Util._file_system import pycryptodome_filename


def _load_tests(dir_comps, file_in, description, conversions):
    """Load and parse a test vector file

    Return a list of objects, one per group of adjacent
    KV lines or for a single line in the form "[.*]".

    For a group of lines, the object has one attribute per line.
    """

    line_number = 0
    results = []

    class TestVector(object):
        def __init__(self, description, count):
            self.desc = description
            self.count = count
            self.others = []

    test_vector = None
    count = 0
    new_group = True

    while True:
        line_number += 1
        line = file_in.readline()
        if not line:
            if test_vector is not None:
                results.append(test_vector)
            break
        line = line.strip()

        # Skip comments and empty lines
        if line.startswith('#') or not line:
            new_group = True
            continue

        if line.startswith("["):
            if test_vector is not None:
                results.append(test_vector)
            test_vector = None
            results.append(line)
            continue

        if new_group:
            count += 1
            new_group = False
            if test_vector is not None:
                results.append(test_vector)
            test_vector = TestVector("%s (#%d)" % (description, count), count)

        res = re.match("([A-Za-z0-9]+) = ?(.*)", line)
        if not res:
            test_vector.others += [line]
        else:
            token = res.group(1).lower()
            data = res.group(2).lower()

            conversion = conversions.get(token, None)
            if conversion is None:
                if len(data) % 2 != 0:
                    data = "0" + data
                setattr(test_vector, token, binascii.unhexlify(data))
            else:
                setattr(test_vector, token, conversion(data))

        # This line is ignored
    return results

def load_tests(dir_comps, file_name, description, conversions):
    """Load and parse a test vector file

    This function returnis a list of objects, one per group of adjacent
    KV lines or for a single line in the form "[.*]".

    For a group of lines, the object has one attribute per line.
    """
    
    description = "%s test (%s)" % (description, file_name)

    with open(pycryptodome_filename(dir_comps, file_name)) as file_in:
        results = _load_tests(dir_comps, file_in, description, conversions)
    return results
