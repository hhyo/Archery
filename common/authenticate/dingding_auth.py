from django_auth_dingding import auth
from common.auth import init_user


class DingdingAuthenticationBackend(auth.DingdingAuthenticationBackend):
    def create_user(self, claims):
        """Return object for a newly created user account."""
        user = super().create_user(claims)
        init_user(user)
        return user
