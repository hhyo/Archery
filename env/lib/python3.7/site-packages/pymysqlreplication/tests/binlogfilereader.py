'''Read binlog files'''
import struct

from pymysql.util import byte2int
from pymysqlreplication import constants
from pymysqlreplication.event import FormatDescriptionEvent
from pymysqlreplication.event import QueryEvent
from pymysqlreplication.event import RotateEvent
from pymysqlreplication.event import XidEvent
from pymysqlreplication.row_event import TableMapEvent
from pymysqlreplication.row_event import WriteRowsEvent

class SimpleBinLogFileReader(object):
    '''Read binlog files'''

    _expected_magic = b'\xfebin'

    def __init__(self, file_path, only_events=None):
        self._current_event = None
        self._file = None
        self._file_path = file_path
        self._only_events = only_events
        self._pos = None

    def fetchone(self):
        '''Fetch one record from the binlog file'''
        if self._pos is None or self._pos < 4:
            self._read_magic()
        while True:
            event = self._read_event()
            self._current_event = event
            if event is None:
                return None
            if self._filter_events(event):
                return event

    def truncatebinlog(self):
        '''Truncate the binlog file at the current event'''
        if self._current_event is not None:
            self._file.truncate(self._current_event.pos)

    def _filter_events(self, event):
        '''Return True if an event can be returned'''
        # It would be good if we could reuse the __event_map in
        # packet.BinLogPacketWrapper.
        event_type = {
            constants.QUERY_EVENT: QueryEvent,
            constants.ROTATE_EVENT: RotateEvent,
            constants.FORMAT_DESCRIPTION_EVENT: FormatDescriptionEvent,
            constants.XID_EVENT: XidEvent,
            constants.TABLE_MAP_EVENT: TableMapEvent,
            constants.WRITE_ROWS_EVENT_V2: WriteRowsEvent,
        }.get(event.event_type)
        return event_type in self._only_events

    def _open_file(self):
        '''Open the file at ``self._file_path``'''
        if self._file is None:
            self._file = open(self._file_path, 'rb+')
            self._pos = self._file.tell()
            assert self._pos == 0

    def _read_event(self):
        '''Read an event from the binlog file'''
        # Assuming a binlog version > 1
        headerlength = 19
        header = self._file.read(headerlength)
        event_pos = self._pos
        self._pos += len(header)
        if len(header) == 0:
            return None
        event = SimpleBinLogEvent(header)
        event.set_pos(event_pos)
        if event.event_size < headerlength:
            messagefmt = 'Event size {0} is too small'
            message = messagefmt.format(event.event_size)
            raise EventSizeTooSmallError(message)
        else:
            body = self._file.read(event.event_size - headerlength)
            self._pos += len(body)
            event.set_body(body)
        return event

    def _read_magic(self):
        '''Read the first four *magic* bytes of the binlog file'''
        self._open_file()
        if self._pos == 0:
            magic = self._file.read(4)
            if magic == self._expected_magic:
                self._pos += len(magic)
            else:
                messagefmt = 'Magic bytes {0!r} did not match expected {1!r}'
                message = messagefmt.format(magic, self._expected_magic)
                raise BadMagicBytesError(message)

    def __iter__(self):
        return iter(self.fetchone, None)

    def __repr__(self):
        cls = self.__class__
        mod = cls.__module__
        name = cls.__name__
        only = [type(x).__name__ for x in self._only_events]
        fmt = '<{mod}.{name}(file_path={fpath}, only_events={only})>'
        return fmt.format(mod=mod, name=name, fpath=self._file_path, only=only)


# pylint: disable=too-many-instance-attributes
class SimpleBinLogEvent(object):
    '''An event from a binlog file'''

    def __init__(self, header):
        '''Initialize the Event with the event header'''
        unpacked = struct.unpack('<IcIIIH', header)
        self.timestamp = unpacked[0]
        self.event_type = byte2int(unpacked[1])
        self.server_id = unpacked[2]
        self.event_size = unpacked[3]
        self.log_pos = unpacked[4]
        self.flags = unpacked[5]

        self.body = None
        self.pos = None

    def set_body(self, body):
        '''Save the body bytes'''
        self.body = body

    def set_pos(self, pos):
        '''Save the event position'''
        self.pos = pos

    def __repr__(self):
        cls = self.__class__
        mod = cls.__module__
        name = cls.__name__
        fmt = '<{mod}.{name}(timestamp={ts}, event_type={et}, log_pos={pos})>'
        return fmt.format(
            mod=mod,
            name=name,
            ts=int(self.timestamp),
            et=self.event_type,
            pos=self.log_pos)


class BadMagicBytesError(Exception):
    '''The binlog file magic bytes did not match the specification'''

class EventSizeTooSmallError(Exception):
    '''The event size was smaller than the length of the event header'''
