"""Sync auth_permission.name to the active UI language.

Django stores permission display names in the DB at create_permissions time.
Those rows are not re-translated when LANGUAGE_CODE changes, so redeploys need
an explicit sync after migrate (and after compilemessages).
"""

from __future__ import annotations

from django.apps import apps
from django.conf import settings
from django.contrib.auth.management import _get_all_permissions
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils import translation
from django.utils.encoding import force_str
from django.utils.translation import gettext as _

# Builtin Django prefixes and leftover labels from previous LANGUAGE_CODE values.
_SOURCE_PREFIXES = (
    ("Can add ", "add"),
    ("Can change ", "change"),
    ("Can delete ", "delete"),
    ("Can view ", "view"),
    ("可以添加 ", "add"),
    ("可以修改 ", "change"),
    ("可以删除 ", "delete"),
    ("可以查看 ", "view"),
    ("Добавить: ", "add"),
    ("Изменить: ", "change"),
    ("Удалить: ", "delete"),
    ("Просмотр: ", "view"),
)

_PREFIX_BY_LANG = {
    "ru": {
        "add": "Добавить: ",
        "change": "Изменить: ",
        "delete": "Удалить: ",
        "view": "Просмотр: ",
    },
    "zh-hans": {
        "add": "可以添加 ",
        "change": "可以修改 ",
        "delete": "可以删除 ",
        "view": "可以查看 ",
    },
    "en": {
        "add": "Can add ",
        "change": "Can change ",
        "delete": "Can delete ",
        "view": "Can view ",
    },
}


def _normalize_language(language: str | None) -> str:
    lang = (language or translation.get_language() or "zh-hans").replace("_", "-")
    lang = lang.lower()
    if lang.startswith("zh"):
        return "zh-hans"
    if lang.startswith("ru"):
        return "ru"
    if lang.startswith("en"):
        return "en"
    return lang


def localize_permission_name(name: str, language: str | None = None) -> str:
    """Translate a permission display name under the currently active language."""
    lang = _normalize_language(language)
    prefixes = _PREFIX_BY_LANG.get(lang, _PREFIX_BY_LANG["zh-hans"])
    with translation.override(lang):
        translated = _(name)
        if translated != name:
            return translated[:255]
        for src, kind in _SOURCE_PREFIXES:
            if name.startswith(src):
                rest = name[len(src) :]
                return f"{prefixes[kind]}{_(rest)}"[:255]
        return name[:255]


def expected_permission_name(
    codename: str, raw_name, language: str | None = None
) -> str:
    """Build the display name for a (codename, Meta name) pair."""
    name = force_str(raw_name)
    return localize_permission_name(name, language)


def sync_permission_names(language: str | None = None, verbosity: int = 1) -> int:
    """
    Rewrite auth_permission.name for all known model permissions.

    Uses the requested language, or settings.LANGUAGE_CODE (default zh-hans).

    Returns the number of rows updated.
    """
    language = language or getattr(settings, "LANGUAGE_CODE", "zh-hans") or "zh-hans"
    translation.activate(language)
    updated = 0
    seen = set()

    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            opts = model._meta
            ctype = ContentType.objects.get_for_model(model, for_concrete_model=False)
            for codename, raw_name in _get_all_permissions(opts):
                seen.add((ctype.pk, codename))
                new_name = expected_permission_name(codename, raw_name, language)
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
        new_name = localize_permission_name(perm.name, language)
        if new_name != perm.name:
            Permission.objects.filter(pk=perm.pk).update(name=new_name)
            updated += 1

    if verbosity >= 1:
        print(f"sync_permission_names({language}): updated {updated} row(s)")
    return updated
