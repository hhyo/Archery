"""Smoke tests for i18n configuration (zh-hans default, ru)."""
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _


class I18nSettingsTests(SimpleTestCase):
    def test_default_language_is_zh_hans(self):
        self.assertEqual(settings.LANGUAGE_CODE, "zh-hans")

    def test_supported_languages(self):
        codes = {code for code, _name in settings.LANGUAGES}
        self.assertEqual(codes, {"ru", "zh-hans"})

    def test_locale_middleware_enabled(self):
        self.assertIn(
            "django.middleware.locale.LocaleMiddleware", settings.MIDDLEWARE
        )

    def test_set_language_url(self):
        self.assertEqual(reverse("set_language"), "/i18n/setlang/")


class I18nCatalogTests(SimpleTestCase):
    def test_russian_workflow_status(self):
        with translation.override("ru"):
            self.assertEqual(_("workflow_finish"), "Успешно завершено")

    def test_russian_common_ui(self):
        with translation.override("ru"):
            self.assertEqual(_("退出"), "Выход")
            self.assertEqual(_("SQL查询"), "SQL-запросы")
            self.assertEqual(_("语言"), "Язык")

    def test_chinese_workflow_status(self):
        with translation.override("zh-hans"):
            self.assertEqual(_("workflow_finish"), "已正常结束")
