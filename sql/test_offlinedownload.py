from unittest.mock import patch, MagicMock, Mock, mock_open
from django.test import TestCase, Client
from django.conf import settings
from django.http import HttpRequest
from datetime import datetime, date
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
        Config.objects.create(item="storage_type", value="local")

    def tearDown(self):
        # 清理测试数据
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()
        Instance.objects.all().delete()
        Config.objects.all().delete()
        AuditEntry.objects.all().delete()

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
        mock_get_engine.return_value = mock_engine

        offline_download = OffLineDownLoad()
        self.workflow.sql_content = "DELETE FROM test_table"
        result = offline_download.pre_count_check(self.workflow)

        # 验证结果
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.warning_count, 0)
        self.assertEqual(result.rows[0].errormessage, "违规语句！")

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
