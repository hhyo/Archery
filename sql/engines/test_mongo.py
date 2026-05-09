import pytest
import json
import datetime
from unittest.mock import patch, MagicMock
from bson.objectid import ObjectId
from bson.int64 import Int64

from sql.engines.mongo import MongoEngine, JsonDecoder, mongo_error
from sql.engines.models import ResultSet

# ====================== Fixtures ======================


@pytest.fixture
def mongo_engine():
    engine = MongoEngine()
    engine.host = "localhost"
    engine.port = 27017
    engine.user = "test_user"
    engine.password = "test_password"
    engine.instance = MagicMock()
    engine.instance.db_name = "test_db"
    engine.instance.is_ssl = False
    engine.instance.verify_ssl = True
    return engine


def _mock_collection(mongo_engine):
    """创建一个通用的 conn/db/collection mock 并挂载到 engine 上"""
    mock_conn = MagicMock()
    mock_db = MagicMock()
    mock_coll = MagicMock()
    mock_conn.__getitem__ = MagicMock(return_value=mock_db)
    mock_db.__getitem__ = MagicMock(return_value=mock_coll)
    mongo_engine.get_connection = MagicMock(return_value=mock_conn)
    return mock_conn, mock_db, mock_coll


# ====================== mongo_error ======================


class TestMongoError:
    def test_mongo_error_str(self):
        err = mongo_error("failed")
        assert str(err) == "failed"


# ====================== JsonDecoder ======================


class TestJsonDecoder:
    def setup_method(self):
        self.de = JsonDecoder()

    def test_decode_simple_object(self):
        assert self.de.decode("{'a':1}") == {"a": 1}

    def test_decode_nested_object(self):
        assert self.de.decode("{'a':{'b':2}}") == {"a": {"b": 2}}

    def test_decode_array(self):
        assert self.de.decode("[1,2,3]") == [1, 2, 3]

    def test_decode_array_of_objects(self):
        assert self.de.decode("[{'a':1},{'b':2}]") == [{"a": 1}, {"b": 2}]

    def test_decode_bool_and_null(self):
        assert self.de.decode("{'a':true,'b':false,'c':null}") == {
            "a": True,
            "b": False,
            "c": None,
        }

    def test_decode_empty_object(self):
        assert self.de.decode("{}") == {}

    def test_decode_empty_array(self):
        assert self.de.decode("[]") == []

    def test_decode_none_when_empty_string(self):
        assert self.de.decode("") is None

    def test_decode_invalid_start(self):
        with pytest.raises(Exception, match="Json must start with"):
            self.de.decode("123")

    def test_decode_objectid(self):
        val = self.de.decode("{'_id':ObjectId('507f1f77bcf86cd799439011')}")
        assert isinstance(val["_id"], ObjectId)

    def test_decode_number_long(self):
        val = self.de.decode("{'n':NumberLong('123456789')}")
        assert isinstance(val["n"], Int64)
        assert int(val["n"]) == 123456789

    def test_decode_isodate(self):
        val = self.de.decode('{"t":ISODate("2024-01-01")}')
        assert isinstance(val["t"], datetime.datetime)

    def test_decode_float(self):
        val = self.de.decode("{'a':1.5}")
        assert val["a"] == 1.5

    def test_decode_negative_number(self):
        val = self.de.decode("{'a':-10}")
        assert val["a"] == -10


# ====================== __split_args ======================


class TestSplitArgs:
    def test_basic_args(self, mongo_engine):
        result = mongo_engine._MongoEngine__split_args("1, 2, 3")
        assert result == ["1", "2", "3"]

    def test_nested_json(self, mongo_engine):
        args_str = "{'a':1}, {'b': {'c': 2}}, [1, 2, 3]"
        result = mongo_engine._MongoEngine__split_args(args_str)
        assert len(result) == 3
        assert result[0] == "{'a':1}"
        assert result[1] == "{'b': {'c': 2}}"
        assert result[2] == "[1, 2, 3]"

    def test_string_with_comma(self, mongo_engine):
        args_str = "{'name': 'a,b'}, {'age': 20}"
        result = mongo_engine._MongoEngine__split_args(args_str)
        assert len(result) == 2
        assert result[0] == "{'name': 'a,b'}"

    def test_parentheses_nested(self, mongo_engine):
        args_str = "({'a':1}, {'$set':{'b':2}}, {upsert:true})"
        result = mongo_engine._MongoEngine__split_args(args_str[1:-1])
        assert len(result) == 3

    def test_empty_string(self, mongo_engine):
        assert mongo_engine._MongoEngine__split_args("") == []

    def test_single_arg(self, mongo_engine):
        assert mongo_engine._MongoEngine__split_args("abc") == ["abc"]


# ====================== _execute_shell_sql ======================


class TestExecuteShellSql:
    def _mock_collection(self, mongo_engine):
        _, _, mock_coll = _mock_collection(mongo_engine)
        return mock_coll

    def test_insertOne(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.acknowledged = True
        mock_result.inserted_id = "abc123"
        mock_coll.insert_one.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.insertOne({'name':'archery'})", "test_db"
        )
        assert success is True
        assert affected == 1
        result_doc = json.loads(result)
        assert result_doc["insertedId"] == "abc123"

    def test_insertMany(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.acknowledged = True
        mock_result.inserted_ids = ["id1", "id2"]
        mock_coll.insert_many.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.insertMany([{'a':1},{'b':2}])", "test_db"
        )
        assert success is True
        assert affected == 2

    def test_insert_list(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.acknowledged = True
        mock_result.inserted_ids = ["id1"]
        mock_coll.insert_many.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.insert([{'a':1}])", "test_db"
        )
        assert success is True
        assert affected == 1

    def test_insert_single_doc(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.acknowledged = True
        mock_result.inserted_id = "id1"
        mock_coll.insert_one.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.insert({'a':1})", "test_db"
        )
        assert success is True
        assert affected == 1
        mock_coll.insert_one.assert_called_once()

    def test_updateOne(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.acknowledged = True
        mock_result.matched_count = 1
        mock_result.modified_count = 1
        mock_coll.update_one.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.updateOne({'a':1},{'$set':{'b':2}})", "test_db"
        )
        assert success is True
        assert affected == 1
        result_doc = json.loads(result)
        assert result_doc["modifiedCount"] == 1

    def test_updateOne_with_upsert(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_coll.update_one.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.updateOne({'a':1},{'$set':{'b':2}},{'upsert':true})",
            "test_db",
        )
        assert success is True
        _, kwargs = mock_coll.update_one.call_args
        assert kwargs.get("upsert") is True

    def test_updateMany(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.modified_count = 5
        mock_coll.update_many.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.updateMany({'a':1},{'$set':{'b':2}})", "test_db"
        )
        assert success is True
        assert affected == 5

    def test_update_with_multi(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.modified_count = 3
        mock_coll.update_many.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.update({'a':1},{'$set':{'b':2}},{'multi':true})", "test_db"
        )
        assert success is True
        assert affected == 3
        mock_coll.update_many.assert_called_once()

    def test_update_without_multi(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_coll.update_one.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.update({'a':1},{'$set':{'b':2}})", "test_db"
        )
        assert success is True
        assert affected == 1
        mock_coll.update_one.assert_called_once()

    def test_replaceOne(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_coll.replace_one.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.replaceOne({'a':1},{'b':2})", "test_db"
        )
        assert success is True
        assert affected == 1

    def test_deleteOne(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_coll.delete_one.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.deleteOne({'a':1})", "test_db"
        )
        assert success is True
        assert affected == 1

    def test_deleteMany(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.deleted_count = 5
        mock_coll.delete_many.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.deleteMany({'a':1})", "test_db"
        )
        assert success is True
        assert affected == 5

    def test_remove_justOne(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_coll.delete_one.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.remove({'a':1},{'justOne':true})", "test_db"
        )
        assert success is True
        assert affected == 1
        mock_coll.delete_one.assert_called_once()

    def test_remove_many(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.deleted_count = 3
        mock_coll.delete_many.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.remove({'a':1})", "test_db"
        )
        assert success is True
        assert affected == 3
        mock_coll.delete_many.assert_called_once()

    def test_drop(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.drop()", "test_db"
        )
        assert success is True
        assert affected == 0
        mock_coll.drop.assert_called_once()

    def test_createCollection(self, mongo_engine):
        mock_conn = MagicMock()
        mock_db = MagicMock()
        mock_conn.__getitem__ = MagicMock(return_value=mock_db)
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.createCollection('new_coll',{'capped':true})", "test_db"
        )
        assert success is True
        assert affected == 0
        mock_db.create_collection.assert_called_once_with("new_coll", capped=True)

    def test_createIndex(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_coll.create_index.return_value = "name_1"

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.createIndex({'name':1},{'background':true})", "test_db"
        )
        assert success is True
        assert affected == 0
        result_doc = json.loads(result)
        assert result_doc["indexName"] == "name_1"

    def test_ensureIndex(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_coll.create_index.return_value = "age_1"

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.ensureIndex({'age':1})", "test_db"
        )
        assert success is True
        result_doc = json.loads(result)
        assert result_doc["indexName"] == "age_1"

    def test_dropIndex(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.dropIndex('name_1')", "test_db"
        )
        assert success is True
        mock_coll.drop_index.assert_called_once_with("name_1")

    def test_dropIndexes(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.dropIndexes()", "test_db"
        )
        assert success is True
        mock_coll.drop_indexes.assert_called_once()

    def test_renameCollection(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.renameCollection('new_name')", "test_db"
        )
        assert success is True
        mock_coll.rename.assert_called_once_with("new_name")

    def test_bulkWrite(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_result.deleted_count = 1
        mock_result.inserted_count = 1
        mock_result.upserted_count = 0
        mock_result.matched_count = 1
        mock_result.acknowledged = True
        mock_coll.bulk_write.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.bulkWrite([{'insertOne':{'document':{'a':1}}},{'updateOne':{'filter':{'a':1},'update':{'$set':{'b':2}}}}])",
            "test_db",
        )
        assert success is True
        assert affected == 3
        mock_coll.bulk_write.assert_called_once()

    def test_unsupported_statement(self, mongo_engine):
        self._mock_collection(mongo_engine)
        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.unknownMethod()", "test_db"
        )
        assert success is False
        assert "暂不支持的语句" in result

    def test_getCollection_syntax(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_result = MagicMock()
        mock_result.deleted_count = 2
        mock_coll.delete_many.return_value = mock_result

        success, result, affected = mongo_engine._execute_shell_sql(
            'db.getCollection("test").deleteMany({"a":1})', "test_db"
        )
        assert success is True
        assert affected == 2

    def test_exception_handling(self, mongo_engine):
        mock_coll = self._mock_collection(mongo_engine)
        mock_coll.insert_one.side_effect = Exception("insert failed")

        success, result, affected = mongo_engine._execute_shell_sql(
            "db.test.insertOne({'a':1})", "test_db"
        )
        assert success is False
        assert affected == 0


# ====================== get_master ======================


class TestGetMaster:
    def test_get_master_success(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.admin.command.return_value = {"primary": "192.168.1.10:27017"}
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        mongo_engine.get_master()
        assert mongo_engine.host == "192.168.1.10"
        assert mongo_engine.port == 27017

    def test_get_master_undefined(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.admin.command.return_value = {"primary": "undefined"}
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        mongo_engine.get_master()
        assert mongo_engine.host == "localhost"

    def test_get_master_no_primary(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.admin.command.return_value = {}
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        mongo_engine.get_master()
        assert mongo_engine.host == "localhost"

    def test_get_master_exception(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.admin.command.side_effect = Exception("conn failed")
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        mongo_engine.get_master()
        assert mongo_engine.host == "localhost"


# ====================== get_slave ======================


class TestGetSlave:
    def test_get_slave_success(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.admin.command.return_value = {
            "members": [
                {"stateStr": "PRIMARY", "name": "host1:27017"},
                {"stateStr": "SECONDARY", "name": "host2:27018"},
            ]
        }
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.get_slave()
        assert result is True
        assert mongo_engine.host == "host2"
        assert mongo_engine.port == 27018

    def test_get_slave_aliyun(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.admin.command.return_value = {
            "members": [
                {"stateStr": "SECONDARY", "name": "SECONDARY"},
            ]
        }
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.get_slave()
        assert result is False

    def test_get_slave_no_secondary(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.admin.command.return_value = {"members": []}
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.get_slave()
        assert result is False

    def test_get_slave_exception(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.admin.command.side_effect = Exception("conn failed")
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.get_slave()
        assert result is False


# ====================== execute ======================


class TestExecute:
    @patch.object(MongoEngine, "get_master")
    def test_execute_success(self, mock_get_master, mongo_engine):
        with patch.object(mongo_engine, "_execute_shell_sql") as mock_exec:
            mock_exec.return_value = (True, '{"ok":1}', 1)
            result = mongo_engine.execute(
                db_name="test_db", sql="db.test.insertOne({'a':1})"
            )
            assert result.error is None
            assert len(result.rows) == 1
            assert result.rows[0].affected_rows == 1
            assert result.rows[0].stagestatus == "执行结束"

    @patch.object(MongoEngine, "get_master")
    def test_execute_failure(self, mock_get_master, mongo_engine):
        with patch.object(mongo_engine, "_execute_shell_sql") as mock_exec:
            mock_exec.return_value = (False, "some error", 0)
            result = mongo_engine.execute(
                db_name="test_db", sql="db.test.insertOne({'a':1})"
            )
            assert result.error == "some error"
            assert result.rows[0].errlevel == 2

    @patch.object(MongoEngine, "get_master")
    def test_execute_multi_statement(self, mock_get_master, mongo_engine):
        with patch.object(mongo_engine, "_execute_shell_sql") as mock_exec:
            mock_exec.side_effect = [
                (True, '{"ok":1}', 1),
                (True, '{"ok":1}', 5),
            ]
            result = mongo_engine.execute(
                db_name="test_db",
                sql="db.test.insertOne({'a':1});db.test.updateMany({'a':1},{'$set':{'b':2}})",
            )
            assert len(result.rows) == 2
            assert result.rows[0].affected_rows == 1
            assert result.rows[1].affected_rows == 5

    @patch.object(MongoEngine, "get_master")
    def test_execute_empty_sql(self, mock_get_master, mongo_engine):
        result = mongo_engine.execute(db_name="test_db", sql="")
        assert len(result.rows) == 0

    @patch.object(MongoEngine, "get_master")
    def test_execute_workflow(self, mock_get_master, mongo_engine):
        workflow = MagicMock()
        workflow.db_name = "test_db"
        workflow.sqlworkflowcontent.sql_content = "db.test.insertOne({'a':1})"
        with patch.object(mongo_engine, "_execute_shell_sql") as mock_exec:
            mock_exec.return_value = (True, '{"ok":1}', 1)
            result = mongo_engine.execute_workflow(workflow)
            assert len(result.rows) == 1


# ====================== execute_check ======================


class TestExecuteCheck:
    @patch("sql.engines.mongo.SysConfig")
    @patch.object(MongoEngine, "get_all_tables")
    def test_execute_check_insertOne(
        self, mock_get_tables, mock_sys_config, mongo_engine
    ):
        mock_get_tables.return_value = MagicMock(rows=["test"])
        mock_sys_config.return_value.get.return_value = False
        result = mongo_engine.execute_check(
            db_name="test_db", sql="db.test.insertOne({'a':1});"
        )
        assert result.error_count == 0
        assert result.rows[0].stagestatus == "Audit completed"

    @patch("sql.engines.mongo.SysConfig")
    @patch.object(MongoEngine, "get_all_tables")
    def test_execute_check_unsupported(
        self, mock_get_tables, mock_sys_config, mongo_engine
    ):
        mock_get_tables.return_value = MagicMock(rows=["test"])
        mock_sys_config.return_value.get.return_value = False
        result = mongo_engine.execute_check(
            db_name="test_db", sql="db.test.unknownMethod();"
        )
        assert result.error_count == 1
        assert result.rows[0].stagestatus == "驳回不支持语句"

    @patch("sql.engines.mongo.SysConfig")
    @patch.object(MongoEngine, "get_all_tables")
    def test_execute_check_no_semicolon(
        self, mock_get_tables, mock_sys_config, mongo_engine
    ):
        mock_get_tables.return_value = MagicMock(rows=["test"])
        mock_sys_config.return_value.get.return_value = False
        with pytest.raises(Exception, match="请以分号结尾"):
            mongo_engine.execute_check(
                db_name="test_db", sql="db.test.insertOne({'a':1})"
            )

    @patch("sql.engines.mongo.SysConfig")
    @patch.object(MongoEngine, "get_all_tables")
    def test_execute_check_table_not_exists(
        self, mock_get_tables, mock_sys_config, mongo_engine
    ):
        mock_get_tables.return_value = MagicMock(rows=["other"])
        mock_sys_config.return_value.get.return_value = False
        result = mongo_engine.execute_check(db_name="test_db", sql="db.test.drop();")
        assert result.error_count == 1
        assert result.rows[0].stagestatus == "文档不存在"

    @patch("sql.engines.mongo.SysConfig")
    @patch.object(MongoEngine, "get_all_tables")
    def test_execute_check_createCollection_exists(
        self, mock_get_tables, mock_sys_config, mongo_engine
    ):
        mock_get_tables.return_value = MagicMock(rows=["test"])
        mock_sys_config.return_value.get.return_value = False
        result = mongo_engine.execute_check(
            db_name="test_db", sql="db.createCollection('test');"
        )
        assert result.error_count == 1
        assert result.rows[0].stagestatus == "文档已经存在"

    @patch("sql.engines.mongo.SysConfig")
    @patch.object(MongoEngine, "get_all_tables")
    def test_execute_check_createIndex_no_background(
        self, mock_get_tables, mock_sys_config, mongo_engine
    ):
        mock_get_tables.return_value = MagicMock(rows=["test"])
        mock_sys_config.return_value.get.return_value = False
        result = mongo_engine.execute_check(
            db_name="test_db", sql="db.test.createIndex({'name':1});"
        )
        assert result.error_count == 1
        assert result.rows[0].stagestatus == "后台创建索引"

    @patch("sql.engines.mongo.SysConfig")
    @patch.object(MongoEngine, "get_all_tables")
    def test_execute_check_syntax_error(
        self, mock_get_tables, mock_sys_config, mongo_engine
    ):
        mock_get_tables.return_value = MagicMock(rows=["test"])
        mock_sys_config.return_value.get.return_value = False
        result = mongo_engine.execute_check(
            db_name="test_db", sql="SELECT * FROM test;"
        )
        assert result.error_count == 1
        assert result.rows[0].stagestatus == "语法错误"


# ====================== get_connection / close ======================


class TestGetConnection:
    @patch("sql.engines.mongo.pymongo.MongoClient")
    def test_get_connection(self, mock_client, mongo_engine):
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        conn = mongo_engine.get_connection("test_db")
        assert conn is mock_instance
        assert mongo_engine.db_name == "test_db"
        mock_client.assert_called_once()

    @patch("sql.engines.mongo.pymongo.MongoClient")
    def test_get_connection_default_db(self, mock_client, mongo_engine):
        mongo_engine.instance.db_name = ""
        mock_client.return_value = MagicMock()
        mongo_engine.get_connection()
        assert mongo_engine.db_name == "admin"

    @patch("sql.engines.mongo.pymongo.MongoClient")
    def test_get_connection_with_tls(self, mock_client, mongo_engine):
        mongo_engine.instance.is_ssl = True
        mongo_engine.instance.verify_ssl = False
        mock_client.return_value = MagicMock()
        mongo_engine.get_connection("test_db")
        _, kwargs = mock_client.call_args
        assert kwargs.get("tls") is True
        assert kwargs.get("tlsInsecure") is True

    @patch("sql.engines.mongo.pymongo.MongoClient")
    def test_get_connection_without_auth(self, mock_client, mongo_engine):
        mongo_engine.user = ""
        mongo_engine.password = ""
        mock_client.return_value = MagicMock()
        mongo_engine.get_connection("test_db")
        mock_client.assert_called_once()


class TestClose:
    def test_close(self, mongo_engine):
        mock_conn = MagicMock()
        mongo_engine.conn = mock_conn
        mongo_engine.close()
        mock_conn.close.assert_called_once()
        assert mongo_engine.conn is None


# ====================== get_all_databases / tables ======================


class TestGetAllDatabases:
    def test_get_all_databases(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.list_database_names.return_value = ["db1", "db2"]
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.get_all_databases()
        assert isinstance(result, ResultSet)
        assert result.rows == ["db1", "db2"]

    def test_get_all_databases_operation_failure(self, mongo_engine):
        from pymongo.errors import OperationFailure

        mock_conn = MagicMock()
        mock_conn.list_database_names.side_effect = OperationFailure("auth failed")
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)
        mongo_engine.db_name = "test_db"

        result = mongo_engine.get_all_databases()
        assert result.rows == ["test_db"]

    def test_test_connection(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.list_database_names.return_value = ["db1"]
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)
        result = mongo_engine.test_connection()
        assert result.rows == ["db1"]


class TestGetAllTables:
    def test_get_all_tables(self, mongo_engine):
        mock_conn = MagicMock()
        mock_db = MagicMock()
        mock_db.list_collection_names.return_value = ["coll1", "coll2"]
        mock_conn.__getitem__ = MagicMock(return_value=mock_db)
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.get_all_tables("test_db")
        assert result.rows == ["coll1", "coll2"]


class TestGetTableCount:
    def test_get_table_count(self, mongo_engine):
        mock_conn = MagicMock()
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.count_documents.return_value = 100
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        mock_conn.__getitem__ = MagicMock(return_value=mock_db)
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)
        mongo_engine.get_slave = MagicMock(return_value=True)

        count = mongo_engine.get_table_conut("test", "test_db")
        assert count == 100

    def test_get_table_count_exception(self, mongo_engine):
        mongo_engine.get_slave = MagicMock(return_value=True)
        mongo_engine.get_connection = MagicMock(side_effect=Exception("fail"))
        count = mongo_engine.get_table_conut("test", "test_db")
        assert count == 0


class TestGetAllColumnsByTb:
    def test_get_all_columns(self, mongo_engine):
        mock_conn = MagicMock()
        mock_db = MagicMock()
        mock_coll = MagicMock()
        # options 中不带 viewOn
        mock_coll.options.return_value = {}
        # sort().limit() 两次调用，一次 _id 升序、一次 _id 降序
        mock_coll.find.return_value.sort.return_value.limit.side_effect = [
            [{"_id": "1", "name": "a"}],
            [{"_id": "2", "age": 10}],
        ]
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        mock_conn.__getitem__ = MagicMock(return_value=mock_db)
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.get_all_columns_by_tb("test_db", "test")
        assert "_id" in result.rows
        assert "name" in result.rows
        assert "age" in result.rows

    def test_get_all_columns_view(self, mongo_engine):
        mock_conn = MagicMock()
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.options.return_value = {"viewOn": "base_table"}
        mock_coll.find.return_value.limit.return_value = [
            {"_id": "1", "x": 1},
            {"_id": "2", "y": 2},
        ]
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        mock_conn.__getitem__ = MagicMock(return_value=mock_db)
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.get_all_columns_by_tb("test_db", "v")
        assert "x" in result.rows
        assert "y" in result.rows


class TestDescribeTable:
    def test_describe_table(self, mongo_engine):
        mongo_engine.get_all_columns_by_tb = MagicMock(
            return_value=MagicMock(rows=["_id", "name"])
        )
        result = mongo_engine.describe_table("test_db", "test")
        assert result.rows == [[["_id"]], [["name"]]]


# ====================== get_roles ======================


class TestGetRoles:
    def test_get_roles(self, mongo_engine):
        mock_result = MagicMock()
        mock_result.rows = [
            ["admin.custom_role1", "custom_role1"],
            ["admin.custom_role2", "custom_role2"],
        ]
        mongo_engine.query = MagicMock(return_value=mock_result)
        result = mongo_engine.get_roles()
        assert "read" in result.rows
        assert "readWrite" in result.rows
        assert "userAdminAnyDatabase" in result.rows
        assert "custom_role1" in result.rows
        assert "custom_role2" in result.rows


# ====================== dispose_pair / dispose_str ======================


class TestDisposePair:
    def test_dispose_pair_simple(self, mongo_engine):
        _, re_char = mongo_engine.dispose_pair("(abc)", 0, "(", ")")
        assert re_char == "(abc)"

    def test_dispose_pair_nested(self, mongo_engine):
        _, re_char = mongo_engine.dispose_pair("({'a':1})", 0, "(", ")")
        assert re_char == "({'a':1})"

    def test_dispose_pair_with_string_containing_brace(self, mongo_engine):
        _, re_char = mongo_engine.dispose_pair('({"a":"{b"})', 0, "(", ")")
        assert re_char == '({"a":"{b"})'

    def test_dispose_pair_unclosed(self, mongo_engine):
        with pytest.raises(Exception, match="has no closed"):
            mongo_engine.dispose_pair("(abc", 0, "(", ")")

    def test_dispose_str_unclosed(self, mongo_engine):
        with pytest.raises(Exception, match="has no close"):
            MongoEngine.dispose_str('"abc', '"', 0)


# ====================== parse_query_sentence ======================


class TestParseQuerySentence:
    def test_find(self, mongo_engine):
        qd = mongo_engine.parse_query_sentence("db.test.find({'a':1})")
        assert qd["collection"] == "test"
        assert qd["method"] == "find"
        assert qd["condition"] == "{'a':1}"

    def test_find_with_projection(self, mongo_engine):
        qd = mongo_engine.parse_query_sentence("db.test.find({'a':1},{'name':1})")
        assert qd["method"] == "find"
        assert qd["projection"] == "{'name':1}"

    def test_getCollection(self, mongo_engine):
        qd = mongo_engine.parse_query_sentence('db.getCollection("my_coll").find({})')
        assert qd["collection"] == "my_coll"

    def test_count(self, mongo_engine):
        qd = mongo_engine.parse_query_sentence("db.test.count({'a':1})")
        assert qd["method"] == "count"
        assert qd["count"] == "{'a':1}"

    def test_findOne(self, mongo_engine):
        qd = mongo_engine.parse_query_sentence("db.test.findOne({'a':1})")
        assert qd["method"] == "findOne"
        assert qd["findOne_filter"] == "{'a':1}"

    def test_findOne_no_args(self, mongo_engine):
        qd = mongo_engine.parse_query_sentence("db.test.findOne()")
        assert qd["method"] == "findOne"
        assert qd["findOne_filter"] == "{}"

    def test_countDocuments(self, mongo_engine):
        qd = mongo_engine.parse_query_sentence("db.test.countDocuments({'a':1})")
        assert qd["method"] == "countDocuments"
        assert qd["countDocuments_filter"] == "{'a':1}"

    def test_distinct(self, mongo_engine):
        qd = mongo_engine.parse_query_sentence("db.test.distinct('name')")
        assert qd["method"] == "distinct"
        assert "'name'" in qd["distinct_args"]

    def test_stats(self, mongo_engine):
        qd = mongo_engine.parse_query_sentence("db.test.stats()")
        assert qd["method"] == "stats"

    def test_getIndexes(self, mongo_engine):
        qd = mongo_engine.parse_query_sentence("db.test.getIndexes()")
        assert qd["method"] == "index_information"

    def test_aggregate(self, mongo_engine):
        qd = mongo_engine.parse_query_sentence(
            "db.test.aggregate([{'$match':{'a':1}},{'$group':{'_id':'$a'}}])"
        )
        assert qd["method"] == "aggregate"
        assert isinstance(qd["condition"], list)
        assert len(qd["condition"]) == 2


# ====================== filter_sql ======================


class TestFilterSql:
    def test_filter_sql_plain(self, mongo_engine):
        assert mongo_engine.filter_sql("db.test.find({})") == "db.test.find({})"

    def test_filter_sql_explain(self, mongo_engine):
        result = mongo_engine.filter_sql("explain db.test.find({})")
        assert result.endswith(".explain()")

    def test_filter_sql_strip_semicolon(self, mongo_engine):
        assert mongo_engine.filter_sql("db.test.find({});extra") == "db.test.find({})"


# ====================== query_check ======================


class TestQueryCheck:
    def test_query_check_valid(self, mongo_engine):
        mongo_engine.get_all_tables = MagicMock(return_value=MagicMock(rows=["test"]))
        result = mongo_engine.query_check(db_name="test_db", sql="db.test.find({});")
        assert result["bad_query"] is False

    def test_query_check_invalid_syntax(self, mongo_engine):
        result = mongo_engine.query_check(db_name="test_db", sql="SELECT * FROM test")
        assert result["bad_query"] is True

    def test_query_check_table_not_exist(self, mongo_engine):
        mongo_engine.get_all_tables = MagicMock(return_value=MagicMock(rows=["other"]))
        result = mongo_engine.query_check(db_name="test_db", sql="db.test.find({});")
        assert result["bad_query"] is True
        assert "不存在" in result["msg"]

    def test_query_check_explain(self, mongo_engine):
        mongo_engine.get_all_tables = MagicMock(return_value=MagicMock(rows=["test"]))
        result = mongo_engine.query_check(
            db_name="test_db", sql="explain db.test.find({})"
        )
        assert result["filtered_sql"].endswith(".explain()")


# ====================== query ======================


class TestQuery:
    def test_query_count(self, mongo_engine):
        mock_conn = MagicMock()
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.count_documents.return_value = 42
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        mock_conn.__getitem__ = MagicMock(return_value=mock_db)
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.query(
            db_name="test_db", sql="db.test.count({'a':1})", limit_num=10
        )
        assert result.error is None
        assert result.affected_rows == 1
        assert result.column_list == ["count"]

    def test_query_findOne(self, mongo_engine):
        mock_conn = MagicMock()
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.find_one.return_value = {"_id": "1", "name": "archery"}
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        mock_conn.__getitem__ = MagicMock(return_value=mock_db)
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.query(
            db_name="test_db", sql="db.test.findOne({'a':1})", limit_num=10
        )
        assert result.error is None
        assert result.column_list == ["findOne"]

    def test_query_findOne_none(self, mongo_engine):
        mock_conn = MagicMock()
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.find_one.return_value = None
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        mock_conn.__getitem__ = MagicMock(return_value=mock_db)
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.query(
            db_name="test_db", sql="db.test.findOne({'a':1})", limit_num=10
        )
        assert result.error is None
        assert result.affected_rows == 0

    def test_query_countDocuments(self, mongo_engine):
        mock_conn = MagicMock()
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.count_documents.return_value = 5
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        mock_conn.__getitem__ = MagicMock(return_value=mock_db)
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.query(
            db_name="test_db",
            sql="db.test.countDocuments({'a':1})",
            limit_num=10,
        )
        assert result.error is None
        assert result.column_list == ["count"]

    def test_query_distinct(self, mongo_engine):
        mock_conn = MagicMock()
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.distinct.return_value = ["a", "b", "c"]
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        mock_conn.__getitem__ = MagicMock(return_value=mock_db)
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.query(
            db_name="test_db",
            sql="db.test.distinct('name')",
            limit_num=10,
        )
        assert result.error is None
        assert result.column_list == ["distinct"]

    def test_query_error(self, mongo_engine):
        mongo_engine.get_connection = MagicMock(side_effect=Exception("conn failed"))

        result = mongo_engine.query(
            db_name="test_db", sql="db.test.count({'a':1})", limit_num=10
        )
        assert result.error is not None


# ====================== processlist / kill_op ======================


class TestProcesslist:
    def test_processlist_active(self, mongo_engine):
        mock_conn = MagicMock()
        cursor_mock = MagicMock()
        cursor_mock.__enter__ = MagicMock(
            return_value=iter(
                [
                    {
                        "opid": 1,
                        "clientMetadata": {},
                        "client": "1.2.3.4",
                        "effectiveUsers": [{"user": "root"}],
                    }
                ]
            )
        )
        cursor_mock.__exit__ = MagicMock(return_value=False)
        mock_conn.admin.aggregate.return_value = cursor_mock
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.processlist("Active")
        assert len(result.rows) == 1
        assert result.rows[0]["effectiveUsers_user"] == "root"

    def test_processlist_exception(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.admin.aggregate.side_effect = Exception("fail")
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.processlist("Active")
        assert result.error is not None


class TestKillOp:
    def test_get_kill_command(self, mongo_engine):
        mock_conn = MagicMock()
        cursor_mock = MagicMock()
        cursor_mock.__enter__ = MagicMock(
            return_value=iter([{"opid": 1}, {"opid": "str_opid"}])
        )
        cursor_mock.__exit__ = MagicMock(return_value=False)
        mock_conn.admin.aggregate.return_value = cursor_mock
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        cmd = mongo_engine.get_kill_command([1, "str_opid"])
        assert "db.killOp(1);" in cmd
        assert 'db.killOp("str_opid");' in cmd

    def test_kill_op_success(self, mongo_engine):
        mock_conn = MagicMock()
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)
        result = mongo_engine.kill_op([1, 2])
        assert result.error is None
        assert mock_conn.admin.command.call_count == 2

    def test_kill_op_connection_error(self, mongo_engine):
        mongo_engine.get_connection = MagicMock(side_effect=Exception("fail"))
        result = mongo_engine.kill_op([1])
        assert result.error is not None

    def test_kill_op_command_error(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.admin.command.side_effect = Exception("op error")
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)
        result = mongo_engine.kill_op([1])
        assert result.error is not None


# ====================== instance users ======================


class TestInstanceUsers:
    def test_get_all_databases_summary(self, mongo_engine):
        mongo_engine.get_all_databases = MagicMock(
            return_value=MagicMock(error=None, rows=["db1"])
        )
        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.command.return_value = {
            "users": [{"user": "u1", "roles": [{"role": "read", "db": "db1"}]}]
        }
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.get_all_databases_summary()
        assert len(result.rows) == 1
        assert result.rows[0]["db_name"] == "db1"

    def test_get_instance_users_summary(self, mongo_engine):
        mongo_engine.get_all_databases = MagicMock(
            return_value=MagicMock(error=None, rows=["db1"])
        )
        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.command.return_value = {
            "users": [{"user": "u1", "roles": [{"role": "read", "db": "db1"}]}]
        }
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.get_instance_users_summary()
        assert len(result.rows) == 1
        assert result.rows[0]["db_name_user"] == "db1.u1"
        assert result.rows[0]["user"] == "u1"

    def test_create_instance_user(self, mongo_engine):
        mock_conn = MagicMock()
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.create_instance_user(
            db_name="db1", user="u1", password1="pwd", remark="note"
        )
        assert result.error is None
        assert result.rows[0]["user"] == "u1"

    def test_create_instance_user_error(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.command.side_effect = Exception("err")
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.create_instance_user(
            db_name="db1", user="u1", password1="pwd"
        )
        assert result.error is not None

    def test_drop_instance_user(self, mongo_engine):
        mock_conn = MagicMock()
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.drop_instance_user("db1.u1")
        assert result.error is None

    def test_drop_instance_user_error(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.command.side_effect = Exception("err")
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.drop_instance_user("db1.u1")
        assert result.error is not None

    def test_reset_instance_user_pwd(self, mongo_engine):
        mock_conn = MagicMock()
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.reset_instance_user_pwd("db1.u1", "new_pwd")
        assert result.error is None

    def test_reset_instance_user_pwd_error(self, mongo_engine):
        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.command.side_effect = Exception("err")
        mongo_engine.get_connection = MagicMock(return_value=mock_conn)

        result = mongo_engine.reset_instance_user_pwd("db1.u1", "new_pwd")
        assert result.error is not None


# ====================== query_masking ======================


class TestQueryMasking:
    @patch("sql.engines.mongo.data_masking")
    def test_query_masking(self, mock_masking, mongo_engine):
        mock_masking.return_value = "masked"
        result = mongo_engine.query_masking(
            db_name="test_db", sql="db.test.find({})", resultset=MagicMock()
        )
        assert result == "masked"
        mock_masking.assert_called_once()


# ====================== parse_tuple / fill_query_columns ======================


class TestParseTuple:
    def test_fill_query_columns(self):
        cursor = [{"a": 1, "b": 2}, {"c": 3}]
        columns = ["mongodballdata"]
        result = MongoEngine.fill_query_columns(cursor, columns)
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_parse_tuple_with_projection(self, mongo_engine):
        cursor = [{"_id": "1", "name": "archery", "age": 10}]
        rows, columns = mongo_engine.parse_tuple(
            cursor, "test_db", "test", projection={"name": 1}
        )
        assert "mongodballdata" in columns
        assert "name" in columns
        assert len(rows) == 1

    def test_parse_tuple_without_projection(self, mongo_engine):
        mongo_engine.get_all_columns_by_tb = MagicMock(
            return_value=MagicMock(rows=["_id", "name"])
        )
        cursor = [{"_id": "1", "name": "archery"}]
        rows, columns = mongo_engine.parse_tuple(cursor, "test_db", "test")
        assert "mongodballdata" in columns
        assert len(rows) == 1

    def test_parse_tuple_array_value(self, mongo_engine):
        cursor = [{"_id": "1", "arr": [1, 2, 3]}]
        rows, _ = mongo_engine.parse_tuple(
            cursor, "test_db", "test", projection={"arr": 1}
        )
        # 数组被转换为 "(array) N Elements"
        assert any("Elements" in str(item) for row in rows for item in row)

    def test_parse_tuple_missing_field(self, mongo_engine):
        cursor = [{"_id": "1"}]
        rows, _ = mongo_engine.parse_tuple(
            cursor, "test_db", "test", projection={"missing_field": 1}
        )
        # 缺失的字段被填充为 "(N/A)"
        assert any("(N/A)" in str(item) for row in rows for item in row)
