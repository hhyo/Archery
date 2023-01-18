from mozilla_django_oidc import auth
from django.core.exceptions import SuspiciousOperation
from common.auth import init_user


class OIDCAuthenticationBackend(auth.OIDCAuthenticationBackend):
    def create_user(self, claims):
        """Return object for a newly created user account."""
        email = claims.get("email")
        username = claims.get("preferred_username")
        display = claims.get("name")
        if not email or not username or not display:
            raise SuspiciousOperation(
                "email and name and preferred_username should not be empty"
            )
        user = self.UserModel.objects.create_user(
            username, email=email, display=display
        )
        init_user(user)
        return user

    def describe_user_by_claims(self, claims):
        username = claims.get("preferred_username")
        return "username {}".format(username)

    def filter_users_by_claims(self, claims):
        """Return all users matching the username."""
        username = claims.get("preferred_username")
        if not username or username == "admin":
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(username__iexact=username)
