"""models.py 的补充测试"""

from sql.models import InstanceTag


def test_instance_tag_str():
    i = InstanceTag(tag_name="test")

    assert str(i) == "test"
