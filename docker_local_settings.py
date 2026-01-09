# -*- coding: UTF-8 -*-
# Local settings override for i18n testing
# This file is loaded by the container's settings.py via: from local_settings import *

import os
from django.utils.translation import gettext_lazy as _

# Get BASE_DIR (this runs inside the container)
BASE_DIR = "/opt/archery"

# i18n: Available languages
LANGUAGES = [
    ("en", _("English")),
    ("es", _("Spanish")),
    ("zh-hans", _("Chinese Simplified")),
]

# Default language: English
LANGUAGE_CODE = "en"

# Timezone
TIME_ZONE = "UTC"
USE_TZ = True

# Enable internationalization
USE_I18N = True

# Path to our locale files
LOCALE_PATHS = [
    os.path.join(BASE_DIR, "locale"),
]

# Add LocaleMiddleware - we need to rebuild the middleware tuple
MIDDLEWARE = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "common.middleware.check_login_middleware.CheckLoginMiddleware",
    "common.middleware.exception_logging_middleware.ExceptionLoggingMiddleware",
)
