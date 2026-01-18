from mozilla_django_oidc import auth
from django.core.exceptions import SuspiciousOperation
from common.auth import init_user
from django.conf import settings


class OIDCAuthenticationBackend(auth.OIDCAuthenticationBackend):
    def _get_oidc_attr_map(self):
        """
        Safely retrieve OIDC_USER_ATTR_MAP, handling both dict (normal) and str (misconfiguration/env issue).
        Format for str: "username=preferred_username,display=name,email=email"
        """
        attr_map = getattr(settings, "OIDC_USER_ATTR_MAP", {})
        if isinstance(attr_map, dict):
            return attr_map

        # Fallback for string configuration
        parsed_map = {}
        if isinstance(attr_map, str):
            pairs = attr_map.split(",")
            for pair in pairs:
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    parsed_map[key.strip()] = value.strip()

        return parsed_map

    def create_user(self, claims):
        """Return object for a newly created user account."""
        attr_map = self._get_oidc_attr_map()
        username_key = attr_map.get("username", "preferred_username")
        display_key = attr_map.get("display", "name")
        email_key = attr_map.get("email", "email")

        username = claims.get(username_key)
        display = claims.get(display_key)
        email = claims.get(email_key)

        if not username or not display or not email:
            missing_fields = []
            if not username:
                missing_fields.append(username_key)
            if not display:
                missing_fields.append(display_key)
            if not email:
                missing_fields.append(email_key)

            raise SuspiciousOperation(
                (
                    "OIDC configuration error.\n"
                    "Missing OIDC fields: {missing}\n"
                    "Received claims: {claims}\n"
                    "Please ensure your .env file contains a correct OIDC_USER_ATTR_MAP.\n"
                    "Example:\n"
                    "    OIDC_USER_ATTR_MAP=username=preferred_username,display=name,email=email\n"
                    "Or refer to https://github.com/hhyo/archery/wiki for more details."
                ).format(
                    missing=", ".join(missing_fields),
                    claims=claims,
                )
            )

        user = self.UserModel.objects.create_user(
            username, display=display, email=email
        )
        init_user(user)
        return user

    def describe_user_by_claims(self, claims):
        attr_map = self._get_oidc_attr_map()
        username = claims.get(attr_map.get("username", "preferred_username"))
        return "username {}".format(username)

    def filter_users_by_claims(self, claims):
        """Return all users matching the username."""
        attr_map = self._get_oidc_attr_map()
        username = claims.get(attr_map.get("username", "preferred_username"))
        if not username or username == "admin":
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(username__iexact=username)
