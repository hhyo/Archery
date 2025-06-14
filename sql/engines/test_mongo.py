import pytest
from unittest.mock import patch, MagicMock
from sql.engines.mongo import MongoEngine


# 创建MongoEngine测试实例的fixture
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


# 测试带load参数的命令生成
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


# 测试不带load参数的命令生成
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


# 测试无认证信息时命令生成
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


# 测试无认证信息且带load参数的命令生成
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


# 参数化测试多种Mongo命令的生成
@pytest.mark.parametrize(
    "params,expected_cmd",
    [
        # 基础 find 查询
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.test_collection.find({})",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.test_collection.find({})\nEOF",
        ),
        # find 带条件
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.test_collection.find({'name':'archery'})",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.test_collection.find({'name':'archery'})\nEOF",
        ),
        # aggregate 查询
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.test_collection.aggregate([{'$match':{'age':{'$gt':18}}}])",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.test_collection.aggregate([{'$match':{'age':{'$gt':18}}}])\nEOF",
        ),
        # count 查询
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.test_collection.count({'status':'active'})",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.test_collection.count({'status':'active'})\nEOF",
        ),
        # explain 查询
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.test_collection.find({'score':{'$gte':90}}).explain()",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.test_collection.find({'score':{'$gte':90}}).explain()\nEOF",
        ),
        # find 带 sort/limit/skip
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.test_collection.find({}).sort({'age':-1}).limit(10).skip(5)",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.test_collection.find({}).sort({'age':-1}).limit(10).skip(5)\nEOF",
        ),
        # findOne 查询
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.test_collection.findOne({'_id':ObjectId('507f1f77bcf86cd799439011')})",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.test_collection.findOne({'_id':ObjectId('507f1f77bcf86cd799439011')})\nEOF",
        ),
        # insertOne
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.test_collection.insertOne({'name':'archery','age':20})",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.test_collection.insertOne({'name':'archery','age':20})\nEOF",
        ),
        # updateMany
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.test_collection.updateMany({'status':'active'},{'$set':{'score':100}})",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.test_collection.updateMany({'status':'active'},{'$set':{'score':100}})\nEOF",
        ),
        # deleteMany
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.test_collection.deleteMany({'expired':true})",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.test_collection.deleteMany({'expired':true})\nEOF",
        ),
        # createIndex
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.test_collection.createIndex({'name':1},{'background':true})",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.test_collection.createIndex({'name':1},{'background':true})\nEOF",
        ),
        # dropIndex
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.test_collection.dropIndex('name_1')",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.test_collection.dropIndex('name_1')\nEOF",
        ),
        # createCollection
        (
            dict(
                db_name="test_db",
                auth_db="admin",
                slave_ok="",
                sql="db.createCollection('new_collection')",
                is_load=False,
            ),
            "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
            "db=db.getSiblingDB('test_db');db.createCollection('new_collection')\nEOF",
        ),
    ],
)
def test_build_cmd_various_queries(mongo_engine, params, expected_cmd):
    # 测试多种Mongo命令的生成
    cmd = mongo_engine._build_cmd(**params)
    assert cmd == expected_cmd


# 测试带slave_ok参数的命令生成
def test_build_cmd_with_slave_ok(mongo_engine):
    cmd = mongo_engine._build_cmd(
        db_name="test_db",
        auth_db="admin",
        slave_ok="rs.slaveOk();",
        sql="db.test_collection.find()",
        is_load=False,
    )
    expected_cmd = (
        "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
        "db=db.getSiblingDB('test_db');rs.slaveOk();db.test_collection.find()\nEOF"
    )
    assert cmd == expected_cmd


# 测试db_name为空时命令生成
def test_build_cmd_with_empty_db_name(mongo_engine):
    cmd = mongo_engine._build_cmd(
        db_name="",
        auth_db="admin",
        slave_ok="",
        sql="db.test_collection.find()",
        is_load=False,
    )
    expected_cmd = (
        "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
        "db=db.getSiblingDB('');db.test_collection.find()\nEOF"
    )
    assert cmd == expected_cmd


# 测试user和password为None时命令生成
def test_build_cmd_with_none_user_password(mongo_engine):
    mongo_engine.user = None
    mongo_engine.password = None
    cmd = mongo_engine._build_cmd(
        db_name="test_db",
        auth_db="admin",
        slave_ok="",
        sql="db.test_collection.find()",
        is_load=False,
    )
    expected_cmd = (
        "mongo --quiet  localhost:27017/admin <<\\EOF\n"
        "db=db.getSiblingDB('test_db');db.test_collection.find()\nEOF"
    )
    assert cmd == expected_cmd


# 测试带load和slave_ok参数的命令生成
def test_build_cmd_with_load_and_slave_ok(mongo_engine):
    cmd = mongo_engine._build_cmd(
        db_name="test_db",
        auth_db="admin",
        slave_ok="rs.slaveOk();",
        tempfile_="/tmp/test.js",
        is_load=True,
    )
    expected_cmd = (
        "mongo --quiet -u test_user -p 'test_password' localhost:27017/admin <<\\EOF\n"
        "db=db.getSiblingDB('test_db');rs.slaveOk();load('/tmp/test.js')\nEOF"
    )
    assert cmd == expected_cmd


# 测试无认证信息且带load和slave_ok参数的命令生成
def test_build_cmd_with_load_without_auth_and_slave_ok(mongo_engine):
    mongo_engine.user = None
    mongo_engine.password = None
    cmd = mongo_engine._build_cmd(
        db_name="test_db",
        auth_db="admin",
        slave_ok="rs.slaveOk();",
        tempfile_="/tmp/test.js",
        is_load=True,
    )
    expected_cmd = (
        "mongo --quiet  localhost:27017/admin <<\\EOF\n"
        "db=db.getSiblingDB('test_db');rs.slaveOk();load('/tmp/test.js')\nEOF"
    )
    assert cmd == expected_cmd
