from django.test import SimpleTestCase, override_settings
from django.utils import translation

from sql.permission_i18n import localize_permission_name, _normalize_language


class TestPermissionI18n(SimpleTestCase):
    def test_zh_hans_uses_chinese_prefix(self):
        with translation.override("zh-hans"):
            name = localize_permission_name("Can add user")
        self.assertTrue(name.startswith("可以添加 "))
        self.assertFalse(name.startswith("Добавить"))

    def test_ru_uses_russian_prefix(self):
        with translation.override("ru"):
            name = localize_permission_name("Can add user")
        self.assertTrue(name.startswith("Добавить: "))

    def test_zh_hans_does_not_rewrite_existing_chinese(self):
        with translation.override("zh-hans"):
            name = localize_permission_name("可以添加 工单")
        self.assertTrue(name.startswith("可以添加 "))
        self.assertNotIn("Добавить", name)

    def test_explicit_language_overrides_active(self):
        with translation.override("ru"):
            name = localize_permission_name("Can view ticket", language="zh-hans")
        self.assertTrue(name.startswith("可以查看 "))

    @override_settings(LANGUAGE_CODE="zh-hans")
    def test_normalize_language_code(self):
        self.assertEqual(_normalize_language("zh-hans"), "zh-hans")
        self.assertEqual(_normalize_language("zh_CN"), "zh-hans")
        self.assertEqual(_normalize_language("ru"), "ru")
        self.assertEqual(_normalize_language("en-us"), "en")
