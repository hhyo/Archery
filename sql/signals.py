from django.conf import settings
from django.db.models.signals import post_migrate
from django.dispatch import receiver


def ensure_workflow_log_column_widths():
    """Widen workflow_log.operation_type_desc for RU labels (was VARCHAR(10))."""
    from django.db import connection

    if connection.vendor != "mysql":
        return
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT CHARACTER_MAXIMUM_LENGTH
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'workflow_log'
              AND COLUMN_NAME = 'operation_type_desc'
            """)
        row = cursor.fetchone()
        if not row or row[0] is None or row[0] >= 64:
            return
        cursor.execute(
            "ALTER TABLE workflow_log MODIFY operation_type_desc VARCHAR(64) NOT NULL"
        )


@receiver(post_migrate)
def sync_permission_names_after_migrate(sender, **kwargs):
    """
    After the sql app finishes migrating, refresh permission display names.

    create_permissions runs on post_migrate for each app; we run once when
    sql migrates so custom Meta.permissions and model perms get Russian names.
    """
    if sender.name != "sql":
        return
    ensure_workflow_log_column_widths()
    # Late import: permission tables must exist.
    from sql.permission_i18n import sync_permission_names

    language = getattr(settings, "LANGUAGE_CODE", "ru") or "ru"
    verbosity = kwargs.get("verbosity", 1)
    sync_permission_names(language=language, verbosity=verbosity)
