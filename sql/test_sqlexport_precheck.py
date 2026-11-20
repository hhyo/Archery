"""数据导出预检接口（/sqlexport/pre_check/）返回结构测试。

前端 sqlexportsubmit.html 的校验回调读取 data.data.affected_rows 判断
“行数统计”是否完成；接口此前只在 data 中返回 error_count/warning_count/rows，
导致校验通过后前端拿到 NaN、页面停留在“行数统计中”且提交按钮被禁用。
"""

from unittest.mock import patch

from django.test import TestCase

from sql.engines.models import ReviewResult, ReviewSet
from sql.models import Instance, InstanceTag, Users


def _build_check_result(affected_rows, errlevel, errormessage):
    """构造与 pre_count_check 返回形态一致的 ReviewSet。"""
    check_result = ReviewSet(full_sql="select * from t")
    check_result.syntax_type = 3
    row = ReviewResult(
        stage="行数统计完成" if errlevel == 0 else "自动审核失败",
        errlevel=errlevel,
        stagestatus="检查未通过！" if errlevel else "行数统计完成",
        errormessage=errormessage,
        affected_rows=affected_rows,
        sql="select * from t",
    )
    check_result.rows = [row]
    if errlevel == 2:
        check_result.error_count = 1
    return check_result


class ExportPreCheckTests(TestCase):
    """sqlexport_pre_check 视图返回结构测试。"""

    def setUp(self):
        self.user = Users.objects.create(username="precheck_admin", is_superuser=True)
        self.client.force_login(self.user)
        tag = InstanceTag.objects.create(
            tag_code="can_read", tag_name="可查询", active=True
        )
        self.instance = Instance.objects.create(
            instance_name="precheck_mysql",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="u",
            password="p",
        )
        self.instance.instance_tag.add(tag)

    def _post(self):
        return self.client.post(
            "/sqlexport/pre_check/",
            {
                "instance_name": "precheck_mysql",
                "db_name": "test_db",
                "sql_content": "select * from t",
            },
        )

    @patch("sql.views.OffLineDownLoad")
    def test_affected_rows_returned_flat_for_frontend(self, mock_download):
        """校验通过时 data.affected_rows 应为统计值，前端才能展示成功并放行提交。"""
        mock_download.return_value.pre_count_check.return_value = _build_check_result(
            123, 0, "None"
        )
        data = self._post().json()
        self.assertEqual(data["status"], 0)
        self.assertEqual(data["data"]["affected_rows"], 123)

    @patch("sql.views.OffLineDownLoad")
    def test_over_threshold_returns_error_status_with_rows(self, mock_download):
        """超过导出阈值时仍应返回状态错误，并带上行数供前端提示。"""
        mock_download.return_value.pre_count_check.return_value = _build_check_result(
            58321, 2, "导出数据行数(58321)超过阈值(10000)。"
        )
        data = self._post().json()
        self.assertEqual(data["status"], 1)
        self.assertIn("超过阈值", data["msg"])
        self.assertEqual(data["data"]["affected_rows"], 58321)

    @patch("sql.views.OffLineDownLoad")
    def test_empty_rows_returns_zero_affected_rows(self, mock_download):
        """无结果行时 affected_rows 应为 0，而不是缺失字段。"""
        check_result = ReviewSet(full_sql="select * from t")
        check_result.rows = []
        mock_download.return_value.pre_count_check.return_value = check_result
        data = self._post().json()
        self.assertEqual(data["status"], 0)
        self.assertEqual(data["data"]["affected_rows"], 0)
