# Copyright (c) 2009, Peter Sagerson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# - Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# - Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
LDAP authentication backend

Complete documentation can be found in docs/howto/auth-ldap.txt (or the thing it
compiles to).

Use of this backend requires the python-ldap module. To support unit tests, we
import ldap in a single centralized place (config._LDAPConfig) so that the test
harness can insert a mock object.

A few notes on naming conventions. If an identifier ends in _dn, it is a string
representation of a distinguished name. If it ends in _info, it is a 2-tuple
containing a DN and a dictionary of lists of attributes. ldap.search_s returns a
list of such structures. An identifier that ends in _attrs is the dictionary of
attributes from the _info structure.

A connection is an LDAPObject that has been successfully bound with a DN and
password. The identifier 'user' always refers to a User model object; LDAP user
information will be user_dn or user_info.

Additional classes can be found in the config module next to this one.
"""

import copy
import operator
import pprint
import re
import warnings
from functools import reduce

import django.conf
import django.dispatch
import ldap
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.utils.inspect import func_supports_parameter

from django_auth_ldap.config import (
    ConfigurationWarning,
    LDAPGroupQuery,
    LDAPSearch,
    _LDAPConfig,
)

logger = _LDAPConfig.get_logger()


# Exported signals

# Allows clients to perform custom user population.
populate_user = django.dispatch.Signal(providing_args=["user", "ldap_user"])

# Allows clients to inspect and perform special handling of LDAPError
# exceptions. Exceptions raised by handlers will be propagated out.
ldap_error = django.dispatch.Signal(providing_args=["context", "user", "exception"])


class LDAPBackend:
    """
    The main backend class. This implements the auth backend API, although it
    actually delegates most of its work to _LDAPUser, which is defined next.
    """

    supports_anonymous_user = False
    supports_object_permissions = True
    supports_inactive_user = False

    _settings = None
    _ldap = None  # The cached ldap module (or mock object)

    # This is prepended to our internal setting names to produce the names we
    # expect in Django's settings file. Subclasses can change this in order to
    # support multiple collections of settings.
    settings_prefix = "AUTH_LDAP_"

    # Default settings to override the built-in defaults.
    default_settings = {}

    def __getstate__(self):
        """
        Exclude certain cached properties from pickling.
        """
        return {
            k: v for k, v in self.__dict__.items() if k not in ["_settings", "_ldap"]
        }

    @property
    def settings(self):
        if self._settings is None:
            self._settings = LDAPSettings(self.settings_prefix, self.default_settings)

        return self._settings

    @settings.setter
    def settings(self, settings):
        self._settings = settings

    @property
    def ldap(self):
        if self._ldap is None:
            options = getattr(django.conf.settings, "AUTH_LDAP_GLOBAL_OPTIONS", None)

            self._ldap = _LDAPConfig.get_ldap(options)

        return self._ldap

    def get_user_model(self):
        """
        By default, this will return the model class configured by
        AUTH_USER_MODEL. Subclasses may wish to override it and return a proxy
        model.
        """
        return get_user_model()

    #
    # The Django auth backend API
    #

    def authenticate(self, request, username=None, password=None, **kwargs):
        if password or self.settings.PERMIT_EMPTY_PASSWORD:
            ldap_user = _LDAPUser(self, username=username.strip(), request=request)
            user = self.authenticate_ldap_user(ldap_user, password)
        else:
            logger.debug("Rejecting empty password for {}".format(username))
            user = None

        return user

    def get_user(self, user_id):
        user = None

        try:
            user = self.get_user_model().objects.get(pk=user_id)
            _LDAPUser(self, user=user)  # This sets user.ldap_user
        except ObjectDoesNotExist:
            pass

        return user

    def has_perm(self, user, perm, obj=None):
        return perm in self.get_all_permissions(user, obj)

    def has_module_perms(self, user, app_label):
        for perm in self.get_all_permissions(user):
            if perm[: perm.index(".")] == app_label:
                return True

        return False

    def get_all_permissions(self, user, obj=None):
        return self.get_group_permissions(user, obj)

    def get_group_permissions(self, user, obj=None):
        if not hasattr(user, "ldap_user") and self.settings.AUTHORIZE_ALL_USERS:
            _LDAPUser(self, user=user)  # This sets user.ldap_user

        if hasattr(user, "ldap_user"):
            permissions = user.ldap_user.get_group_permissions()
        else:
            permissions = set()

        return permissions

    #
    # Bonus API: populate the Django user from LDAP without authenticating.
    #

    def populate_user(self, username):
        ldap_user = _LDAPUser(self, username=username)
        return ldap_user.populate_user()

    #
    # Hooks for subclasses
    #

    def authenticate_ldap_user(self, ldap_user, password):
        """
        Returns an authenticated Django user or None.
        """
        return ldap_user.authenticate(password)

    def get_or_build_user(self, username, ldap_user):
        """
        This must return a (User, built) 2-tuple for the given LDAP user.

        username is the Django-friendly username of the user. ldap_user.dn is
        the user's DN and ldap_user.attrs contains all of their LDAP
        attributes.

        The returned User object may be an unsaved model instance.

        """
        model = self.get_user_model()

        if self.settings.USER_QUERY_FIELD:
            query_field = self.settings.USER_QUERY_FIELD
            query_value = ldap_user.attrs[self.settings.USER_ATTR_MAP[query_field]][0]
            lookup = query_field
        else:
            query_field = model.USERNAME_FIELD
            query_value = username.lower()
            lookup = "{}__iexact".format(query_field)

        try:
            user = model.objects.get(**{lookup: query_value})
        except model.DoesNotExist:
            user = model(**{query_field: query_value})
            built = True
        else:
            built = False

        return (user, built)

    def ldap_to_django_username(self, username):
        return username

    def django_to_ldap_username(self, username):
        return username


class _LDAPUser:
    """
    Represents an LDAP user and ultimately fields all requests that the
    backend receives. This class exists for two reasons. First, it's
    convenient to have a separate object for each request so that we can use
    object attributes without running into threading problems. Second, these
    objects get attached to the User objects, which allows us to cache
    expensive LDAP information, especially around groups and permissions.

    self.backend is a reference back to the LDAPBackend instance, which we need
    to access the ldap module and any hooks that a subclass has overridden.
    """

    class AuthenticationFailed(Exception):
        pass

    # Defaults
    _user = None
    _user_dn = None
    _user_attrs = None
    _groups = None
    _group_permissions = None
    _connection = None
    _connection_bound = False

    #
    # Initialization
    #

    def __init__(self, backend, username=None, user=None, request=None):
        """
        A new LDAPUser must be initialized with either a username or an
        authenticated User object. If a user is given, the username will be
        ignored.
        """
        self.backend = backend
        self._username = username
        self._request = request

        if user is not None:
            self._set_authenticated_user(user)

        if username is None and user is None:
            raise Exception("Internal error: _LDAPUser improperly initialized.")

    def __deepcopy__(self, memo):
        obj = object.__new__(self.__class__)
        obj.backend = self.backend
        obj._user = copy.deepcopy(self._user, memo)

        # This is all just cached immutable data. There's no point copying it.
        obj._username = self._username
        obj._user_dn = self._user_dn
        obj._user_attrs = self._user_attrs
        obj._groups = self._groups
        obj._group_permissions = self._group_permissions

        # The connection couldn't be copied even if we wanted to
        obj._connection = self._connection
        obj._connection_bound = self._connection_bound

        return obj

    def __getstate__(self):
        """
        Most of our properties are cached from the LDAP server. We only want to
        pickle a few crucial things.
        """
        return {
            k: v
            for k, v in self.__dict__.items()
            if k in ["backend", "_username", "_user"]
        }

    def _set_authenticated_user(self, user):
        self._user = user
        self._username = self.backend.django_to_ldap_username(user.get_username())

        user.ldap_user = self
        user.ldap_username = self._username

    @property
    def ldap(self):
        return self.backend.ldap

    @property
    def settings(self):
        return self.backend.settings

    #
    # Entry points
    #

    def authenticate(self, password):
        """
        Authenticates against the LDAP directory and returns the corresponding
        User object if successful. Returns None on failure.
        """
        user = None

        try:
            self._authenticate_user_dn(password)
            self._check_requirements()
            self._get_or_create_user()

            user = self._user
        except self.AuthenticationFailed as e:
            logger.debug("Authentication failed for {}: {}".format(self._username, e))
        except ldap.LDAPError as e:
            results = ldap_error.send(
                self.backend.__class__,
                context="authenticate",
                user=self._user,
                exception=e,
            )
            if len(results) == 0:
                logger.warning(
                    "Caught LDAPError while authenticating {}: {}".format(
                        self._username, pprint.pformat(e)
                    )
                )
        except Exception as e:
            logger.warning("{} while authenticating {}".format(e, self._username))
            raise

        return user

    def get_group_permissions(self):
        """
        If allowed by the configuration, this returns the set of permissions
        defined by the user's LDAP group memberships.
        """
        if self._group_permissions is None:
            self._group_permissions = set()

            if self.settings.FIND_GROUP_PERMS:
                try:
                    if self.dn is not None:
                        self._load_group_permissions()
                except ldap.LDAPError as e:
                    results = ldap_error.send(
                        self.backend.__class__,
                        context="get_group_permissions",
                        user=self._user,
                        exception=e,
                    )
                    if len(results) == 0:
                        logger.warning(
                            "Caught LDAPError loading group permissions: {}".format(
                                pprint.pformat(e)
                            )
                        )

        return self._group_permissions

    def populate_user(self):
        """
        Populates the Django user object using the default bind credentials.
        """
        user = None

        try:
            # self.attrs will only be non-None if we were able to load this user
            # from the LDAP directory, so this filters out nonexistent users.
            if self.attrs is not None:
                self._get_or_create_user(force_populate=True)

            user = self._user
        except ldap.LDAPError as e:
            results = ldap_error.send(
                self.backend.__class__,
                context="populate_user",
                user=self._user,
                exception=e,
            )
            if len(results) == 0:
                logger.warning(
                    "Caught LDAPError while authenticating {}: {}".format(
                        self._username, pprint.pformat(e)
                    )
                )
        except Exception as e:
            logger.warning("{} while authenticating {}".format(e, self._username))
            raise

        return user

    #
    # Public properties (callbacks). These are all lazy for performance reasons.
    #

    @property
    def dn(self):
        if self._user_dn is None:
            self._load_user_dn()

        return self._user_dn

    @property
    def attrs(self):
        if self._user_attrs is None:
            self._load_user_attrs()

        return self._user_attrs

    @property
    def group_dns(self):
        return self._get_groups().get_group_dns()

    @property
    def group_names(self):
        return self._get_groups().get_group_names()

    @property
    def connection(self):
        if not self._connection_bound:
            self._bind()

        return self._get_connection()

    #
    # Authentication
    #

    def _authenticate_user_dn(self, password):
        """
        Binds to the LDAP server with the user's DN and password. Raises
        AuthenticationFailed on failure.
        """
        if self.dn is None:
            raise self.AuthenticationFailed("failed to map the username to a DN.")

        try:
            sticky = self.settings.BIND_AS_AUTHENTICATING_USER

            self._bind_as(self.dn, password, sticky=sticky)
        except ldap.INVALID_CREDENTIALS:
            raise self.AuthenticationFailed("user DN/password rejected by LDAP server.")

    def _load_user_attrs(self):
        if self.dn is not None:
            search = LDAPSearch(
                self.dn, ldap.SCOPE_BASE, attrlist=self.settings.USER_ATTRLIST
            )
            results = search.execute(self.connection)

            if results is not None and len(results) > 0:
                self._user_attrs = results[0][1]

    def _load_user_dn(self):
        """
        Populates self._user_dn with the distinguished name of our user.

        This will either construct the DN from a template in
        AUTH_LDAP_USER_DN_TEMPLATE or connect to the server and search for it.
        If we have to search, we'll cache the DN.

        """
        if self._using_simple_bind_mode():
            self._user_dn = self._construct_simple_user_dn()
        else:
            if self.settings.CACHE_TIMEOUT > 0:
                cache_key = valid_cache_key(
                    "django_auth_ldap.user_dn.{}".format(self._username)
                )
                self._user_dn = cache.get_or_set(
                    cache_key, self._search_for_user_dn, self.settings.CACHE_TIMEOUT
                )
            else:
                self._user_dn = self._search_for_user_dn()

    def _using_simple_bind_mode(self):
        return self.settings.USER_DN_TEMPLATE is not None

    def _construct_simple_user_dn(self):
        template = self.settings.USER_DN_TEMPLATE
        username = ldap.dn.escape_dn_chars(self._username)
        return template % {"user": username}

    def _search_for_user_dn(self):
        """
        Searches the directory for a user matching AUTH_LDAP_USER_SEARCH.
        Populates self._user_dn and self._user_attrs.
        """
        search = self.settings.USER_SEARCH
        if search is None:
            raise ImproperlyConfigured(
                "AUTH_LDAP_USER_SEARCH must be an LDAPSearch instance."
            )

        results = search.execute(self.connection, {"user": self._username})
        if results is not None and len(results) == 1:
            (user_dn, self._user_attrs) = next(iter(results))
        else:
            user_dn = None

        return user_dn

    def _check_requirements(self):
        """
        Checks all authentication requirements beyond credentials. Raises
        AuthenticationFailed on failure.
        """
        self._check_required_group()
        self._check_denied_group()

    def _check_required_group(self):
        """
        Returns True if the group requirement (AUTH_LDAP_REQUIRE_GROUP) is
        met. Always returns True if AUTH_LDAP_REQUIRE_GROUP is None.
        """
        required_group_dn = self.settings.REQUIRE_GROUP

        if required_group_dn is not None:
            if not isinstance(required_group_dn, LDAPGroupQuery):
                required_group_dn = LDAPGroupQuery(required_group_dn)
            result = required_group_dn.resolve(self)
            if not result:
                raise self.AuthenticationFailed(
                    "user does not satisfy AUTH_LDAP_REQUIRE_GROUP"
                )

        return True

    def _check_denied_group(self):
        """
        Returns True if the negative group requirement (AUTH_LDAP_DENY_GROUP)
        is met. Always returns True if AUTH_LDAP_DENY_GROUP is None.
        """
        denied_group_dn = self.settings.DENY_GROUP

        if denied_group_dn is not None:
            is_member = self._get_groups().is_member_of(denied_group_dn)
            if is_member:
                raise self.AuthenticationFailed(
                    "user does not satisfy AUTH_LDAP_DENY_GROUP"
                )

        return True

    #
    # User management
    #

    def _get_or_create_user(self, force_populate=False):
        """
        Loads the User model object from the database or creates it if it
        doesn't exist. Also populates the fields, subject to
        AUTH_LDAP_ALWAYS_UPDATE_USER.
        """
        save_user = False

        username = self.backend.ldap_to_django_username(self._username)

        self._user, built = self.backend.get_or_build_user(username, self)
        self._user.ldap_user = self
        self._user.ldap_username = self._username

        should_populate = force_populate or self.settings.ALWAYS_UPDATE_USER or built

        if built:
            if self.settings.NO_NEW_USERS:
                raise self.AuthenticationFailed(
                    "user does not satisfy AUTH_LDAP_NO_NEW_USERS"
                )

            logger.debug("Creating Django user {}".format(username))
            self._user.set_unusable_password()
            save_user = True

        if should_populate:
            logger.debug("Populating Django user {}".format(username))
            self._populate_user()
            save_user = True

            # Give the client a chance to finish populating the user just
            # before saving.
            populate_user.send(self.backend.__class__, user=self._user, ldap_user=self)

        if save_user:
            self._user.save()

        # This has to wait until we're sure the user has a pk.
        if self.settings.MIRROR_GROUPS or self.settings.MIRROR_GROUPS_EXCEPT:
            self._normalize_mirror_settings()
            self._mirror_groups()

    def _populate_user(self):
        """
        Populates our User object with information from the LDAP directory.
        """
        self._populate_user_from_attributes()
        self._populate_user_from_group_memberships()

    def _populate_user_from_attributes(self):
        for field, attr in self.settings.USER_ATTR_MAP.items():
            try:
                value = self.attrs[attr][0]
            except (TypeError, LookupError):
                # TypeError occurs when self.attrs is None as we were unable to
                # load this user's attributes.
                logger.warning(
                    "{} does not have a value for the attribute {}".format(
                        self.dn, attr
                    )
                )
            else:
                setattr(self._user, field, value)

    def _populate_user_from_group_memberships(self):
        for field, group_dns in self.settings.USER_FLAGS_BY_GROUP.items():
            try:
                query = self._normalize_group_dns(group_dns)
            except ValueError as e:
                raise ImproperlyConfigured(
                    "{}: {}", self.settings._name("USER_FLAGS_BY_GROUP"), e
                )

            value = query.resolve(self)
            setattr(self._user, field, value)

    def _normalize_group_dns(self, group_dns):
        """
        Converts one or more group DNs to an LDAPGroupQuery.

        group_dns may be a string, a non-empty list or tuple of strings, or an
        LDAPGroupQuery. The result will be an LDAPGroupQuery. A list or tuple
        will be joined with the | operator.

        """
        if isinstance(group_dns, LDAPGroupQuery):
            query = group_dns
        elif isinstance(group_dns, str):
            query = LDAPGroupQuery(group_dns)
        elif isinstance(group_dns, (list, tuple)) and len(group_dns) > 0:
            query = reduce(operator.or_, map(LDAPGroupQuery, group_dns))
        else:
            raise ValueError(group_dns)

        return query

    def _normalize_mirror_settings(self):
        """
        Validates the group mirroring settings and converts them as necessary.
        """

        def malformed_mirror_groups_except():
            return ImproperlyConfigured(
                "{} must be a collection of group names".format(
                    self.settings._name("MIRROR_GROUPS_EXCEPT")
                )
            )

        def malformed_mirror_groups():
            return ImproperlyConfigured(
                "{} must be True or a collection of group names".format(
                    self.settings._name("MIRROR_GROUPS")
                )
            )

        mge = self.settings.MIRROR_GROUPS_EXCEPT
        mg = self.settings.MIRROR_GROUPS

        if mge is not None:
            if isinstance(mge, (set, frozenset)):
                pass
            elif isinstance(mge, (list, tuple)):
                mge = self.settings.MIRROR_GROUPS_EXCEPT = frozenset(mge)
            else:
                raise malformed_mirror_groups_except()

            if not all(isinstance(value, str) for value in mge):
                raise malformed_mirror_groups_except()
            elif mg:
                warnings.warn(
                    ConfigurationWarning(
                        "Ignoring {} in favor of {}".format(
                            self.settings._name("MIRROR_GROUPS"),
                            self.settings._name("MIRROR_GROUPS_EXCEPT"),
                        )
                    )
                )
                mg = self.settings.MIRROR_GROUPS = None

        if mg is not None:
            if isinstance(mg, (bool, set, frozenset)):
                pass
            elif isinstance(mg, (list, tuple)):
                mg = self.settings.MIRROR_GROUPS = frozenset(mg)
            else:
                raise malformed_mirror_groups()

            if isinstance(mg, (set, frozenset)) and (
                not all(isinstance(value, str) for value in mg)
            ):
                raise malformed_mirror_groups()

    def _mirror_groups(self):
        """
        Mirrors the user's LDAP groups in the Django database and updates the
        user's membership.
        """
        target_group_names = frozenset(self._get_groups().get_group_names())
        current_group_names = frozenset(
            self._user.groups.values_list("name", flat=True).iterator()
        )

        # These were normalized to sets above.
        MIRROR_GROUPS_EXCEPT = self.settings.MIRROR_GROUPS_EXCEPT
        MIRROR_GROUPS = self.settings.MIRROR_GROUPS

        # If the settings are white- or black-listing groups, we'll update
        # target_group_names such that we won't modify the membership of groups
        # beyond our purview.
        if isinstance(MIRROR_GROUPS_EXCEPT, (set, frozenset)):
            target_group_names = (target_group_names - MIRROR_GROUPS_EXCEPT) | (
                current_group_names & MIRROR_GROUPS_EXCEPT
            )
        elif isinstance(MIRROR_GROUPS, (set, frozenset)):
            target_group_names = (target_group_names & MIRROR_GROUPS) | (
                current_group_names - MIRROR_GROUPS
            )

        if target_group_names != current_group_names:
            existing_groups = list(
                Group.objects.filter(name__in=target_group_names).iterator()
            )
            existing_group_names = frozenset(group.name for group in existing_groups)

            new_groups = [
                Group.objects.get_or_create(name=name)[0]
                for name in target_group_names
                if name not in existing_group_names
            ]

            self._user.groups.set(existing_groups + new_groups)

    #
    # Group information
    #

    def _load_group_permissions(self):
        """
        Populates self._group_permissions based on LDAP group membership and
        Django group permissions.
        """
        group_names = self._get_groups().get_group_names()

        perms = Permission.objects.filter(group__name__in=group_names)
        perms = perms.values_list("content_type__app_label", "codename")
        perms = perms.order_by()

        self._group_permissions = {"{}.{}".format(ct, name) for ct, name in perms}

    def _get_groups(self):
        """
        Returns an _LDAPUserGroups object, which can determine group
        membership.
        """
        if self._groups is None:
            self._groups = _LDAPUserGroups(self)

        return self._groups

    #
    # LDAP connection
    #

    def _bind(self):
        """
        Binds to the LDAP server with AUTH_LDAP_BIND_DN and
        AUTH_LDAP_BIND_PASSWORD.
        """
        self._bind_as(self.settings.BIND_DN, self.settings.BIND_PASSWORD, sticky=True)

    def _bind_as(self, bind_dn, bind_password, sticky=False):
        """
        Binds to the LDAP server with the given credentials. This does not trap
        exceptions.

        If sticky is True, then we will consider the connection to be bound for
        the life of this object. If False, then the caller only wishes to test
        the credentials, after which the connection will be considered unbound.
        """
        self._get_connection().simple_bind_s(bind_dn, bind_password)

        self._connection_bound = sticky

    def _get_connection(self):
        """
        Returns our cached LDAPObject, which may or may not be bound.
        """
        if self._connection is None:
            uri = self.settings.SERVER_URI
            if callable(uri):
                if func_supports_parameter(uri, "request"):
                    uri = uri(self._request)
                else:
                    warnings.warn(
                        "Update AUTH_LDAP_SERVER_URI callable %s.%s to accept "
                        "a positional `request` argument. Support for callables "
                        "accepting no arguments will be removed in a future "
                        "version." % (uri.__module__, uri.__name__),
                        DeprecationWarning,
                    )
                    uri = uri()

            self._connection = self.backend.ldap.initialize(uri, bytes_mode=False)

            for opt, value in self.settings.CONNECTION_OPTIONS.items():
                self._connection.set_option(opt, value)

            if self.settings.START_TLS:
                logger.debug("Initiating TLS")
                self._connection.start_tls_s()

        return self._connection


class _LDAPUserGroups:
    """
    Represents the set of groups that a user belongs to.
    """

    def __init__(self, ldap_user):
        self.settings = ldap_user.settings
        self._ldap_user = ldap_user
        self._group_type = None
        self._group_search = None
        self._group_infos = None
        self._group_dns = None
        self._group_names = None

        self._init_group_settings()

    def _init_group_settings(self):
        """
        Loads the settings we need to deal with groups.

        Raises ImproperlyConfigured if anything's not right.

        """
        self._group_type = self.settings.GROUP_TYPE
        if self._group_type is None:
            raise ImproperlyConfigured(
                "AUTH_LDAP_GROUP_TYPE must be an LDAPGroupType instance."
            )

        self._group_search = self.settings.GROUP_SEARCH
        if self._group_search is None:
            raise ImproperlyConfigured(
                "AUTH_LDAP_GROUP_SEARCH must be an LDAPSearch instance."
            )

    def get_group_names(self):
        """
        Returns the set of Django group names that this user belongs to by
        virtue of LDAP group memberships.
        """
        if self._group_names is None:
            self._load_cached_attr("_group_names")

        if self._group_names is None:
            group_infos = self._get_group_infos()
            self._group_names = {
                self._group_type.group_name_from_info(group_info)
                for group_info in group_infos
            }
            self._cache_attr("_group_names")

        return self._group_names

    def is_member_of(self, group_dn):
        """
        Returns true if our user is a member of the given group.
        """
        is_member = None

        # Normalize the DN
        group_dn = group_dn.lower()

        # If we have self._group_dns, we'll use it. Otherwise, we'll try to
        # avoid the cost of loading it.
        if self._group_dns is None:
            is_member = self._group_type.is_member(self._ldap_user, group_dn)

        if is_member is None:
            is_member = group_dn in self.get_group_dns()

        logger.debug(
            "{} is{}a member of {}".format(
                self._ldap_user.dn, is_member and " " or " not ", group_dn
            )
        )

        return is_member

    def get_group_dns(self):
        """
        Returns a (cached) set of the distinguished names in self._group_infos.
        """
        if self._group_dns is None:
            group_infos = self._get_group_infos()
            self._group_dns = {group_info[0] for group_info in group_infos}

        return self._group_dns

    def _get_group_infos(self):
        """
        Returns a (cached) list of group_info structures for the groups that our
        user is a member of.
        """
        if self._group_infos is None:
            self._group_infos = self._group_type.user_groups(
                self._ldap_user, self._group_search
            )

        return self._group_infos

    def _load_cached_attr(self, attr_name):
        if self.settings.CACHE_TIMEOUT > 0:
            key = self._cache_key(attr_name)
            value = cache.get(key)
            setattr(self, attr_name, value)

    def _cache_attr(self, attr_name):
        if self.settings.CACHE_TIMEOUT > 0:
            key = self._cache_key(attr_name)
            value = getattr(self, attr_name, None)
            cache.set(key, value, self.settings.CACHE_TIMEOUT)

    def _cache_key(self, attr_name):
        """
        Memcache keys can't have spaces in them, so we'll remove them from the
        DN for maximum compatibility.
        """
        dn = self._ldap_user.dn
        return valid_cache_key(
            "auth_ldap.{}.{}.{}".format(self.__class__.__name__, attr_name, dn)
        )


class LDAPSettings:
    """
    This is a simple class to take the place of the global settings object. An
    instance will contain all of our settings as attributes, with default values
    if they are not specified by the configuration.
    """

    _prefix = "AUTH_LDAP_"

    defaults = {
        "ALWAYS_UPDATE_USER": True,
        "AUTHORIZE_ALL_USERS": False,
        "BIND_AS_AUTHENTICATING_USER": False,
        "BIND_DN": "",
        "BIND_PASSWORD": "",
        "CONNECTION_OPTIONS": {},
        "DENY_GROUP": None,
        "FIND_GROUP_PERMS": False,
        "CACHE_TIMEOUT": 0,
        "GROUP_SEARCH": None,
        "GROUP_TYPE": None,
        "MIRROR_GROUPS": None,
        "MIRROR_GROUPS_EXCEPT": None,
        "PERMIT_EMPTY_PASSWORD": False,
        "REQUIRE_GROUP": None,
        "NO_NEW_USERS": False,
        "SERVER_URI": "ldap://localhost",
        "START_TLS": False,
        "USER_QUERY_FIELD": None,
        "USER_ATTRLIST": None,
        "USER_ATTR_MAP": {},
        "USER_DN_TEMPLATE": None,
        "USER_FLAGS_BY_GROUP": {},
        "USER_SEARCH": None,
    }

    def __init__(self, prefix="AUTH_LDAP_", defaults={}):
        """
        Loads our settings from django.conf.settings, applying defaults for any
        that are omitted.
        """
        self._prefix = prefix

        defaults = dict(self.defaults, **defaults)

        for name, default in defaults.items():
            value = getattr(django.conf.settings, prefix + name, default)
            setattr(self, name, value)

        # Compatibility with old caching settings.
        if getattr(
            django.conf.settings,
            self._name("CACHE_GROUPS"),
            defaults.get("CACHE_GROUPS"),
        ):
            warnings.warn(
                "Found deprecated setting AUTH_LDAP_CACHE_GROUP. Use "
                "AUTH_LDAP_CACHE_TIMEOUT instead.",
                DeprecationWarning,
            )
            self.CACHE_TIMEOUT = getattr(
                django.conf.settings,
                self._name("GROUP_CACHE_TIMEOUT"),
                defaults.get("GROUP_CACHE_TIMEOUT", 3600),
            )

    def _name(self, suffix):
        return self._prefix + suffix


def valid_cache_key(key):
    """
    Sanitizes a cache key for memcached.
    """
    return re.sub(r"\s+", "+", key)[:250]
