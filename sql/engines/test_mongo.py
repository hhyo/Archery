import pytest
from unittest.mock import patch, MagicMock
from sql.engines.mongo import MongoEngine


@pytest.fixture
def mongo_engine():
    engine = MongoEngine()
    engine.host = "localhost"
    engine.port = 27017
    engine.user = "test_user"
    engine.password = "test_password"
    engine.instance = MagicMock()
    engine.instance.db_name = "test_db"
    return engine


def test_build_cmd_with_load(mongo_engine):
    # Call the method with is_load=True
    cmd = mongo_engine._build_cmd(
        db_name="test_db",
        auth_db="admin",
        slave_ok="rs.slaveOk();",
        tempfile_="/tmp/test.js",
        is_load=True,
    )

    # Expected command template
    expected_cmd = (
        "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
        "db=db.getSiblingDB('test_db');rs.slaveOk();load('/tmp/test.js')\nEOF"
    )

    # Assertions
    assert cmd == expected_cmd


def test_build_cmd_without_load(mongo_engine):
    # Call the method with is_load=False
    cmd = mongo_engine._build_cmd(
        db_name="test_db",
        auth_db="admin",
        slave_ok="rs.slaveOk();",
        sql="db.test_collection.find()",
        is_load=False,
    )

    # Expected command template
    expected_cmd = (
        "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
        "db=db.getSiblingDB('test_db');rs.slaveOk();db.test_collection.find()\nEOF"
    )

    # Assertions
    assert cmd == expected_cmd


def test_build_cmd_without_auth(mongo_engine):
    # Set user and password to None
    mongo_engine.user = None
    mongo_engine.password = None

    # Call the method with is_load=False
    cmd = mongo_engine._build_cmd(
        db_name="test_db",
        auth_db="admin",
        slave_ok="rs.slaveOk();",
        sql="db.test_collection.find()",
        is_load=False,
    )

    # Expected command template
    expected_cmd = (
        "mongo --quiet  localhost:27017/admin <<\\EOF\n"
        "db=db.getSiblingDB('test_db');rs.slaveOk();db.test_collection.find()\nEOF"
    )

    # Assertions
    assert cmd == expected_cmd


def test_build_cmd_with_load_without_auth(mongo_engine):
    # Set user and password to None
    mongo_engine.user = None
    mongo_engine.password = None

    # Call the method with is_load=True
    cmd = mongo_engine._build_cmd(
        db_name="test_db",
        auth_db="admin",
        slave_ok="rs.slaveOk();",
        tempfile_="/tmp/test.js",
        is_load=True,
    )

    # Expected command template
    expected_cmd = (
        "mongo --quiet  localhost:27017/admin <<\\EOF\n"
        "db=db.getSiblingDB('test_db');rs.slaveOk();load('/tmp/test.js')\nEOF"
    )

    # Assertions
    assert cmd == expected_cmd
