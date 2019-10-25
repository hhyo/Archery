# Copyright 2017 MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Logical sessions for ordering sequential operations.

Requires MongoDB 3.6.

.. versionadded:: 3.6

Causally Consistent Reads
=========================

.. code-block:: python

  with client.start_session(causal_consistency=True) as session:
      collection = client.db.collection
      collection.update_one({'_id': 1}, {'$set': {'x': 10}}, session=session)
      secondary_c = collection.with_options(
          read_preference=ReadPreference.SECONDARY)

      # A secondary read waits for replication of the write.
      secondary_c.find_one({'_id': 1}, session=session)

If `causal_consistency` is True (the default), read operations that use
the session are causally after previous read and write operations. Using a
causally consistent session, an application can read its own writes and is
guaranteed monotonic reads, even when reading from replica set secondaries.

.. mongodoc:: causal-consistency

.. _transactions-ref:

Transactions
============

MongoDB 4.0 adds support for transactions on replica set primaries. A
transaction is associated with a :class:`ClientSession`. To start a transaction
on a session, use :meth:`ClientSession.start_transaction` in a with-statement.
Then, execute an operation within the transaction by passing the session to the
operation:

.. code-block:: python

  orders = client.db.orders
  inventory = client.db.inventory
  with client.start_session() as session:
      with session.start_transaction():
          orders.insert_one({"sku": "abc123", "qty": 100}, session=session)
          inventory.update_one({"sku": "abc123", "qty": {"$gte": 100}},
                               {"$inc": {"qty": -100}}, session=session)

Upon normal completion of ``with session.start_transaction()`` block, the
transaction automatically calls :meth:`ClientSession.commit_transaction`.
If the block exits with an exception, the transaction automatically calls
:meth:`ClientSession.abort_transaction`.

For multi-document transactions, you can only specify read/write (CRUD)
operations on existing collections. For example, a multi-document transaction
cannot include a create or drop collection/index operations, including an
insert operation that would result in the creation of a new collection.

A session may only have a single active transaction at a time, multiple
transactions on the same session can be executed in sequence.

.. versionadded:: 3.7

.. mongodoc:: transactions

Classes
=======
"""

import collections
import sys
import uuid

from bson.binary import Binary
from bson.int64 import Int64
from bson.py3compat import abc, reraise_instance
from bson.timestamp import Timestamp

from pymongo import monotonic, __version__
from pymongo.errors import (ConfigurationError,
                            ConnectionFailure,
                            InvalidOperation,
                            OperationFailure,
                            ServerSelectionTimeoutError,
                            WriteConcernError,
                            WTimeoutError)
from pymongo.helpers import _RETRYABLE_ERROR_CODES
from pymongo.read_concern import ReadConcern
from pymongo.read_preferences import ReadPreference, _ServerMode
from pymongo.write_concern import WriteConcern


class SessionOptions(object):
    """Options for a new :class:`ClientSession`.

    :Parameters:
      - `causal_consistency` (optional): If True (the default), read
        operations are causally ordered within the session.
      - `default_transaction_options` (optional): The default
        TransactionOptions to use for transactions started on this session.
    """
    def __init__(self,
                 causal_consistency=True,
                 default_transaction_options=None):
        self._causal_consistency = causal_consistency
        if default_transaction_options is not None:
            if not isinstance(default_transaction_options, TransactionOptions):
                raise TypeError(
                    "default_transaction_options must be an instance of "
                    "pymongo.client_session.TransactionOptions, not: %r" %
                    (default_transaction_options,))
        self._default_transaction_options = default_transaction_options

    @property
    def causal_consistency(self):
        """Whether causal consistency is configured."""
        return self._causal_consistency

    @property
    def default_transaction_options(self):
        """The default TransactionOptions to use for transactions started on
        this session.

        .. versionadded:: 3.7
        """
        return self._default_transaction_options


class TransactionOptions(object):
    """Options for :meth:`ClientSession.start_transaction`.
    
    :Parameters:
      - `read_concern`: The :class:`~pymongo.read_concern.ReadConcern` to use
        for this transaction.
      - `write_concern`: The :class:`~pymongo.write_concern.WriteConcern` to
        use for this transaction.

    .. versionadded:: 3.7
    """
    def __init__(self, read_concern=None, write_concern=None,
                 read_preference=None):
        self._read_concern = read_concern
        self._write_concern = write_concern
        self._read_preference = read_preference
        if read_concern is not None:
            if not isinstance(read_concern, ReadConcern):
                raise TypeError("read_concern must be an instance of "
                                "pymongo.read_concern.ReadConcern, not: %r" %
                                (read_concern,))
        if write_concern is not None:
            if not isinstance(write_concern, WriteConcern):
                raise TypeError("write_concern must be an instance of "
                                "pymongo.write_concern.WriteConcern, not: %r" %
                                (write_concern,))
            if not write_concern.acknowledged:
                raise ConfigurationError(
                    "transactions do not support unacknowledged write concern"
                    ": %r" % (write_concern,))
        if read_preference is not None:
            if not isinstance(read_preference, _ServerMode):
                raise TypeError("%r is not valid for read_preference. See "
                                "pymongo.read_preferences for valid "
                                "options." % (read_preference,))

    @property
    def read_concern(self):
        """This transaction's :class:`~pymongo.read_concern.ReadConcern`."""
        return self._read_concern

    @property
    def write_concern(self):
        """This transaction's :class:`~pymongo.write_concern.WriteConcern`."""
        return self._write_concern

    @property
    def read_preference(self):
        """This transaction's :class:`~pymongo.read_preferences.ReadPreference`.
        """
        return self._read_preference


def _validate_session_write_concern(session, write_concern):
    """Validate that an explicit session is not used with an unack'ed write.

    Returns the session to use for the next operation.
    """
    if session:
        if write_concern is not None and not write_concern.acknowledged:
            # For unacknowledged writes without an explicit session,
            # drivers SHOULD NOT use an implicit session. If a driver
            # creates an implicit session for unacknowledged writes
            # without an explicit session, the driver MUST NOT send the
            # session ID.
            if session._implicit:
                return None
            else:
                raise ConfigurationError(
                    'Explicit sessions are incompatible with '
                    'unacknowledged write concern: %r' % (
                        write_concern,))
    return session


class _TransactionContext(object):
    """Internal transaction context manager for start_transaction."""
    def __init__(self, session):
        self.__session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.__session._in_transaction:
            if exc_val is None:
                self.__session.commit_transaction()
            else:
                self.__session.abort_transaction()


class _TxnState(object):
    NONE = 1
    STARTING = 2
    IN_PROGRESS = 3
    COMMITTED = 4
    COMMITTED_EMPTY = 5
    ABORTED = 6


class _Transaction(object):
    """Internal class to hold transaction information in a ClientSession."""
    def __init__(self, opts):
        self.opts = opts
        self.state = _TxnState.NONE
        self.transaction_id = 0

    def active(self):
        return self.state in (_TxnState.STARTING, _TxnState.IN_PROGRESS)


def _reraise_with_unknown_commit(exc):
    """Re-raise an exception with the UnknownTransactionCommitResult label."""
    exc._add_error_label("UnknownTransactionCommitResult")
    reraise_instance(exc, trace=sys.exc_info()[2])


# From the transactions spec, all the retryable writes errors plus
# WriteConcernFailed.
_UNKNOWN_COMMIT_ERROR_CODES = _RETRYABLE_ERROR_CODES | frozenset([
    64,    # WriteConcernFailed
])

_MONGOS_NOT_SUPPORTED_MSG = (
    'PyMongo %s does not support running multi-document transactions on '
    'sharded clusters') % (__version__,)


class ClientSession(object):
    """A session for ordering sequential operations."""
    def __init__(self, client, server_session, options, authset, implicit):
        # A MongoClient, a _ServerSession, a SessionOptions, and a set.
        self._client = client
        self._server_session = server_session
        self._options = options
        self._authset = authset
        self._cluster_time = None
        self._operation_time = None
        # Is this an implicitly created session?
        self._implicit = implicit
        self._transaction = _Transaction(None)

    def end_session(self):
        """Finish this session. If a transaction has started, abort it.

        It is an error to use the session after the session has ended.
        """
        self._end_session(lock=True)

    def _end_session(self, lock):
        if self._server_session is not None:
            try:
                if self._in_transaction:
                    self.abort_transaction()
            finally:
                self._client._return_server_session(self._server_session, lock)
                self._server_session = None

    def _check_ended(self):
        if self._server_session is None:
            raise InvalidOperation("Cannot use ended session")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._end_session(lock=True)

    @property
    def client(self):
        """The :class:`~pymongo.mongo_client.MongoClient` this session was
        created from.
        """
        return self._client

    @property
    def options(self):
        """The :class:`SessionOptions` this session was created with."""
        return self._options

    @property
    def session_id(self):
        """A BSON document, the opaque server session identifier."""
        self._check_ended()
        return self._server_session.session_id

    @property
    def cluster_time(self):
        """The cluster time returned by the last operation executed
        in this session.
        """
        return self._cluster_time

    @property
    def operation_time(self):
        """The operation time returned by the last operation executed
        in this session.
        """
        return self._operation_time

    def _inherit_option(self, name, val):
        """Return the inherited TransactionOption value."""
        if val:
            return val
        txn_opts = self.options.default_transaction_options
        val = txn_opts and getattr(txn_opts, name)
        if val:
            return val
        return getattr(self.client, name)

    def start_transaction(self, read_concern=None, write_concern=None,
                          read_preference=None):
        """Start a multi-statement transaction.

        Takes the same arguments as :class:`TransactionOptions`.

        .. versionadded:: 3.7
        """
        self._check_ended()

        if self._client._is_mongos_non_blocking():
            raise ConfigurationError(_MONGOS_NOT_SUPPORTED_MSG)

        if self._in_transaction:
            raise InvalidOperation("Transaction already in progress")

        read_concern = self._inherit_option("read_concern", read_concern)
        write_concern = self._inherit_option("write_concern", write_concern)
        read_preference = self._inherit_option(
            "read_preference", read_preference)

        self._transaction.opts = TransactionOptions(
            read_concern, write_concern, read_preference)
        self._transaction.state = _TxnState.STARTING
        self._start_retryable_write()
        self._transaction.transaction_id = self._server_session.transaction_id
        return _TransactionContext(self)

    def commit_transaction(self):
        """Commit a multi-statement transaction.

        .. versionadded:: 3.7
        """
        self._check_ended()

        state = self._transaction.state
        if state is _TxnState.NONE:
            raise InvalidOperation("No transaction started")
        elif state in (_TxnState.STARTING, _TxnState.COMMITTED_EMPTY):
            # Server transaction was never started, no need to send a command.
            self._transaction.state = _TxnState.COMMITTED_EMPTY
            return
        elif state is _TxnState.ABORTED:
            raise InvalidOperation(
                "Cannot call commitTransaction after calling abortTransaction")

        try:
            self._finish_transaction_with_retry("commitTransaction")
        except ConnectionFailure as exc:
            # We do not know if the commit was successfully applied on the
            # server or if it satisfied the provided write concern, set the
            # unknown commit error label.
            exc._remove_error_label("TransientTransactionError")
            _reraise_with_unknown_commit(exc)
        except WTimeoutError as exc:
            # We do not know if the commit has satisfied the provided write
            # concern, add the unknown commit error label.
            _reraise_with_unknown_commit(exc)
        except OperationFailure as exc:
            if exc.code not in _UNKNOWN_COMMIT_ERROR_CODES:
                # The server reports errorLabels in the case.
                raise
            # We do not know if the commit was successfully applied on the
            # server or if it satisfied the provided write concern, set the
            # unknown commit error label.
            _reraise_with_unknown_commit(exc)
        finally:
            self._transaction.state = _TxnState.COMMITTED

    def abort_transaction(self):
        """Abort a multi-statement transaction.

        .. versionadded:: 3.7
        """
        self._check_ended()

        state = self._transaction.state
        if state is _TxnState.NONE:
            raise InvalidOperation("No transaction started")
        elif state is _TxnState.STARTING:
            # Server transaction was never started, no need to send a command.
            self._transaction.state = _TxnState.ABORTED
            return
        elif state is _TxnState.ABORTED:
            raise InvalidOperation("Cannot call abortTransaction twice")
        elif state in (_TxnState.COMMITTED, _TxnState.COMMITTED_EMPTY):
            raise InvalidOperation(
                "Cannot call abortTransaction after calling commitTransaction")

        try:
            self._finish_transaction_with_retry("abortTransaction")
        except (OperationFailure, ConnectionFailure):
            # The transactions spec says to ignore abortTransaction errors.
            pass
        finally:
            self._transaction.state = _TxnState.ABORTED

    def _finish_transaction(self, command_name):
        with self._client._socket_for_writes() as sock_info:
            return self._client.admin._command(
                sock_info,
                command_name,
                txnNumber=self._transaction.transaction_id,
                autocommit=False,
                session=self,
                write_concern=self._transaction.opts.write_concern,
                parse_write_concern_error=True)

    def _finish_transaction_with_retry(self, command_name):
        # This can be refactored with MongoClient._retry_with_session.
        try:
            return self._finish_transaction(command_name)
        except ServerSelectionTimeoutError:
            raise
        except ConnectionFailure as exc:
            try:
                return self._finish_transaction(command_name)
            except ServerSelectionTimeoutError:
                # Raise the original error so the application can infer that
                # an attempt was made.
                raise exc
        except OperationFailure as exc:
            if exc.code not in _RETRYABLE_ERROR_CODES:
                raise
            try:
                return self._finish_transaction(command_name)
            except ServerSelectionTimeoutError:
                # Raise the original error so the application can infer that
                # an attempt was made.
                raise exc

    def _advance_cluster_time(self, cluster_time):
        """Internal cluster time helper."""
        if self._cluster_time is None:
            self._cluster_time = cluster_time
        elif cluster_time is not None:
            if cluster_time["clusterTime"] > self._cluster_time["clusterTime"]:
                self._cluster_time = cluster_time

    def advance_cluster_time(self, cluster_time):
        """Update the cluster time for this session.

        :Parameters:
          - `cluster_time`: The
            :data:`~pymongo.client_session.ClientSession.cluster_time` from
            another `ClientSession` instance.
        """
        if not isinstance(cluster_time, abc.Mapping):
            raise TypeError(
                "cluster_time must be a subclass of collections.Mapping")
        if not isinstance(cluster_time.get("clusterTime"), Timestamp):
            raise ValueError("Invalid cluster_time")
        self._advance_cluster_time(cluster_time)

    def _advance_operation_time(self, operation_time):
        """Internal operation time helper."""
        if self._operation_time is None:
            self._operation_time = operation_time
        elif operation_time is not None:
            if operation_time > self._operation_time:
                self._operation_time = operation_time

    def advance_operation_time(self, operation_time):
        """Update the operation time for this session.

        :Parameters:
          - `operation_time`: The
            :data:`~pymongo.client_session.ClientSession.operation_time` from
            another `ClientSession` instance.
        """
        if not isinstance(operation_time, Timestamp):
            raise TypeError("operation_time must be an instance "
                            "of bson.timestamp.Timestamp")
        self._advance_operation_time(operation_time)

    @property
    def has_ended(self):
        """True if this session is finished."""
        return self._server_session is None

    @property
    def _in_transaction(self):
        """True if this session has an active multi-statement transaction."""
        return self._transaction.active()

    def _txn_read_preference(self):
        """Return read preference of this transaction or None."""
        if self._in_transaction:
            return self._transaction.opts.read_preference
        return None

    def _apply_to(self, command, is_retryable, read_preference, sock_info):
        self._check_ended()

        self._server_session.last_use = monotonic.time()
        command['lsid'] = self._server_session.session_id

        if not self._in_transaction:
            self._transaction.state = _TxnState.NONE

        if is_retryable:
            command['txnNumber'] = self._server_session.transaction_id
            return

        if self._in_transaction:
            if sock_info.is_mongos:
                raise ConfigurationError(_MONGOS_NOT_SUPPORTED_MSG)

            if read_preference != ReadPreference.PRIMARY:
                raise InvalidOperation(
                    'read preference in a transaction must be primary, not: '
                    '%r' % (read_preference,))

            if self._transaction.state == _TxnState.STARTING:
                # First command begins a new transaction.
                self._transaction.state = _TxnState.IN_PROGRESS
                command['startTransaction'] = True

                if self._transaction.opts.read_concern:
                    rc = self._transaction.opts.read_concern.document
                else:
                    rc = {}

                if (self.options.causal_consistency
                        and self.operation_time is not None):
                    rc['afterClusterTime'] = self.operation_time

                if rc:
                    command['readConcern'] = rc

            command['txnNumber'] = self._server_session.transaction_id
            command['autocommit'] = False

    def _start_retryable_write(self):
        self._check_ended()
        self._server_session.inc_transaction_id()


class _ServerSession(object):
    def __init__(self):
        # Ensure id is type 4, regardless of CodecOptions.uuid_representation.
        self.session_id = {'id': Binary(uuid.uuid4().bytes, 4)}
        self.last_use = monotonic.time()
        self._transaction_id = 0

    def timed_out(self, session_timeout_minutes):
        idle_seconds = monotonic.time() - self.last_use

        # Timed out if we have less than a minute to live.
        return idle_seconds > (session_timeout_minutes - 1) * 60

    @property
    def transaction_id(self):
        """Positive 64-bit integer."""
        return Int64(self._transaction_id)

    def inc_transaction_id(self):
        self._transaction_id += 1


class _ServerSessionPool(collections.deque):
    """Pool of _ServerSession objects.

    This class is not thread-safe, access it while holding the Topology lock.
    """
    def pop_all(self):
        ids = []
        while self:
            ids.append(self.pop().session_id)
        return ids

    def get_server_session(self, session_timeout_minutes):
        # Although the Driver Sessions Spec says we only clear stale sessions
        # in return_server_session, PyMongo can't take a lock when returning
        # sessions from a __del__ method (like in Cursor.__die), so it can't
        # clear stale sessions there. In case many sessions were returned via
        # __del__, check for stale sessions here too.
        self._clear_stale(session_timeout_minutes)

        # The most recently used sessions are on the left.
        while self:
            s = self.popleft()
            if not s.timed_out(session_timeout_minutes):
                return s

        return _ServerSession()

    def return_server_session(self, server_session, session_timeout_minutes):
        self._clear_stale(session_timeout_minutes)
        if not server_session.timed_out(session_timeout_minutes):
            self.appendleft(server_session)

    def return_server_session_no_lock(self, server_session):
        self.appendleft(server_session)

    def _clear_stale(self, session_timeout_minutes):
        # Clear stale sessions. The least recently used are on the right.
        while self:
            if self[-1].timed_out(session_timeout_minutes):
                self.pop()
            else:
                # The remaining sessions also haven't timed out.
                break
