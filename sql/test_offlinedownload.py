from unittest.mock import patch, MagicMock, Mock, mock_open
from django.test import TestCase, Client
from django.conf import settings
from django.http import HttpRequest
from datetime import datetime, date
from io import BytesIO
import tempfile
import os
import shutil
import zipfile
import simplejson as json
import pandas as pd
import csv
import xml.etree.ElementTree as ET

from sql.models import SqlWorkflow, SqlWorkflowContent, Instance, Config, AuditEntry
from sql.offlinedownload import (
    OffLineDownLoad,
    StorageFileResponse,
    get_single_export_statement,
    save_to_format_file,
    save_csv,
    save_json,
    save_xml,
    save_xlsx,
    save_sql,
    offline_file_download,
)
from sql.engines.models import ReviewSet, ReviewResult, ResultSet
from sql.storage import DynamicStorage
from sql.tests import User


class TestOfflineDownload(TestCase):
    """
    测试离线下载功能
    """

    def setUp(self):
        # 创建测试用户
        self.client = Client()
        self.superuser = User.objects.create(username="super", is_superuser=True)
        # 创建测试实例
        self.instance = Instance.objects.create(
            instance_name="test_instance",
            type="master",
            db_type="mysql",
            host=settings.DATABASES["default"]["HOST"],
            port=settings.DATABASES["default"]["PORT"],
            user=settings.DATABASES["default"]["USER"],
            password=settings.DATABASES["default"]["PASSWORD"],
        )
        # 创建测试工单
        self.workflow = SqlWorkflow.objects.create(
            workflow_name="test_workflow",
            group_id=1,
            group_name="test_group",
            engineer_display="test_user",
            audit_auth_groups="test_group",
            status="workflow_finish",
            is_backup=True,
            instance=self.instance,
            db_name="test_db",
            syntax_type=1,
            is_offline_export=1,
            export_format="csv",
        )
        self.sql_content = SqlWorkflowContent.objects.create(
            workflow=self.workflow,
            sql_content="SELECT * FROM test_table",
            execute_result="",
        )
        # 设置系统配置
        Config.objects.create(item="max_export_rows", value="10000")
        Config.objects.create(item="max_execution_time", value="60")
        Config.objects.create(item="storage_type", value="local")

    def tearDown(self):
        # 清理测试数据
        SqlWorkflowContent.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        Instance.objects.all().delete()
        Config.objects.all().delete()
        AuditEntry.objects.all().delete()

    def test_get_single_export_statement_sql_engine_strips_comments(self):
        """
        测试SQL引擎语句解析 - 去除注释并拆分SQL
        """
        sql_list, normalized_sql = get_single_export_statement(
            "-- comment\nSELECT * FROM test_table; SELECT 1", "mysql"
        )

        self.assertEqual(sql_list, ["SELECT * FROM test_table;", "SELECT 1"])
        self.assertNotIn("comment", normalized_sql)

    def test_get_single_export_statement_line_based_engine(self):
        """
        测试按行执行的引擎语句解析
        """
        sql_list, normalized_sql = get_single_export_statement(
            "\nget key1\n\nset key2 value2\n", "redis"
        )

        self.assertEqual(sql_list, ["get key1", "set key2 value2"])
        self.assertEqual(normalized_sql, "get key1\n\nset key2 value2")

    def test_get_single_export_statement_native_engine(self):
        """
        测试原生命令引擎语句解析
        """
        sql_list, normalized_sql = get_single_export_statement("cmd1; cmd2; ", "mongo")

        self.assertEqual(sql_list, ["cmd1", "cmd2"])
        self.assertEqual(normalized_sql, "cmd1; cmd2")

    def test_get_single_export_statement_empty_native_engine(self):
        """
        测试原生命令引擎空语句
        """
        sql_list, normalized_sql = get_single_export_statement(" ; ", "mongo")

        self.assertEqual(sql_list, [])
        self.assertEqual(normalized_sql, "")

    @patch("sql.offlinedownload.get_engine")
    def test_pre_count_check_empty_sql(self, mock_get_engine):
        """
        测试pre_count_check方法 - 空SQL
        """
        offline_download = OffLineDownLoad()
        self.workflow.sql_content = "   "

        result = offline_download.pre_count_check(self.workflow)

        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.rows[0].errormessage, "没有有效的查询语句")
        mock_get_engine.assert_called_once()

    @patch("sql.offlinedownload.get_engine")
    def test_pre_count_check_multiple_sql(self, mock_get_engine):
        """
        测试pre_count_check方法 - 多条SQL
        """
        offline_download = OffLineDownLoad()
        self.workflow.sql_content = "select 1; select 2"

        result = offline_download.pre_count_check(self.workflow)

        self.assertEqual(result.error_count, 1)
        self.assertEqual(
            result.rows[0].errormessage, "检测到多个查询语句，只能提交一个导出查询。"
        )
        mock_get_engine.return_value.query_check.assert_not_called()

    @patch("sql.offlinedownload.get_engine")
    def test_pre_count_check_query_check_exception(self, mock_get_engine):
        """
        测试pre_count_check方法 - 查询语法校验异常
        """
        mock_engine = MagicMock()
        mock_engine.query_check.side_effect = Exception("check failed")
        mock_get_engine.return_value = mock_engine
        self.workflow.sql_content = "SELECT * FROM test_table"

        result = OffLineDownLoad().pre_count_check(self.workflow)

        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.rows[0].errormessage, "check failed")
        mock_engine.query.assert_not_called()

    @patch("sql.offlinedownload.get_engine")
    def test_pre_count_check_query_check_none_and_count_error_fallback(
        self, mock_get_engine
    ):
        """
        测试pre_count_check方法 - query_check为空且COUNT失败后降级limit查询
        """
        count_result = MagicMock()
        count_result.error = "count error"
        fallback_result = MagicMock()
        fallback_result.error = None
        fallback_result.rows = [(1,), (2,), (3,)]
        fallback_result.affected_rows = 0

        mock_engine = MagicMock()
        mock_engine.query_check.return_value = None
        mock_engine.filter_sql.return_value = "SELECT * FROM test_table LIMIT 10001"
        mock_engine.query.side_effect = [count_result, fallback_result]
        mock_get_engine.return_value = mock_engine
        self.workflow.sql_content = "SELECT * FROM test_table"

        result = OffLineDownLoad().pre_count_check(self.workflow)

        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.rows[0].affected_rows, 3)
        self.assertEqual(mock_engine.query.call_count, 2)
        mock_engine.filter_sql.assert_called_once_with(
            sql="SELECT * FROM test_table", limit_num=10001
        )

    @patch("sql.offlinedownload.get_engine")
    def test_pre_count_check_count_query_exception(self, mock_get_engine):
        """
        测试pre_count_check方法 - 行数统计查询异常
        """
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "filtered_sql": "SELECT * FROM test_table",
        }
        mock_engine.query.side_effect = Exception("count failed")
        mock_get_engine.return_value = mock_engine
        self.workflow.sql_content = "SELECT * FROM test_table"

        result = OffLineDownLoad().pre_count_check(self.workflow)

        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.rows[0].errormessage, "count failed")

    @patch("sql.offlinedownload.get_engine")
    def test_pre_count_check_result_set_error_after_fallback(self, mock_get_engine):
        """
        测试pre_count_check方法 - 降级查询返回错误
        """
        count_result = MagicMock()
        count_result.error = "count not supported"
        fallback_result = MagicMock()
        fallback_result.error = "query failed"
        fallback_result.rows = []
        fallback_result.affected_rows = 0

        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "filtered_sql": "SELECT * FROM test_table",
        }
        mock_engine.filter_sql.return_value = "SELECT * FROM test_table LIMIT 10001"
        mock_engine.query.side_effect = [count_result, fallback_result]
        mock_get_engine.return_value = mock_engine
        self.workflow.sql_content = "SELECT * FROM test_table"

        result = OffLineDownLoad().pre_count_check(self.workflow)

        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.rows[0].errormessage, "query failed")

    @patch("sql.offlinedownload.get_engine")
    def test_pre_count_check_pass(self, mock_get_engine):
        """
        测试pre_count_check方法 - 正常通过
        """

        # 模拟数据库查询结果
        mock_engine = MagicMock()
        mock_result_set = MagicMock()
        mock_result_set.rows = [(500,)]
        mock_result_set.error = None
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "filtered_sql": "SELECT * FROM test_table",
        }
        mock_engine.query.return_value = mock_result_set
        mock_get_engine.return_value = mock_engine

        # 执行测试
        offline_download = OffLineDownLoad()
        # 修改workflow的sql_content以匹配测试
        self.workflow.sql_content = "SELECT * FROM test_table"
        result = offline_download.pre_count_check(self.workflow)

        # 验证结果
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.warning_count, 0)
        self.assertEqual(result.rows[0].stagestatus, "行数统计完成")
        self.assertEqual(result.rows[0].affected_rows, 500)
        mock_engine.query.assert_called_once_with(
            db_name="test_db",
            sql="SELECT COUNT(*) FROM (SELECT * FROM test_table) t",
            max_execution_time=60000,
        )

    @patch("sql.offlinedownload.get_engine")
    def test_pre_count_check_over_limit(self, mock_get_engine):
        """
        测试pre_count_check方法 - 超过行数限制
        """

        # 模拟数据库查询结果
        mock_engine = MagicMock()
        mock_result_set = MagicMock()
        mock_result_set.rows = [(15000,)]
        mock_result_set.error = None
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "filtered_sql": "SELECT * FROM test_table",
        }
        mock_engine.query.return_value = mock_result_set
        mock_get_engine.return_value = mock_engine

        # 执行测试
        offline_download = OffLineDownLoad()
        self.workflow.sql_content = "SELECT * FROM test_table"
        result = offline_download.pre_count_check(self.workflow)

        # 验证结果
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.warning_count, 0)
        self.assertIn("超过阈值", result.rows[0].errormessage)

    @patch("sql.offlinedownload.get_engine")
    def test_pre_count_check_invalid_sql(self, mock_get_engine):
        """
        测试pre_count_check方法 - 无效SQL语句
        """

        # 模拟get_engine返回值
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": True,
            "msg": "禁止执行该命令！",
            "filtered_sql": "DELETE FROM test_table",
        }
        mock_get_engine.return_value = mock_engine

        offline_download = OffLineDownLoad()
        self.workflow.sql_content = "DELETE FROM test_table"
        result = offline_download.pre_count_check(self.workflow)

        # 验证结果
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.warning_count, 0)
        self.assertEqual(result.rows[0].errormessage, "禁止执行该命令！")
        mock_engine.query.assert_not_called()

    @patch("sql.offlinedownload.get_engine")
    def test_pre_count_check_non_sql_query_uses_affected_rows(self, mock_get_engine):
        """
        测试pre_count_check方法 - 非SQL引擎使用查询返回行数
        """

        mock_engine = MagicMock()
        mock_result_set = MagicMock()
        mock_result_set.rows = [("key1",), ("key2",)]
        mock_result_set.affected_rows = 2
        mock_result_set.error = None
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "filtered_sql": "scan 0 count 10",
        }
        mock_engine.filter_sql.return_value = "scan 0 count 10"
        mock_engine.query.return_value = mock_result_set
        mock_get_engine.return_value = mock_engine

        offline_download = OffLineDownLoad()
        self.workflow.db_type = "redis"
        self.workflow.sql_content = "scan 0 count 10"
        result = offline_download.pre_count_check(self.workflow)

        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.rows[0].affected_rows, 2)
        mock_engine.query.assert_called_once_with(
            db_name="test_db",
            sql="scan 0 count 10",
            limit_num=10001,
            max_execution_time=60000,
        )

    @patch("sql.offlinedownload.get_engine")
    def test_pre_count_check_mongo_native_query(self, mock_get_engine):
        """
        测试pre_count_check方法 - Mongo原生命令保持原样校验
        """

        mock_engine = MagicMock()
        mock_result_set = MagicMock()
        mock_result_set.rows = ["{}"]
        mock_result_set.affected_rows = 100
        mock_result_set.error = None
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "filtered_sql": "db.follow.find().limit(100)",
        }
        mock_engine.filter_sql.return_value = "db.follow.find().limit(100)"
        mock_engine.query.return_value = mock_result_set
        mock_get_engine.return_value = mock_engine

        offline_download = OffLineDownLoad()
        self.workflow.instance.db_type = "mongo"
        self.workflow.sql_content = "db.follow.find().limit(100)"
        result = offline_download.pre_count_check(self.workflow)

        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.rows[0].affected_rows, 100)
        mock_engine.query_check.assert_called_once_with(
            db_name="test_db", sql="db.follow.find().limit(100)"
        )
        mock_engine.query.assert_called_once_with(
            db_name="test_db",
            sql="db.follow.find().limit(100)",
            limit_num=10001,
            max_execution_time=60000,
        )

    @patch("sql.offlinedownload.get_engine")
    def test_pre_count_check_instance_uses_selected_db_without_overwriting_auth_db(
        self, mock_get_engine
    ):
        """
        测试pre_count_check方法 - Instance输入保留认证库并使用选择的业务库
        """

        mock_engine = MagicMock()
        mock_result_set = MagicMock()
        mock_result_set.rows = ["{}"]
        mock_result_set.affected_rows = 1
        mock_result_set.error = None
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "filtered_sql": "db.follow.find().limit(100)",
        }
        mock_engine.filter_sql.return_value = "db.follow.find().limit(100)"
        mock_engine.query.return_value = mock_result_set
        mock_get_engine.return_value = mock_engine

        self.instance.db_type = "mongo"
        self.instance.db_name = "admin"
        self.instance.selected_db_name = "boomplay_follow"
        self.instance.sql_content = "db.follow.find().limit(100)"
        result = OffLineDownLoad().pre_count_check(self.instance)

        self.assertEqual(result.error_count, 0)
        self.assertEqual(self.instance.db_name, "admin")
        mock_engine.query_check.assert_called_once_with(
            db_name="boomplay_follow", sql="db.follow.find().limit(100)"
        )
        mock_engine.query.assert_called_once_with(
            db_name="boomplay_follow",
            sql="db.follow.find().limit(100)",
            limit_num=10001,
            max_execution_time=60000,
        )

    @patch("sql.offlinedownload.get_engine")
    @patch("sql.offlinedownload.DynamicStorage")
    @patch("sql.offlinedownload.save_to_format_file")
    @patch("builtins.open", new_callable=mock_open)
    def test_execute_offline_download_success(
        self, mock_open_file, mock_save_format, mock_storage, mock_get_engine
    ):
        """
        测试execute_offline_download方法 - 成功执行
        """

        # 模拟依赖
        mock_engine = MagicMock()
        mock_result_set = MagicMock()
        mock_result_set.error = None
        mock_result_set.column_list = ["id", "name"]
        mock_result_set.rows = [(1, "test1"), (2, "test2")]
        mock_result_set.affected_rows = 2
        mock_engine.query.return_value = mock_result_set
        mock_get_engine.return_value = mock_engine

        mock_save_format.return_value = "test_file.zip"

        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance

        # 模拟文件打开
        mock_file = MagicMock()
        mock_open_file.return_value = mock_file

        # 执行测试
        offline_download = OffLineDownLoad()
        result = offline_download.execute_offline_download(self.workflow)

        # 验证结果
        self.assertEqual(result.error, None)
        self.assertEqual(result.rows[0].stagestatus, "执行正常")
        self.assertIn("test_file.zip", result.rows[0].errormessage)

        # 验证workflow已更新
        updated_workflow = SqlWorkflow.objects.get(id=self.workflow.id)
        self.assertEqual(updated_workflow.file_name, "test_file.zip")

    @patch("sql.offlinedownload.get_engine")
    @patch("sql.offlinedownload.DynamicStorage")
    def test_execute_offline_download_error(self, mock_storage, mock_get_engine):
        """
        测试execute_offline_download方法 - 执行错误
        """

        # 模拟数据库查询错误
        mock_engine = MagicMock()
        mock_result_set = MagicMock()
        mock_result_set.error = "Database error"
        mock_engine.query.return_value = mock_result_set
        mock_get_engine.return_value = mock_engine

        # 模拟DynamicStorage
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance

        # 执行测试
        offline_download = OffLineDownLoad()
        result = offline_download.execute_offline_download(self.workflow)

        # 验证结果
        self.assertIsNotNone(result.error)
        self.assertEqual(result.rows[0].stagestatus, "异常终止")
        self.assertEqual(result.rows[0].errormessage, "Database error")

    def test_save_csv(self):
        """
        测试save_csv方法
        """

        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()

        # 测试数据
        result = [(1, "test1"), (2, None)]
        columns = ["id", "name"]

        # 执行测试
        save_csv(temp_file.name, result, columns)

        # 验证结果
        with open(temp_file.name, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
            self.assertEqual(rows[0], columns)
            self.assertEqual(rows[1], ["1", "test1"])
            self.assertEqual(rows[2], ["2", "null"])

        # 清理
        os.unlink(temp_file.name)

    def test_save_csv_special_chars(self):
        """
        测试save_csv方法处理特殊字符
        """

        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()

        # 测试数据包含特殊字符
        result = [
            (1, "Normal, value"),
            (2, 'Value with "quotes"'),
            (3, "Line\nbreak"),
            (4, 'Comma, and quote"'),
        ]
        columns = ["id", "text"]

        # 执行测试
        save_csv(temp_file.name, result, columns)

        # 验证结果
        with open(temp_file.name, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn('"Normal, value"', content)
            self.assertIn('"Value with ""quotes"""', content)  # CSV标准转义
            self.assertIn('"Line\nbreak"', content)
            self.assertIn('"Comma, and quote"""', content)

        # 清理
        os.unlink(temp_file.name)

    def test_save_json(self):
        """
        测试save_json方法
        """

        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()

        # 测试数据
        result = [(1, "test1"), (2, "2023-01-01T00:00:00")]
        columns = ["id", "name"]

        # 执行测试
        save_json(temp_file.name, result, columns)

        # 验证结果
        with open(temp_file.name, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["id"], 1)
            self.assertEqual(data[0]["name"], "test1")
            self.assertEqual(data[1]["id"], 2)
            self.assertEqual(data[1]["name"], "2023-01-01T00:00:00")

        # 清理
        os.unlink(temp_file.name)

    def test_save_xml(self):
        """
        测试save_xml方法
        """

        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()

        # 测试数据
        result = [(1, "test1"), (2, datetime(2023, 1, 1))]
        columns = ["id", "name"]

        # 执行测试
        save_xml(temp_file.name, result, columns)

        # 验证结果
        tree = ET.parse(temp_file.name)
        root = tree.getroot()

        # 验证字段
        fields = root.find("fields")
        self.assertEqual(len(fields), 2)
        self.assertEqual(fields[0].text, "id")
        self.assertEqual(fields[1].text, "name")

        # 验证数据
        data = root.find("data")
        self.assertEqual(len(data), 2)
        row1 = data[0]
        self.assertEqual(row1.get("id"), "1")
        self.assertEqual(row1.find("column-1").text, "1")
        self.assertEqual(row1.find("column-2").text, "test1")

        row2 = data[1]
        self.assertEqual(row2.get("id"), "2")
        self.assertEqual(row2.find("column-1").text, "2")
        self.assertEqual(row2.find("column-2").text, "2023-01-01T00:00:00")

        # 清理
        os.unlink(temp_file.name)

    def test_save_xml_null_and_date_values(self):
        """
        测试save_xml方法处理NULL和date类型
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()

        result = [(None, date(2023, 1, 2))]
        columns = ["id", "created_at"]

        save_xml(temp_file.name, result, columns)

        tree = ET.parse(temp_file.name)
        row = tree.getroot().find("data")[0]
        self.assertEqual(row.find("column-1").text, "(null)")
        self.assertEqual(row.find("column-2").text, "2023-01-02")

        os.unlink(temp_file.name)

    def test_save_xlsx(self):
        """
        测试save_xlsx方法
        """

        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        temp_file.close()

        # 测试数据
        result = [(1, "test1"), (2, "test2")]
        columns = ["id", "name"]

        # 执行测试
        save_xlsx(temp_file.name, result, columns)

        # 验证结果
        df = pd.read_excel(temp_file.name)
        self.assertEqual(len(df), 2)
        self.assertEqual(list(df.columns), columns)
        self.assertEqual(df.iloc[0]["id"], 1)
        self.assertEqual(df.iloc[0]["name"], "test1")
        self.assertEqual(df.iloc[1]["id"], 2)
        self.assertEqual(df.iloc[1]["name"], "test2")

        # 清理
        os.unlink(temp_file.name)

    def test_save_xlsx_null_like_values(self):
        """
        测试save_xlsx方法处理None和NULL字符串
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        temp_file.close()

        result = [(1, None), (2, "NULL"), (3, "value")]
        columns = ["id", "name"]

        save_xlsx(temp_file.name, result, columns)

        df = pd.read_excel(temp_file.name)
        self.assertTrue(pd.isna(df.iloc[0]["name"]))
        self.assertTrue(pd.isna(df.iloc[1]["name"]))
        self.assertEqual(df.iloc[2]["name"], "value")

        os.unlink(temp_file.name)

    @patch("sql.offlinedownload.pd.DataFrame")
    def test_save_xlsx_large_file(self, mock_dataframe):
        """
        测试save_xlsx方法处理超过Excel行数限制的情况
        """

        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        temp_file.close()

        # 模拟pd.DataFrame.to_excel抛出异常
        mock_dataframe.return_value.to_excel.side_effect = ValueError(
            "Excel max rows exceeded"
        )

        # 测试数据（不需要实际生成大量数据）
        result = [(1, "test1")]
        columns = ["id", "name"]

        # 执行测试并验证异常
        with self.assertRaises(ValueError) as context:
            save_xlsx(temp_file.name, result, columns)
        self.assertIn("Excel最大支持行数为1048576,已超出!", str(context.exception))

        # 清理
        os.unlink(temp_file.name)

    def test_save_sql(self):
        """
        测试save_sql方法
        """

        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".sql")
        temp_file.close()

        # 测试数据
        result = [(1, "test1"), (2, datetime(2023, 1, 1))]
        columns = ["id", "name"]

        # 执行测试
        save_sql(temp_file.name, result, columns)

        # 验证结果
        with open(temp_file.name, "r") as f:
            content = f.read()
            self.assertIn(
                "INSERT INTO your_table_name (id, name) VALUES (1, 'test1');", content
            )
            self.assertIn(
                "INSERT INTO your_table_name (id, name) VALUES (2, '2023-01-01 00:00:00');",
                content,
            )

        # 清理
        os.unlink(temp_file.name)

    def test_save_sql_special_values(self):
        """
        测试save_sql方法处理特殊值
        """

        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".sql")
        temp_file.close()

        # 测试数据
        result = [(1, None), (2, ""), (3, "O'Reilly"), (4, "Special;value")]
        columns = ["id", "name"]

        # 执行测试
        save_sql(temp_file.name, result, columns)

        # 验证结果
        with open(temp_file.name, "r") as f:
            content = f.read()
            self.assertIn("(1, NULL);", content)
            self.assertIn("(2, '');", content)
            self.assertIn("(3, 'O''Reilly');", content)  # 单引号转义
            self.assertIn("(4, 'Special;value');", content)

        # 清理
        os.unlink(temp_file.name)

    def test_save_sql_without_columns(self):
        """
        测试save_sql方法处理无列名场景
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".sql")
        temp_file.close()

        save_sql(temp_file.name, [(1, "test")], [])

        with open(temp_file.name, "r") as f:
            content = f.read()
            self.assertEqual(content, "(1, 'test');\n")

        os.unlink(temp_file.name)

    def test_save_to_format_file(self):
        """
        测试save_to_format_file方法
        """

        # 创建临时目录
        temp_dir = tempfile.mkdtemp()

        # 测试数据
        result = [(1, "test1"), (2, "test2")]
        columns = ["id", "name"]

        # 测试CSV格式
        csv_file_name = save_to_format_file(
            "csv", result, self.workflow, columns, temp_dir
        )
        self.assertTrue(csv_file_name.endswith(".zip"))
        # 验证ZIP文件包含CSV
        zip_file_path = os.path.join(temp_dir, csv_file_name)
        with zipfile.ZipFile(zip_file_path, "r") as zipf:
            file_list = zipf.namelist()
            self.assertEqual(len(file_list), 1)
            self.assertTrue(file_list[0].endswith(".csv"))

        # 清理
        shutil.rmtree(temp_dir)

    def test_save_to_format_file_supported_formats(self):
        """
        测试save_to_format_file方法 - 支持的所有格式分派
        """
        temp_dir = tempfile.mkdtemp()
        result = [(1, "test1"), (2, "test2")]
        columns = ["id", "name"]

        try:
            for format_type in ["json", "xml", "xlsx", "sql"]:
                zip_file_name = save_to_format_file(
                    format_type, result, self.workflow, columns, temp_dir
                )
                self.assertTrue(zip_file_name.endswith(".zip"))
                with zipfile.ZipFile(
                    os.path.join(temp_dir, zip_file_name), "r"
                ) as zipf:
                    file_list = zipf.namelist()
                    self.assertEqual(len(file_list), 1)
                    self.assertTrue(file_list[0].endswith(f".{format_type}"))
        finally:
            shutil.rmtree(temp_dir)

    def test_save_to_format_file_unsupported(self):
        """
        测试save_to_format_file方法 - 不支持的格式
        """
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()

        # 测试数据
        result = [(1, "test1"), (2, "test2")]
        columns = ["id", "name"]

        # 测试不支持的格式
        with self.assertRaises(ValueError) as context:
            save_to_format_file(
                "invalid_format", result, self.workflow, columns, temp_dir
            )

        self.assertIn("Unsupported format type: invalid_format", str(context.exception))

        # 清理
        shutil.rmtree(temp_dir)

    @patch("sql.offlinedownload.get_engine")
    def test_execute_offline_download_empty_result(self, mock_get_engine):
        """
        测试execute_offline_download方法处理空结果集
        """

        # 模拟依赖
        mock_engine = MagicMock()
        mock_result_set = MagicMock()
        mock_result_set.error = None
        mock_result_set.column_list = ["id", "name"]
        mock_result_set.rows = []
        mock_result_set.affected_rows = 0
        mock_engine.query.return_value = mock_result_set
        mock_get_engine.return_value = mock_engine

        # 执行测试
        offline_download = OffLineDownLoad()
        result = offline_download.execute_offline_download(self.workflow)

        # 验证结果
        self.assertEqual(result.error, None)
        self.assertEqual(result.rows[0].stagestatus, "执行正常")
        self.assertIn("保存文件", result.rows[0].errormessage)

    @patch("sql.offlinedownload.DynamicStorage")
    def test_offline_file_download_error(self, mock_storage):
        """
        测试文件下载时的错误处理
        """

        # 清除已有的审计日志
        AuditEntry.objects.all().delete()

        # 配置mock
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.exists.return_value = False  # 文件不存在

        # 创建请求对象
        request = HttpRequest()
        request.GET = {"file_name": "missing.zip", "workflow_id": "123"}
        request.method = "GET"
        request.user = self.superuser

        # 执行测试
        response = offline_file_download(request)

        # 验证响应
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.content)["error"], "文件不存在")

        # 验证审计日志
        audit_entry = AuditEntry.objects.last()
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.action, "离线下载")
        self.assertIn(
            "工单id：123，文件：missing.zip，error:文件不存在", audit_entry.extra_info
        )
        self.assertEqual(audit_entry.user_id, self.superuser.id)

    @patch("django.http.response.signals.request_finished.send")
    def test_storage_file_response_close_closes_storage(self, mock_request_finished):
        """
        测试StorageFileResponse关闭时同步关闭storage
        """
        storage = MagicMock()
        response = StorageFileResponse(BytesIO(b"data"), storage=storage)

        response.close()

        storage.close.assert_called_once()
        mock_request_finished.assert_called_once()

    @patch("sql.offlinedownload.DynamicStorage")
    def test_offline_file_download_local_success(self, mock_storage):
        """
        测试本地文件下载成功
        """
        AuditEntry.objects.all().delete()
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.exists.return_value = True
        mock_storage_instance.open.return_value = BytesIO(b"zip-data")
        mock_storage_instance.size.return_value = 8

        request = HttpRequest()
        request.GET = {"file_name": "export.zip", "workflow_id": "123"}
        request.method = "GET"
        request.user = self.superuser

        response = offline_file_download(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"], 'attachment; filename="export.zip"'
        )
        self.assertEqual(response["Content-Length"], "8")
        self.assertEqual(response["Content-Encoding"], "identity")
        mock_storage_instance.open.assert_called_once_with("export.zip", "rb")
        self.assertEqual(AuditEntry.objects.count(), 1)

    @patch("sql.offlinedownload.SysConfig")
    @patch("sql.offlinedownload.DynamicStorage")
    def test_offline_file_download_cloud_success(self, mock_storage, mock_sys_config):
        """
        测试云对象存储下载成功返回重定向信息
        """
        AuditEntry.objects.all().delete()
        mock_sys_config.return_value.get.return_value = "s3c"
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.exists.return_value = True
        mock_storage_instance.url.return_value = "https://example.com/export.zip"

        request = HttpRequest()
        request.GET = {"file_name": "export.zip", "workflow_id": "123"}
        request.method = "GET"
        request.user = self.superuser

        response = offline_file_download(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content),
            {"type": "redirect", "url": "https://example.com/export.zip"},
        )
        mock_storage_instance.url.assert_called_once_with("export.zip")
        self.assertEqual(AuditEntry.objects.count(), 1)

    @patch("sql.offlinedownload.DynamicStorage")
    def test_offline_file_download_local_open_exception(self, mock_storage):
        """
        测试本地文件打开异常
        """
        AuditEntry.objects.all().delete()
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.exists.return_value = True
        mock_storage_instance.open.side_effect = Exception("open failed")

        request = HttpRequest()
        request.GET = {"file_name": "export.zip", "workflow_id": "123"}
        request.method = "GET"
        request.user = self.superuser

        response = offline_file_download(request)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            json.loads(response.content)["error"], "文件下载失败：请联系管理员。"
        )
        self.assertIn("open failed", AuditEntry.objects.last().extra_info)

    @patch("sql.offlinedownload.SysConfig")
    @patch("sql.offlinedownload.DynamicStorage")
    def test_offline_file_download_cloud_url_exception(
        self, mock_storage, mock_sys_config
    ):
        """
        测试云对象存储生成URL异常
        """
        AuditEntry.objects.all().delete()
        mock_sys_config.return_value.get.return_value = "azure"
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.exists.return_value = True
        mock_storage_instance.url.side_effect = Exception("url failed")

        request = HttpRequest()
        request.GET = {"file_name": "export.zip", "workflow_id": "123"}
        request.method = "GET"
        request.user = self.superuser

        response = offline_file_download(request)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            json.loads(response.content)["error"], "文件下载失败：请联系管理员。"
        )
        self.assertIn("url failed", AuditEntry.objects.last().extra_info)

    @patch("sql.offlinedownload.DynamicStorage")
    def test_offline_file_download_outer_exception(self, mock_storage):
        """
        测试文件下载外层异常处理
        """
        AuditEntry.objects.all().delete()
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.exists.side_effect = Exception("exists failed")

        request = HttpRequest()
        request.GET = {"file_name": "export.zip", "workflow_id": "123"}
        request.method = "GET"
        request.user = self.superuser

        response = offline_file_download(request)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            json.loads(response.content)["error"], "内部错误，请联系管理员。"
        )
        self.assertIn("exists failed", AuditEntry.objects.last().extra_info)

    @patch("sql.offlinedownload.DynamicStorage")
    def test_offline_file_download_head_skips_audit(self, mock_storage):
        """
        测试HEAD请求不记录审计日志
        """
        AuditEntry.objects.all().delete()
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.exists.return_value = False

        request = HttpRequest()
        request.GET = {"file_name": "missing.zip", "workflow_id": "123"}
        request.method = "HEAD"
        request.user = self.superuser

        response = offline_file_download(request)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(AuditEntry.objects.count(), 0)
