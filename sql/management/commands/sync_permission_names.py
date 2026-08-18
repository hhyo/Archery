from django.conf import settings
from django.core.management.base import BaseCommand

from sql.permission_i18n import sync_permission_names


class Command(BaseCommand):
    help = (
        "Rewrite auth_permission.name using gettext for the given language "
        "(default: settings.LANGUAGE_CODE). Run after migrate + compilemessages "
        "so Django admin and group forms show labels in the active language."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--language",
            default=getattr(settings, "LANGUAGE_CODE", "zh-hans"),
            help="Language code to activate (default: LANGUAGE_CODE)",
        )

    def handle(self, *args, **options):
        sync_permission_names(
            language=options["language"],
            verbosity=options["verbosity"],
        )
