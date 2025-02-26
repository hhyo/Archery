"""models.py 的补充测试"""

from django.conf import settings
from sql.models import InstanceTag


def test_instance_tag_str():
    i = InstanceTag(tag_name="test")

    assert str(i) == "test"


def test_password_mixin_import_error():
    settings.PASSWORD_MIXIN_PATH = "sql.not_found:ErrorMixin"
    from sql.models import PasswordMixin

    assert PasswordMixin.__name__ == "DummyMixin"
