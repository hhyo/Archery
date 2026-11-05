"""Regression checks for the Django/Python runtime upgrade."""

from copy import copy

from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.files.storage import FileSystemStorage, storages
from django.template import Context, Template

from common.storage import ForgivingManifestStaticFilesStorage


def test_template_context_can_be_copied_and_rendered():
    # Older Django crashes here on Python 3.14, including during admin rendering.
    original = Context({"value": "original"})
    cloned = copy(original)
    template = Template("{{ value }}")

    with cloned.push(value="copied"):
        assert template.render(cloned) == "copied"
        assert template.render(original) == "original"


def test_storage_backends_preserve_manifest_and_upload_behavior():
    # STATICFILES_STORAGE is ignored by Django 5.2; STORAGES must retain our backend.
    assert isinstance(staticfiles_storage, ForgivingManifestStaticFilesStorage)
    assert staticfiles_storage.manifest_strict is False
    assert type(storages["default"]) is FileSystemStorage
