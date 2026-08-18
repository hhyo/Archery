"""Sync auth_permission.name to the active UI language (Russian).

Django stores permission display names in the DB at create_permissions time.
Those rows are not re-translated when LANGUAGE_CODE changes, so redeploys need
an explicit sync after migrate (and after compilemessages).
"""

from __future__ import annotations

from django.apps import apps
from django.contrib.auth.management import _get_all_permissions
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils import translation
from django.utils.encoding import force_str
from django.utils.translation import gettext as _

# Builtin permission name format from django.contrib.auth.management
_BUILTIN_PREFIXES = (
    ("Can add ", "Добавить: "),
    ("Can change ", "Изменить: "),
    ("Can delete ", "Удалить: "),
    ("Can view ", "Просмотр: "),
    # Chinese Django-style leftovers from older installs
    ("可以添加 ", "Добавить: "),
    ("可以修改 ", "Изменить: "),
    ("可以删除 ", "Удалить: "),
    ("可以查看 ", "Просмотр: "),
)


def localize_permission_name(name: str) -> str:
    """Translate a permission display name under the currently active language."""
    translated = _(name)
    if translated != name:
        return translated[:255]
    for en_or_zh, ru in _BUILTIN_PREFIXES:
        if name.startswith(en_or_zh):
            rest = name[len(en_or_zh) :]
            return f"{ru}{_(rest)}"[:255]
    return name[:255]


def expected_permission_name(codename: str, raw_name) -> str:
    """Build the Russian display name for a (codename, Meta name) pair."""
    name = force_str(raw_name)
    # Builtin perms are English "Can add <verbose>"; custom ones are gettext msgids.
    if codename.startswith(("add_", "change_", "delete_", "view_")):
        return localize_permission_name(name)
    return localize_permission_name(name)


def sync_permission_names(language: str = "ru", verbosity: int = 1) -> int:
    """
    Rewrite auth_permission.name for all known model permissions.

    Returns the number of rows updated.
    """
    translation.activate(language)
    updated = 0
    seen = set()

    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            opts = model._meta
            ctype = ContentType.objects.get_for_model(model, for_concrete_model=False)
            for codename, raw_name in _get_all_permissions(opts):
                seen.add((ctype.pk, codename))
                new_name = expected_permission_name(codename, raw_name)
                qs = Permission.objects.filter(content_type=ctype, codename=codename)
                for perm in qs.only("pk", "name", "codename"):
                    if perm.name != new_name:
                        old_name = perm.name
                        Permission.objects.filter(pk=perm.pk).update(name=new_name)
                        updated += 1
                        if verbosity >= 2:
                            print(f"{perm.codename}: {old_name!r} -> {new_name!r}")

    # Orphan / leftover rows (e.g. removed models): best-effort gettext.
    for perm in Permission.objects.iterator():
        key = (perm.content_type_id, perm.codename)
        if key in seen:
            continue
        new_name = localize_permission_name(perm.name)
        if new_name != perm.name:
            Permission.objects.filter(pk=perm.pk).update(name=new_name)
            updated += 1

    if verbosity >= 1:
        print(f"sync_permission_names({language}): updated {updated} row(s)")
    return updated
