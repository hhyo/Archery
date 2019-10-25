# Copyright 2011-present MongoDB, Inc.
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


"""Tools to parse and validate a MongoDB URI."""
import re
import warnings

try:
    from dns import resolver
    _HAVE_DNSPYTHON = True
except ImportError:
    _HAVE_DNSPYTHON = False

from bson.py3compat import PY3, string_type

if PY3:
    from urllib.parse import unquote_plus
else:
    from urllib import unquote_plus

from pymongo.common import get_validated_options
from pymongo.errors import ConfigurationError, InvalidURI


SCHEME = 'mongodb://'
SCHEME_LEN = len(SCHEME)
SRV_SCHEME = 'mongodb+srv://'
SRV_SCHEME_LEN = len(SRV_SCHEME)
DEFAULT_PORT = 27017


def parse_userinfo(userinfo):
    """Validates the format of user information in a MongoDB URI.
    Reserved characters like ':', '/', '+' and '@' must be escaped
    following RFC 3986.

    Returns a 2-tuple containing the unescaped username followed
    by the unescaped password.

    :Paramaters:
        - `userinfo`: A string of the form <username>:<password>

    .. versionchanged:: 2.2
       Now uses `urllib.unquote_plus` so `+` characters must be escaped.
    """
    if '@' in userinfo or userinfo.count(':') > 1:
        if PY3:
            quote_fn = "urllib.parse.quote_plus"
        else:
            quote_fn = "urllib.quote_plus"
        raise InvalidURI("Username and password must be escaped according to "
                         "RFC 3986, use %s()." % quote_fn)
    user, _, passwd = userinfo.partition(":")
    # No password is expected with GSSAPI authentication.
    if not user:
        raise InvalidURI("The empty string is not valid username.")
    return unquote_plus(user), unquote_plus(passwd)


def parse_ipv6_literal_host(entity, default_port):
    """Validates an IPv6 literal host:port string.

    Returns a 2-tuple of IPv6 literal followed by port where
    port is default_port if it wasn't specified in entity.

    :Parameters:
        - `entity`: A string that represents an IPv6 literal enclosed
                    in braces (e.g. '[::1]' or '[::1]:27017').
        - `default_port`: The port number to use when one wasn't
                          specified in entity.
    """
    if entity.find(']') == -1:
        raise ValueError("an IPv6 address literal must be "
                         "enclosed in '[' and ']' according "
                         "to RFC 2732.")
    i = entity.find(']:')
    if i == -1:
        return entity[1:-1], default_port
    return entity[1: i], entity[i + 2:]


def parse_host(entity, default_port=DEFAULT_PORT):
    """Validates a host string

    Returns a 2-tuple of host followed by port where port is default_port
    if it wasn't specified in the string.

    :Parameters:
        - `entity`: A host or host:port string where host could be a
                    hostname or IP address.
        - `default_port`: The port number to use when one wasn't
                          specified in entity.
    """
    host = entity
    port = default_port
    if entity[0] == '[':
        host, port = parse_ipv6_literal_host(entity, default_port)
    elif entity.endswith(".sock"):
        return entity, default_port
    elif entity.find(':') != -1:
        if entity.count(':') > 1:
            raise ValueError("Reserved characters such as ':' must be "
                             "escaped according RFC 2396. An IPv6 "
                             "address literal must be enclosed in '[' "
                             "and ']' according to RFC 2732.")
        host, port = host.split(':', 1)
    if isinstance(port, string_type):
        if not port.isdigit() or int(port) > 65535 or int(port) <= 0:
            raise ValueError("Port must be an integer between 0 and 65535: %s"
                             % (port,))
        port = int(port)

    # Normalize hostname to lowercase, since DNS is case-insensitive:
    # http://tools.ietf.org/html/rfc4343
    # This prevents useless rediscovery if "foo.com" is in the seed list but
    # "FOO.com" is in the ismaster response.
    return host.lower(), port


def validate_options(opts, warn=False):
    """Validates and normalizes options passed in a MongoDB URI.

    Returns a new dictionary of validated and normalized options. If warn is
    False then errors will be thrown for invalid options, otherwise they will
    be ignored and a warning will be issued.

    :Parameters:
        - `opts`: A dict of MongoDB URI options.
        - `warn` (optional): If ``True`` then warnigns will be logged and
          invalid options will be ignored. Otherwise invalid options will
          cause errors.
    """
    return get_validated_options(opts, warn)


def _parse_options(opts, delim):
    """Helper method for split_options which creates the options dict.
    Also handles the creation of a list for the URI tag_sets/
    readpreferencetags portion."""
    options = {}
    for opt in opts.split(delim):
        key, val = opt.split("=")
        if key.lower() == 'readpreferencetags':
            options.setdefault('readpreferencetags', []).append(val)
        else:
            # str(option) to ensure that a unicode URI results in plain 'str'
            # option names. 'normalized' is then suitable to be passed as
            # kwargs in all Python versions.
            if str(key) in options:
                warnings.warn("Duplicate URI option %s" % (str(key),))
            options[str(key)] = unquote_plus(val)

    # Special case for deprecated options
    if "wtimeout" in options:
        if "wtimeoutMS" in options:
            options.pop("wtimeout")
        warnings.warn("Option wtimeout is deprecated, use 'wtimeoutMS'"
                      " instead")

    return options


def split_options(opts, validate=True, warn=False):
    """Takes the options portion of a MongoDB URI, validates each option
    and returns the options in a dictionary.

    :Parameters:
        - `opt`: A string representing MongoDB URI options.
        - `validate`: If ``True`` (the default), validate and normalize all
          options.
    """
    and_idx = opts.find("&")
    semi_idx = opts.find(";")
    try:
        if and_idx >= 0 and semi_idx >= 0:
            raise InvalidURI("Can not mix '&' and ';' for option separators.")
        elif and_idx >= 0:
            options = _parse_options(opts, "&")
        elif semi_idx >= 0:
            options = _parse_options(opts, ";")
        elif opts.find("=") != -1:
            options = _parse_options(opts, None)
        else:
            raise ValueError
    except ValueError:
        raise InvalidURI("MongoDB URI options are key=value pairs.")

    if validate:
        return validate_options(options, warn)
    return options


def split_hosts(hosts, default_port=DEFAULT_PORT):
    """Takes a string of the form host1[:port],host2[:port]... and
    splits it into (host, port) tuples. If [:port] isn't present the
    default_port is used.

    Returns a set of 2-tuples containing the host name (or IP) followed by
    port number.

    :Parameters:
        - `hosts`: A string of the form host1[:port],host2[:port],...
        - `default_port`: The port number to use when one wasn't specified
          for a host.
    """
    nodes = []
    for entity in hosts.split(','):
        if not entity:
            raise ConfigurationError("Empty host "
                                     "(or extra comma in host list).")
        port = default_port
        # Unix socket entities don't have ports
        if entity.endswith('.sock'):
            port = None
        nodes.append(parse_host(entity, port))
    return nodes


# Prohibited characters in database name. DB names also can't have ".", but for
# backward-compat we allow "db.collection" in URI.
_BAD_DB_CHARS = re.compile('[' + re.escape(r'/ "$') + ']')


if PY3:
    # dnspython can return bytes or str from various parts
    # of its API depending on version. We always want str.
    def maybe_decode(text):
        if isinstance(text, bytes):
            return text.decode()
        return text
else:
    def maybe_decode(text):
        return text


_ALLOWED_TXT_OPTS = frozenset(
    ['authsource', 'authSource', 'replicaset', 'replicaSet'])


def _get_dns_srv_hosts(hostname):
    try:
        results = resolver.query('_mongodb._tcp.' + hostname, 'SRV')
    except Exception as exc:
        raise ConfigurationError(str(exc))
    return [(maybe_decode(res.target.to_text(omit_final_dot=True)), res.port)
            for res in results]


def _get_dns_txt_options(hostname):
    try:
        results = resolver.query(hostname, 'TXT')
    except (resolver.NoAnswer, resolver.NXDOMAIN):
        # No TXT records
        return None
    except Exception as exc:
        raise ConfigurationError(str(exc))
    if len(results) > 1:
        raise ConfigurationError('Only one TXT record is supported')
    return (
        b'&'.join([b''.join(res.strings) for res in results])).decode('utf-8')


def parse_uri(uri, default_port=DEFAULT_PORT, validate=True, warn=False):
    """Parse and validate a MongoDB URI.

    Returns a dict of the form::

        {
            'nodelist': <list of (host, port) tuples>,
            'username': <username> or None,
            'password': <password> or None,
            'database': <database name> or None,
            'collection': <collection name> or None,
            'options': <dict of MongoDB URI options>
        }

    If the URI scheme is "mongodb+srv://" DNS SRV and TXT lookups will be done
    to build nodelist and options.

    :Parameters:
        - `uri`: The MongoDB URI to parse.
        - `default_port`: The port number to use when one wasn't specified
          for a host in the URI.
        - `validate`: If ``True`` (the default), validate and normalize all
          options.
        - `warn` (optional): When validating, if ``True`` then will warn
          the user then ignore any invalid options or values. If ``False``,
          validation will error when options are unsupported or values are
          invalid.

    .. versionchanged:: 3.6
        Added support for mongodb+srv:// URIs

    .. versionchanged:: 3.5
        Return the original value of the ``readPreference`` MongoDB URI option
        instead of the validated read preference mode.

    .. versionchanged:: 3.1
        ``warn`` added so invalid options can be ignored.
    """
    if uri.startswith(SCHEME):
        is_srv = False
        scheme_free = uri[SCHEME_LEN:]
    elif uri.startswith(SRV_SCHEME):
        if not _HAVE_DNSPYTHON:
            raise ConfigurationError('The "dnspython" module must be '
                                     'installed to use mongodb+srv:// URIs')
        is_srv = True
        scheme_free = uri[SRV_SCHEME_LEN:]
    else:
        raise InvalidURI("Invalid URI scheme: URI must "
                         "begin with '%s' or '%s'" % (SCHEME, SRV_SCHEME))

    if not scheme_free:
        raise InvalidURI("Must provide at least one hostname or IP.")

    user = None
    passwd = None
    dbase = None
    collection = None
    options = {}

    host_part, _, path_part = scheme_free.partition('/')
    if not host_part:
        host_part = path_part
        path_part = ""

    if not path_part and '?' in host_part:
        raise InvalidURI("A '/' is required between "
                         "the host list and any options.")

    if '@' in host_part:
        userinfo, _, hosts = host_part.rpartition('@')
        user, passwd = parse_userinfo(userinfo)
    else:
        hosts = host_part

    if '/' in hosts:
        raise InvalidURI("Any '/' in a unix domain socket must be"
                         " percent-encoded: %s" % host_part)

    hosts = unquote_plus(hosts)

    if is_srv:
        nodes = split_hosts(hosts, default_port=None)
        if len(nodes) != 1:
            raise InvalidURI(
                "%s URIs must include one, "
                "and only one, hostname" % (SRV_SCHEME,))
        fqdn, port = nodes[0]
        if port is not None:
            raise InvalidURI(
                "%s URIs must not include a port number" % (SRV_SCHEME,))
        nodes = _get_dns_srv_hosts(fqdn)

        try:
            plist = fqdn.split(".")[1:]
        except Exception:
            raise ConfigurationError("Invalid URI host")
        slen = len(plist)
        if slen < 2:
            raise ConfigurationError("Invalid URI host")
        for node in nodes:
            try:
                nlist = node[0].split(".")[1:][-slen:]
            except Exception:
                raise ConfigurationError("Invalid SRV host")
            if plist != nlist:
                raise ConfigurationError("Invalid SRV host")

        dns_options = _get_dns_txt_options(fqdn)
        if dns_options:
            options = split_options(dns_options, validate, warn)
            if set(options) - _ALLOWED_TXT_OPTS:
                raise ConfigurationError(
                    "Only authSource and replicaSet are supported from DNS")
        options["ssl"] = True if validate else 'true'
    else:
        nodes = split_hosts(hosts, default_port=default_port)

    if path_part:
        if path_part[0] == '?':
            opts = unquote_plus(path_part[1:])
        else:
            dbase, _, opts = map(unquote_plus, path_part.partition('?'))
            if '.' in dbase:
                dbase, collection = dbase.split('.', 1)

            if _BAD_DB_CHARS.search(dbase):
                raise InvalidURI('Bad database name "%s"' % dbase)

        if opts:
            options.update(split_options(opts, validate, warn))

    if dbase is not None:
        dbase = unquote_plus(dbase)
    if collection is not None:
        collection = unquote_plus(collection)

    return {
        'nodelist': nodes,
        'username': user,
        'password': passwd,
        'database': dbase,
        'collection': collection,
        'options': options
    }


if __name__ == '__main__':
    import pprint
    import sys
    try:
        pprint.pprint(parse_uri(sys.argv[1]))
    except InvalidURI as exc:
        print(exc)
    sys.exit(0)
