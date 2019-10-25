# Copyright 2015-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you
# may not use this file except in compliance with the License.  You
# may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.  See the License for the specific language governing
# permissions and limitations under the License.

"""Tools to monitor driver events.

.. versionadded:: 3.1

Use :func:`register` to register global listeners for specific events.
Listeners must inherit from one of the abstract classes below and implement
the correct functions for that class.

For example, a simple command logger might be implemented like this::

    import logging

    from pymongo import monitoring

    class CommandLogger(monitoring.CommandListener):

        def started(self, event):
            logging.info("Command {0.command_name} with request id "
                         "{0.request_id} started on server "
                         "{0.connection_id}".format(event))

        def succeeded(self, event):
            logging.info("Command {0.command_name} with request id "
                         "{0.request_id} on server {0.connection_id} "
                         "succeeded in {0.duration_micros} "
                         "microseconds".format(event))

        def failed(self, event):
            logging.info("Command {0.command_name} with request id "
                         "{0.request_id} on server {0.connection_id} "
                         "failed in {0.duration_micros} "
                         "microseconds".format(event))

    monitoring.register(CommandLogger())

Server discovery and monitoring events are also available. For example::

    class ServerLogger(monitoring.ServerListener):

        def opened(self, event):
            logging.info("Server {0.server_address} added to topology "
                         "{0.topology_id}".format(event))

        def description_changed(self, event):
            previous_server_type = event.previous_description.server_type
            new_server_type = event.new_description.server_type
            if new_server_type != previous_server_type:
                # server_type_name was added in PyMongo 3.4
                logging.info(
                    "Server {0.server_address} changed type from "
                    "{0.previous_description.server_type_name} to "
                    "{0.new_description.server_type_name}".format(event))

        def closed(self, event):
            logging.warning("Server {0.server_address} removed from topology "
                            "{0.topology_id}".format(event))


    class HeartbeatLogger(monitoring.ServerHeartbeatListener):

        def started(self, event):
            logging.info("Heartbeat sent to server "
                         "{0.connection_id}".format(event))

        def succeeded(self, event):
            # The reply.document attribute was added in PyMongo 3.4.
            logging.info("Heartbeat to server {0.connection_id} "
                         "succeeded with reply "
                         "{0.reply.document}".format(event))

        def failed(self, event):
            logging.warning("Heartbeat to server {0.connection_id} "
                            "failed with error {0.reply}".format(event))

    class TopologyLogger(monitoring.TopologyListener):

        def opened(self, event):
            logging.info("Topology with id {0.topology_id} "
                         "opened".format(event))

        def description_changed(self, event):
            logging.info("Topology description updated for "
                         "topology id {0.topology_id}".format(event))
            previous_topology_type = event.previous_description.topology_type
            new_topology_type = event.new_description.topology_type
            if new_topology_type != previous_topology_type:
                # topology_type_name was added in PyMongo 3.4
                logging.info(
                    "Topology {0.topology_id} changed type from "
                    "{0.previous_description.topology_type_name} to "
                    "{0.new_description.topology_type_name}".format(event))
            # The has_writable_server and has_readable_server methods
            # were added in PyMongo 3.4.
            if not event.new_description.has_writable_server():
                logging.warning("No writable servers available.")
            if not event.new_description.has_readable_server():
                logging.warning("No readable servers available.")

        def closed(self, event):
            logging.info("Topology with id {0.topology_id} "
                         "closed".format(event))


Event listeners can also be registered per instance of
:class:`~pymongo.mongo_client.MongoClient`::

    client = MongoClient(event_listeners=[CommandLogger()])

Note that previously registered global listeners are automatically included
when configuring per client event listeners. Registering a new global listener
will not add that listener to existing client instances.

.. note:: Events are delivered **synchronously**. Application threads block
  waiting for event handlers (e.g. :meth:`~CommandListener.started`) to
  return. Care must be taken to ensure that your event handlers are efficient
  enough to not adversely affect overall application performance.

.. warning:: The command documents published through this API are *not* copies.
  If you intend to modify them in any way you must copy them in your event
  handler first.
"""

import sys
import traceback

from collections import namedtuple

from bson.py3compat import abc
from pymongo.helpers import _handle_exception

_Listeners = namedtuple('Listeners',
                        ('command_listeners', 'server_listeners',
                         'server_heartbeat_listeners', 'topology_listeners'))

_LISTENERS = _Listeners([], [], [], [])


class _EventListener(object):
    """Abstract base class for all event listeners."""


class CommandListener(_EventListener):
    """Abstract base class for command listeners.
    Handles `CommandStartedEvent`, `CommandSucceededEvent`,
    and `CommandFailedEvent`."""

    def started(self, event):
        """Abstract method to handle a `CommandStartedEvent`.

        :Parameters:
          - `event`: An instance of :class:`CommandStartedEvent`.
        """
        raise NotImplementedError

    def succeeded(self, event):
        """Abstract method to handle a `CommandSucceededEvent`.

        :Parameters:
          - `event`: An instance of :class:`CommandSucceededEvent`.
        """
        raise NotImplementedError

    def failed(self, event):
        """Abstract method to handle a `CommandFailedEvent`.

        :Parameters:
          - `event`: An instance of :class:`CommandFailedEvent`.
        """
        raise NotImplementedError


class ServerHeartbeatListener(_EventListener):
    """Abstract base class for server heartbeat listeners.
    Handles `ServerHeartbeatStartedEvent`, `ServerHeartbeatSucceededEvent`,
    and `ServerHeartbeatFailedEvent`.

    .. versionadded:: 3.3
    """

    def started(self, event):
        """Abstract method to handle a `ServerHeartbeatStartedEvent`.

        :Parameters:
          - `event`: An instance of :class:`ServerHeartbeatStartedEvent`.
        """
        raise NotImplementedError

    def succeeded(self, event):
        """Abstract method to handle a `ServerHeartbeatSucceededEvent`.

        :Parameters:
          - `event`: An instance of :class:`ServerHeartbeatSucceededEvent`.
        """
        raise NotImplementedError

    def failed(self, event):
        """Abstract method to handle a `ServerHeartbeatFailedEvent`.

        :Parameters:
          - `event`: An instance of :class:`ServerHeartbeatFailedEvent`.
        """
        raise NotImplementedError


class TopologyListener(_EventListener):
    """Abstract base class for topology monitoring listeners.
    Handles `TopologyOpenedEvent`, `TopologyDescriptionChangedEvent`, and
    `TopologyClosedEvent`.

    .. versionadded:: 3.3
    """

    def opened(self, event):
        """Abstract method to handle a `TopologyOpenedEvent`.

        :Parameters:
          - `event`: An instance of :class:`TopologyOpenedEvent`.
        """
        raise NotImplementedError

    def description_changed(self, event):
        """Abstract method to handle a `TopologyDescriptionChangedEvent`.

        :Parameters:
          - `event`: An instance of :class:`TopologyDescriptionChangedEvent`.
        """
        raise NotImplementedError

    def closed(self, event):
        """Abstract method to handle a `TopologyClosedEvent`.

        :Parameters:
          - `event`: An instance of :class:`TopologyClosedEvent`.
        """
        raise NotImplementedError


class ServerListener(_EventListener):
    """Abstract base class for server listeners.
    Handles `ServerOpeningEvent`, `ServerDescriptionChangedEvent`, and
    `ServerClosedEvent`.

    .. versionadded:: 3.3
    """

    def opened(self, event):
        """Abstract method to handle a `ServerOpeningEvent`.

        :Parameters:
          - `event`: An instance of :class:`ServerOpeningEvent`.
        """
        raise NotImplementedError

    def description_changed(self, event):
        """Abstract method to handle a `ServerDescriptionChangedEvent`.

        :Parameters:
          - `event`: An instance of :class:`ServerDescriptionChangedEvent`.
        """
        raise NotImplementedError

    def closed(self, event):
        """Abstract method to handle a `ServerClosedEvent`.

        :Parameters:
          - `event`: An instance of :class:`ServerClosedEvent`.
        """
        raise NotImplementedError


def _to_micros(dur):
    """Convert duration 'dur' to microseconds."""
    return int(dur.total_seconds() * 10e5)


def _validate_event_listeners(option, listeners):
    """Validate event listeners"""
    if not isinstance(listeners, abc.Sequence):
        raise TypeError("%s must be a list or tuple" % (option,))
    for listener in listeners:
        if not isinstance(listener, _EventListener):
            raise TypeError("Listeners for %s must be either a "
                            "CommandListener, ServerHeartbeatListener, "
                            "ServerListener, or TopologyListener." % (option,))
    return listeners


def register(listener):
    """Register a global event listener.

    :Parameters:
      - `listener`: A subclasses of :class:`CommandListener`,
        :class:`ServerHeartbeatListener`, :class:`ServerListener`, or
        :class:`TopologyListener`.
    """
    if not isinstance(listener, _EventListener):
        raise TypeError("Listeners for %s must be either a "
                        "CommandListener, ServerHeartbeatListener, "
                        "ServerListener, or TopologyListener." % (listener,))
    if isinstance(listener, CommandListener):
        _LISTENERS.command_listeners.append(listener)
    if isinstance(listener, ServerHeartbeatListener):
        _LISTENERS.server_heartbeat_listeners.append(listener)
    if isinstance(listener, ServerListener):
        _LISTENERS.server_listeners.append(listener)
    if isinstance(listener, TopologyListener):
        _LISTENERS.topology_listeners.append(listener)


# Note - to avoid bugs from forgetting which if these is all lowercase and
# which are camelCase, and at the same time avoid having to add a test for
# every command, use all lowercase here and test against command_name.lower().
_SENSITIVE_COMMANDS = set(
    ["authenticate", "saslstart", "saslcontinue", "getnonce", "createuser",
     "updateuser", "copydbgetnonce", "copydbsaslstart", "copydb"])


class _CommandEvent(object):
    """Base class for command events."""

    __slots__ = ("__cmd_name", "__rqst_id", "__conn_id", "__op_id")

    def __init__(self, command_name, request_id, connection_id, operation_id):
        self.__cmd_name = command_name
        self.__rqst_id = request_id
        self.__conn_id = connection_id
        self.__op_id = operation_id

    @property
    def command_name(self):
        """The command name."""
        return self.__cmd_name

    @property
    def request_id(self):
        """The request id for this operation."""
        return self.__rqst_id

    @property
    def connection_id(self):
        """The address (host, port) of the server this command was sent to."""
        return self.__conn_id

    @property
    def operation_id(self):
        """An id for this series of events or None."""
        return self.__op_id


class CommandStartedEvent(_CommandEvent):
    """Event published when a command starts.

    :Parameters:
      - `command`: The command document.
      - `database_name`: The name of the database this command was run against.
      - `request_id`: The request id for this operation.
      - `connection_id`: The address (host, port) of the server this command
        was sent to.
      - `operation_id`: An optional identifier for a series of related events.
    """
    __slots__ = ("__cmd", "__db")

    def __init__(self, command, database_name, *args):
        if not command:
            raise ValueError("%r is not a valid command" % (command,))
        # Command name must be first key.
        command_name = next(iter(command))
        super(CommandStartedEvent, self).__init__(command_name, *args)
        if command_name.lower() in _SENSITIVE_COMMANDS:
            self.__cmd = {}
        else:
            self.__cmd = command
        self.__db = database_name

    @property
    def command(self):
        """The command document."""
        return self.__cmd

    @property
    def database_name(self):
        """The name of the database this command was run against."""
        return self.__db


class CommandSucceededEvent(_CommandEvent):
    """Event published when a command succeeds.

    :Parameters:
      - `duration`: The command duration as a datetime.timedelta.
      - `reply`: The server reply document.
      - `command_name`: The command name.
      - `request_id`: The request id for this operation.
      - `connection_id`: The address (host, port) of the server this command
        was sent to.
      - `operation_id`: An optional identifier for a series of related events.
    """
    __slots__ = ("__duration_micros", "__reply")

    def __init__(self, duration, reply, command_name,
                 request_id, connection_id, operation_id):
        super(CommandSucceededEvent, self).__init__(
            command_name, request_id, connection_id, operation_id)
        self.__duration_micros = _to_micros(duration)
        if command_name.lower() in _SENSITIVE_COMMANDS:
            self.__reply = {}
        else:
            self.__reply = reply

    @property
    def duration_micros(self):
        """The duration of this operation in microseconds."""
        return self.__duration_micros

    @property
    def reply(self):
        """The server failure document for this operation."""
        return self.__reply


class CommandFailedEvent(_CommandEvent):
    """Event published when a command fails.

    :Parameters:
      - `duration`: The command duration as a datetime.timedelta.
      - `failure`: The server reply document.
      - `command_name`: The command name.
      - `request_id`: The request id for this operation.
      - `connection_id`: The address (host, port) of the server this command
        was sent to.
      - `operation_id`: An optional identifier for a series of related events.
    """
    __slots__ = ("__duration_micros", "__failure")

    def __init__(self, duration, failure, *args):
        super(CommandFailedEvent, self).__init__(*args)
        self.__duration_micros = _to_micros(duration)
        self.__failure = failure

    @property
    def duration_micros(self):
        """The duration of this operation in microseconds."""
        return self.__duration_micros

    @property
    def failure(self):
        """The server failure document for this operation."""
        return self.__failure


class _ServerEvent(object):
    """Base class for server events."""

    __slots__ = ("__server_address", "__topology_id")

    def __init__(self, server_address, topology_id):
        self.__server_address = server_address
        self.__topology_id = topology_id

    @property
    def server_address(self):
        """The address (host/port pair) of the server"""
        return self.__server_address

    @property
    def topology_id(self):
        """A unique identifier for the topology this server is a part of."""
        return self.__topology_id


class ServerDescriptionChangedEvent(_ServerEvent):
    """Published when server description changes.

    .. versionadded:: 3.3
    """

    __slots__ = ('__previous_description', '__new_description')

    def __init__(self, previous_description, new_description, *args):
        super(ServerDescriptionChangedEvent, self).__init__(*args)
        self.__previous_description = previous_description
        self.__new_description = new_description

    @property
    def previous_description(self):
        """The previous
        :class:`~pymongo.server_description.ServerDescription`."""
        return self.__previous_description

    @property
    def new_description(self):
        """The new
        :class:`~pymongo.server_description.ServerDescription`."""
        return self.__new_description


class ServerOpeningEvent(_ServerEvent):
    """Published when server is initialized.

    .. versionadded:: 3.3
    """

    __slots__ = ()


class ServerClosedEvent(_ServerEvent):
    """Published when server is closed.

    .. versionadded:: 3.3
    """

    __slots__ = ()


class TopologyEvent(object):
    """Base class for topology description events."""

    __slots__ = ('__topology_id')

    def __init__(self, topology_id):
        self.__topology_id = topology_id

    @property
    def topology_id(self):
        """A unique identifier for the topology this server is a part of."""
        return self.__topology_id


class TopologyDescriptionChangedEvent(TopologyEvent):
    """Published when the topology description changes.

    .. versionadded:: 3.3
    """

    __slots__ = ('__previous_description', '__new_description')

    def __init__(self, previous_description,  new_description, *args):
        super(TopologyDescriptionChangedEvent, self).__init__(*args)
        self.__previous_description = previous_description
        self.__new_description = new_description

    @property
    def previous_description(self):
        """The previous
        :class:`~pymongo.topology_description.TopologyDescription`."""
        return self.__previous_description

    @property
    def new_description(self):
        """The new
        :class:`~pymongo.topology_description.TopologyDescription`."""
        return self.__new_description


class TopologyOpenedEvent(TopologyEvent):
    """Published when the topology is initialized.

    .. versionadded:: 3.3
    """

    __slots__ = ()


class TopologyClosedEvent(TopologyEvent):
    """Published when the topology is closed.

    .. versionadded:: 3.3
    """

    __slots__ = ()


class _ServerHeartbeatEvent(object):
    """Base class for server heartbeat events."""

    __slots__ = ('__connection_id')

    def __init__(self, connection_id):
        self.__connection_id = connection_id

    @property
    def connection_id(self):
        """The address (host, port) of the server this heartbeat was sent
        to."""
        return self.__connection_id


class ServerHeartbeatStartedEvent(_ServerHeartbeatEvent):
    """Published when a heartbeat is started.

    .. versionadded:: 3.3
    """

    __slots__ = ()


class ServerHeartbeatSucceededEvent(_ServerHeartbeatEvent):
    """Fired when the server heartbeat succeeds.

    .. versionadded:: 3.3
    """

    __slots__ = ('__duration', '__reply')

    def __init__(self, duration, reply, *args):
        super(ServerHeartbeatSucceededEvent, self).__init__(*args)
        self.__duration = duration
        self.__reply = reply

    @property
    def duration(self):
        """The duration of this heartbeat in microseconds."""
        return self.__duration

    @property
    def reply(self):
        """An instance of :class:`~pymongo.ismaster.IsMaster`."""
        return self.__reply


class ServerHeartbeatFailedEvent(_ServerHeartbeatEvent):
    """Fired when the server heartbeat fails, either with an "ok: 0"
    or a socket exception.

    .. versionadded:: 3.3
    """

    __slots__ = ('__duration', '__reply')

    def __init__(self, duration, reply, *args):
        super(ServerHeartbeatFailedEvent, self).__init__(*args)
        self.__duration = duration
        self.__reply = reply

    @property
    def duration(self):
        """The duration of this heartbeat in microseconds."""
        return self.__duration

    @property
    def reply(self):
        """A subclass of :exc:`Exception`."""
        return self.__reply


class _EventListeners(object):
    """Configure event listeners for a client instance.

    Any event listeners registered globally are included by default.

    :Parameters:
      - `listeners`: A list of event listeners.
    """
    def __init__(self, listeners):
        self.__command_listeners = _LISTENERS.command_listeners[:]
        self.__server_listeners = _LISTENERS.server_listeners[:]
        lst = _LISTENERS.server_heartbeat_listeners
        self.__server_heartbeat_listeners = lst[:]
        self.__topology_listeners = _LISTENERS.topology_listeners[:]
        if listeners is not None:
            for lst in listeners:
                if isinstance(lst, CommandListener):
                    self.__command_listeners.append(lst)
                if isinstance(lst, ServerListener):
                    self.__server_listeners.append(lst)
                if isinstance(lst, ServerHeartbeatListener):
                    self.__server_heartbeat_listeners.append(lst)
                if isinstance(lst, TopologyListener):
                    self.__topology_listeners.append(lst)
        self.__enabled_for_commands = bool(self.__command_listeners)
        self.__enabled_for_server = bool(self.__server_listeners)
        self.__enabled_for_server_heartbeat = bool(
            self.__server_heartbeat_listeners)
        self.__enabled_for_topology = bool(self.__topology_listeners)

    @property
    def enabled_for_commands(self):
        """Are any CommandListener instances registered?"""
        return self.__enabled_for_commands

    @property
    def enabled_for_server(self):
        """Are any ServerListener instances registered?"""
        return self.__enabled_for_server

    @property
    def enabled_for_server_heartbeat(self):
        """Are any ServerHeartbeatListener instances registered?"""
        return self.__enabled_for_server_heartbeat

    @property
    def enabled_for_topology(self):
        """Are any TopologyListener instances registered?"""
        return self.__enabled_for_topology

    def event_listeners(self):
        """List of registered event listeners."""
        return (self.__command_listeners[:],
                self.__server_heartbeat_listeners[:],
                self.__server_listeners[:],
                self.__topology_listeners[:])

    def publish_command_start(self, command, database_name,
                              request_id, connection_id, op_id=None):
        """Publish a CommandStartedEvent to all command listeners.

        :Parameters:
          - `command`: The command document.
          - `database_name`: The name of the database this command was run
            against.
          - `request_id`: The request id for this operation.
          - `connection_id`: The address (host, port) of the server this
            command was sent to.
          - `op_id`: The (optional) operation id for this operation.
        """
        if op_id is None:
            op_id = request_id
        event = CommandStartedEvent(
            command, database_name, request_id, connection_id, op_id)
        for subscriber in self.__command_listeners:
            try:
                subscriber.started(event)
            except Exception:
                _handle_exception()

    def publish_command_success(self, duration, reply, command_name,
                                request_id, connection_id, op_id=None):
        """Publish a CommandSucceededEvent to all command listeners.

        :Parameters:
          - `duration`: The command duration as a datetime.timedelta.
          - `reply`: The server reply document.
          - `command_name`: The command name.
          - `request_id`: The request id for this operation.
          - `connection_id`: The address (host, port) of the server this
            command was sent to.
          - `op_id`: The (optional) operation id for this operation.
        """
        if op_id is None:
            op_id = request_id
        event = CommandSucceededEvent(
            duration, reply, command_name, request_id, connection_id, op_id)
        for subscriber in self.__command_listeners:
            try:
                subscriber.succeeded(event)
            except Exception:
                _handle_exception()

    def publish_command_failure(self, duration, failure, command_name,
                                request_id, connection_id, op_id=None):
        """Publish a CommandFailedEvent to all command listeners.

        :Parameters:
          - `duration`: The command duration as a datetime.timedelta.
          - `failure`: The server reply document or failure description
            document.
          - `command_name`: The command name.
          - `request_id`: The request id for this operation.
          - `connection_id`: The address (host, port) of the server this
            command was sent to.
          - `op_id`: The (optional) operation id for this operation.
        """
        if op_id is None:
            op_id = request_id
        event = CommandFailedEvent(
            duration, failure, command_name, request_id, connection_id, op_id)
        for subscriber in self.__command_listeners:
            try:
                subscriber.failed(event)
            except Exception:
                _handle_exception()

    def publish_server_heartbeat_started(self, connection_id):
        """Publish a ServerHeartbeatStartedEvent to all server heartbeat
        listeners.

        :Parameters:
         - `connection_id`: The address (host/port pair) of the connection.
        """
        event = ServerHeartbeatStartedEvent(connection_id)
        for subscriber in self.__server_heartbeat_listeners:
            try:
                subscriber.started(event)
            except Exception:
                _handle_exception()

    def publish_server_heartbeat_succeeded(self, connection_id, duration,
                                           reply):
        """Publish a ServerHeartbeatSucceededEvent to all server heartbeat
        listeners.

        :Parameters:
         - `connection_id`: The address (host/port pair) of the connection.
         - `duration`: The execution time of the event in the highest possible
            resolution for the platform.
         - `reply`: The command reply.
         """
        event = ServerHeartbeatSucceededEvent(duration, reply, connection_id)
        for subscriber in self.__server_heartbeat_listeners:
            try:
                subscriber.succeeded(event)
            except Exception:
                _handle_exception()

    def publish_server_heartbeat_failed(self, connection_id, duration, reply):
        """Publish a ServerHeartbeatFailedEvent to all server heartbeat
        listeners.

        :Parameters:
         - `connection_id`: The address (host/port pair) of the connection.
         - `duration`: The execution time of the event in the highest possible
            resolution for the platform.
         - `reply`: The command reply.
         """
        event = ServerHeartbeatFailedEvent(duration, reply, connection_id)
        for subscriber in self.__server_heartbeat_listeners:
            try:
                subscriber.failed(event)
            except Exception:
                _handle_exception()

    def publish_server_opened(self, server_address, topology_id):
        """Publish a ServerOpeningEvent to all server listeners.

        :Parameters:
         - `server_address`: The address (host/port pair) of the server.
         - `topology_id`: A unique identifier for the topology this server
           is a part of.
        """
        event = ServerOpeningEvent(server_address, topology_id)
        for subscriber in self.__server_listeners:
            try:
                subscriber.opened(event)
            except Exception:
                _handle_exception()

    def publish_server_closed(self, server_address, topology_id):
        """Publish a ServerClosedEvent to all server listeners.

        :Parameters:
         - `server_address`: The address (host/port pair) of the server.
         - `topology_id`: A unique identifier for the topology this server
           is a part of.
        """
        event = ServerClosedEvent(server_address, topology_id)
        for subscriber in self.__server_listeners:
            try:
                subscriber.closed(event)
            except Exception:
                _handle_exception()

    def publish_server_description_changed(self, previous_description,
                                           new_description, server_address,
                                           topology_id):
        """Publish a ServerDescriptionChangedEvent to all server listeners.

        :Parameters:
         - `previous_description`: The previous server description.
         - `server_address`: The address (host/port pair) of the server.
         - `new_description`: The new server description.
         - `topology_id`: A unique identifier for the topology this server
           is a part of.
        """
        event = ServerDescriptionChangedEvent(previous_description,
                                              new_description, server_address,
                                              topology_id)
        for subscriber in self.__server_listeners:
            try:
                subscriber.description_changed(event)
            except Exception:
                _handle_exception()

    def publish_topology_opened(self, topology_id):
        """Publish a TopologyOpenedEvent to all topology listeners.

        :Parameters:
         - `topology_id`: A unique identifier for the topology this server
           is a part of.
        """
        event = TopologyOpenedEvent(topology_id)
        for subscriber in self.__topology_listeners:
            try:
                subscriber.opened(event)
            except Exception:
                _handle_exception()

    def publish_topology_closed(self, topology_id):
        """Publish a TopologyClosedEvent to all topology listeners.

        :Parameters:
         - `topology_id`: A unique identifier for the topology this server
           is a part of.
        """
        event = TopologyClosedEvent(topology_id)
        for subscriber in self.__topology_listeners:
            try:
                subscriber.closed(event)
            except Exception:
                _handle_exception()

    def publish_topology_description_changed(self, previous_description,
                                             new_description, topology_id):
        """Publish a TopologyDescriptionChangedEvent to all topology listeners.

        :Parameters:
         - `previous_description`: The previous topology description.
         - `new_description`: The new topology description.
         - `topology_id`: A unique identifier for the topology this server
           is a part of.
        """
        event = TopologyDescriptionChangedEvent(previous_description,
                                                new_description, topology_id)
        for subscriber in self.__topology_listeners:
            try:
                subscriber.description_changed(event)
            except Exception:
                _handle_exception()
