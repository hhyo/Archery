from mozilla_django_oidc import auth
from django.core.exceptions import SuspiciousOperation

class OIDCAuthenticationBackend(auth.OIDCAuthenticationBackend):
    def create_user(self, claims):
        """Return object for a newly created user account."""
        email = claims.get("email")
        username = claims.get("preferred_username")
        display = claims.get("name")
        if not email or not username or not display:
            raise SuspiciousOperation("email and name and preferred_username should not be empty")
        if username == "admin":
            raise SuspiciousOperation("admin never get access from oidc")
        return self.UserModel.objects.create_user(username, email=email, display=display)
