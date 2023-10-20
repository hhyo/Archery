from django.contrib.auth.models import User
from django_cas_ng.backends import CASBackend


class CASAuthenticationBackend(CASBackend):
    def get_user_info_ldap(self, user: User):
        """
        If CAS uses LDAP as the database, it can read user information from LDAP.
        Using the django_auth_ldap module to search for LDAP user information
        """
        from django_auth_ldap.backend import LDAPBackend

        ldap_backend = LDAPBackend()
        try:
            ldap_user = ldap_backend.populate_user(user.username)
            if ldap_user is None:
                return None
            # Retrieve field information based on the LDAP attribute map.
            user.email = ldap_user.ldap_user.attrs["mail"][0]
            user.display = ldap_user.ldap_user.attrs["cn"][0]
            # If the Feishu app ID has been configured, query the user ID.
            return user
        except Exception as e:
            print(str(e))
            return None
