# -*- coding: utf-8 -*-

import re
import struct
import binascii
from io import BytesIO

def overlap(i1, i2):
    return i1[0] < i2[1] and i1[1] > i2[0]

def contains(i1, i2):
    return i2[0] >= i1[0] and i2[1] <= i1[1]

class Gtid(object):
    """A mysql GTID is composed of a server-id and a set of right-open
    intervals [a,b), and represent all transactions x that happened on
    server SID such as

        x <= a < b

    The human representation of it, though, is either represented by a
    single transaction number A=a (when only one transaction is covered,
    ie b = a+1)

        SID:A

    Or a closed interval [A,B] for at least two transactions (note, in that
    case, that b=B+1)

        SID:A-B

    We can also have a mix of ranges for a given SID:
        SID:1-2:4:6-74

    For convenience, a Gtid accepts adding Gtid's to it and will merge
    the existing interval representation. Adding TXN 3 to the human
    representation above would produce:

        SID:1-4:6-74

    and adding 5 to this new result:

        SID:1-74

    Adding an already present transaction number (one that overlaps) will
    raise an exception.

    Adding a Gtid with a different SID will raise an exception.
    """
    @staticmethod
    def parse_interval(interval):
        """
        We parse a human-generated string here. So our end value b
        is incremented to conform to the internal representation format.
        """
        m = re.search('^([0-9]+)(?:-([0-9]+))?$', interval)
        if not m:
            raise ValueError('GTID format is incorrect: %r' % (interval, ))
        a = int(m.group(1))
        b = int(m.group(2) or a)
        return (a, b+1)

    @staticmethod
    def parse(gtid):
        m = re.search('^([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})'
                      '((?::[0-9-]+)+)$', gtid)
        if not m:
            raise ValueError('GTID format is incorrect: %r' % (gtid, ))

        sid = m.group(1)
        intervals = m.group(2)

        intervals_parsed = [Gtid.parse_interval(x)
                            for x in intervals.split(':')[1:]]

        return (sid, intervals_parsed)

    def __add_interval(self, itvl):
        """
        Use the internal representation format and add it
        to our intervals, merging if required.
        """
        new = []

        if itvl[0] > itvl[1]:
            raise Exception('Malformed interval %s' % (itvl,))

        if any(overlap(x, itvl) for x in self.intervals):
            raise Exception('Overlapping interval %s' % (itvl,))

        ## Merge: arrange interval to fit existing set
        for existing in sorted(self.intervals):
            if itvl[0] == existing[1]:
                itvl = (existing[0], itvl[1])
                continue

            if itvl[1] == existing[0]:
                itvl = (itvl[0], existing[1])
                continue

            new.append(existing)

        self.intervals = sorted(new + [itvl])

    def __sub_interval(self, itvl):
        """Using the internal representation, remove an interval"""
        new = []

        if itvl[0] > itvl[1]:
            raise Exception('Malformed interval %s' % (itvl,))

        if not any(overlap(x, itvl) for x in self.intervals):
            # No raise
            return

        ## Merge: arrange existing set around interval
        for existing in sorted(self.intervals):
            if overlap(existing, itvl):
                if existing[0] < itvl[0]:
                    new.append((existing[0], itvl[0]))
                if existing[1] > itvl[1]:
                    new.append((itvl[1], existing[1]))
            else:
                new.append(existing)

        self.intervals = new

    def __contains__(self, other):
        if other.sid != self.sid:
            return False

        return all(any(contains(me, them) for me in self.intervals)
                   for them in other.intervals)

    def __init__(self, gtid, sid=None, intervals=[]):
        if sid:
            intervals = intervals
        else:
            sid, intervals = Gtid.parse(gtid)

        self.sid = sid
        self.intervals = []
        for itvl in intervals:
            self.__add_interval(itvl)

    def __add__(self, other):
        """Include the transactions of this gtid. Raise if the
        attempted merge has different SID"""
        if self.sid != other.sid:
            raise Exception('Attempt to merge different SID'
                            '%s != %s' % (self.sid, other.sid))

        result = Gtid(str(self))

        for itvl in other.intervals:
            result.__add_interval(itvl)

        return result

    def __sub__(self, other):
        """Remove intervals. Do not raise, if different SID simply
        ignore"""
        result = Gtid(str(self))
        if self.sid != other.sid:
            return result

        for itvl in other.intervals:
            result.__sub_interval(itvl)

        return result

    def __cmp__(self, other):
        if other.sid != self.sid:
            return cmp(self.sid, other.sid)
        return cmp(self.intervals, other.intervals)

    def __str__(self):
        """We represent the human value here - a single number
        for one transaction, or a closed interval (decrementing b)"""
        return '%s:%s' % (self.sid,
                          ':'.join(('%d-%d' % (x[0], x[1]-1)) if x[0] +1 != x[1]
                                   else str(x[0])
                                   for x in self.intervals))

    def __repr__(self):
        return '<Gtid "%s">' % self

    @property
    def encoded_length(self):
        return (16 +  # sid
                8 +  # n_intervals
                2 *  # stop/start
                8 *  # stop/start mark encoded as int64
                len(self.intervals))

    def encode(self):
        buffer = b''
        # sid
        buffer += binascii.unhexlify(self.sid.replace('-', ''))
        # n_intervals
        buffer += struct.pack('<Q', len(self.intervals))

        for interval in self.intervals:
            # Start position
            buffer += struct.pack('<Q', interval[0])
            # Stop position
            buffer += struct.pack('<Q', interval[1])

        return buffer

    @classmethod
    def decode(cls, payload):
        assert isinstance(payload, BytesIO), \
            'payload is expected to be a BytesIO'
        sid = b''
        sid = sid + binascii.hexlify(payload.read(4))
        sid = sid + b'-'
        sid = sid + binascii.hexlify(payload.read(2))
        sid = sid + b'-'
        sid = sid + binascii.hexlify(payload.read(2))
        sid = sid + b'-'
        sid = sid + binascii.hexlify(payload.read(2))
        sid = sid + b'-'
        sid = sid + binascii.hexlify(payload.read(6))

        (n_intervals,) = struct.unpack('<Q', payload.read(8))
        intervals = []
        for i in range(0, n_intervals):
            start, end = struct.unpack('<QQ', payload.read(16))
            intervals.append((start, end-1))

        return cls('%s:%s' % (sid.decode('ascii'), ':'.join([
            '%d-%d' % x
            if isinstance(x, tuple)
            else '%d' % x
            for x in intervals])))


class GtidSet(object):
    def __init__(self, gtid_set):
        def _to_gtid(element):
            if isinstance(element, Gtid):
                return element
            return Gtid(element.strip(' \n'))

        if not gtid_set:
            self.gtids = []
        elif isinstance(gtid_set, (list, set)):
            self.gtids = [_to_gtid(x) for x in gtid_set]
        else:
            self.gtids = [Gtid(x.strip(' \n')) for x in gtid_set.split(',')]

    def merge_gtid(self, gtid):
        new_gtids = []
        for existing in self.gtids:
            if existing.sid == gtid.sid:
                new_gtids.append(existing + gtid)
            else:
                new_gtids.append(existing)
        if gtid.sid not in (x.sid for x in new_gtids):
            new_gtids.append(gtid)
        self.gtids = new_gtids

    def __contains__(self, other):
        if isinstance(other, Gtid):
            return any(other in x for x in self.gtids)
        raise NotImplementedError

    def __add__(self, other):
        if isinstance(other, Gtid):
            new = GtidSet(self.gtids)
            new.merge_gtid(other)
            return new
        raise NotImplementedError

    def __str__(self):
        return ','.join(str(x) for x in self.gtids)

    def __repr__(self):
        return '<GtidSet %r>' % self.gtids

    @property
    def encoded_length(self):
        return (8 +  # n_sids
                sum(x.encoded_length for x in self.gtids))

    def encoded(self):
        return b'' + (struct.pack('<Q', len(self.gtids)) +
                      b''.join(x.encode() for x in self.gtids))

    encode = encoded

    @classmethod
    def decode(cls, payload):
        assert isinstance(payload, BytesIO), \
            'payload is expected to be a BytesIO'
        (n_sid,) = struct.unpack('<Q', payload.read(8))

        return cls([Gtid.decode(payload) for _ in range(0, n_sid)])
