from django.apps import AppConfig


class SqlConfig(AppConfig):
    name = "sql"
    verbose_name = "SQL"

    def ready(self):
        # Avoid import cycles at app registry load time.
        from sql import signals  # noqa: F401
