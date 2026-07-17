# -*- coding: UTF-8 -*-
import pymysql

pymysql.install_as_MySQLdb()

import pytest

from common.config import SysConfig
from sql.models import Instance


@pytest.fixture
def normal_user(django_user_model):
    user = django_user_model.objects.create(
        username="test_user", display="中文显示", is_active=True
    )
    yield user
    user.delete()


@pytest.fixture
def db_instance(db):
    ins = Instance.objects.create(
        instance_name="some_ins",
        type="slave",
        db_type="mysql",
        host="some_host",
        port=3306,
        user="ins_user",
        password="some_str",
    )
    yield ins
    ins.delete()


@pytest.fixture
def setup_sys_config(db):
    sys_config = SysConfig()
    yield sys_config
    sys_config.purge()
