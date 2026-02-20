# -*- coding: UTF-8 -*-
# i18n configuration override for Archery
# This file overrides settings in the container's default settings.py

import os
from django.utils.translation import gettext_lazy as _

# Get BASE_DIR from the container's structure
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Available languages (English default, Spanish)
LANGUAGES = [
    ("en", _("English")),
    ("es", _("Spanish")),
    ("zh-hans", _("Chinese Simplified")),
]

# Default language
LANGUAGE_CODE = "en"

# Timezone
TIME_ZONE = "UTC"

# Enable i18n
USE_I18N = True
USE_TZ = True

# Locale paths for translation files
LOCALE_PATHS = [
    os.path.join(BASE_DIR, "locale"),
]

# Insert LocaleMiddleware if not present
# Note: This requires the middleware to be added manually or the container to support it
