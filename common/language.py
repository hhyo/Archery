"""Persist a supported interface language using Django's language cookie."""

from django.conf import settings
from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.views.i18n import set_language as django_set_language


@require_POST
def set_language(request):
    if request.POST.get("language") not in dict(settings.LANGUAGES):
        return HttpResponseBadRequest("Unsupported language")
    return django_set_language(request)
