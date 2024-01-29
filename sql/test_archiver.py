import json
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import TestCase, Client
from pytest_django.asserts import assertTemplateUsed

from common.config import SysConfig
from common.utils.const import WorkflowStatus, WorkflowType
from sql.utils.workflow_audit import AuditSetting, AuditV2
from sql.archiver import add_archive_task, archive
from sql.models import (
    Instance,
    ResourceGroup,
    ArchiveConfig,
    WorkflowAudit,
    WorkflowAuditSetting,
)
from sql.tests import User


class TestArchiver(TestCase):
    """
    测试Archive
    """

    def setUp(self):
        self.superuser = User.objects.create(username="super", is_superuser=True)
        self.u1 = User.objects.create(username="u1", is_superuser=False)
        self.u2 = User.objects.create(username="u2", is_superuser=False)
        menu_archive = Permission.objects.get(codename="menu_archive")
        archive_review = Permission.objects.get(codename="archive_review")
        self.u1.user_permissions.add(menu_archive)
        self.u2.user_permissions.add(menu_archive)
        self.u2.user_permissions.add(archive_review)
        # 使用 travis.ci 时实例和测试service保持一致
        self.ins = Instance.objects.create(
            instance_name="test_instance",
            type="master",
            db_type="mysql",
            host=settings.DATABASES["default"]["HOST"],
            port=settings.DATABASES["default"]["PORT"],
            user=settings.DATABASES["default"]["USER"],
            password=settings.DATABASES["default"]["PASSWORD"],
        )
        self.res_group = ResourceGroup.objects.create(
            group_id=1, group_name="group_name"
        )
        self.archive_apply = ArchiveConfig.objects.create(
            title="title",
            resource_group=self.res_group,
            audit_auth_groups="some_audit_group",
            src_instance=self.ins,
            src_db_name="src_db_name",
            src_table_name="src_table_name",
            dest_instance=self.ins,
            dest_db_name="src_db_name",
            dest_table_name="src_table_name",
            condition="1=1",
            mode="file",
            no_delete=True,
            sleep=1,
            status=WorkflowStatus.WAITING,
            state=False,
            user_name="some_user",
            user_display="display",
        )
        self.audit_flow = WorkflowAudit.objects.create(
            group_id=1,
            group_name="g1",
            workflow_id=self.archive_apply.id,
            workflow_type=WorkflowType.ARCHIVE,
            workflow_title="123",
            audit_auth_groups="123",
            current_audit="",
            next_audit="",
            current_status=WorkflowStatus.WAITING,
            create_user="",
            create_user_display="",
        )
        self.sys_config = SysConfig()
        self.client = Client()

    def tearDown(self):
        User.objects.all().delete()
        ResourceGroup.objects.all().delete()
        ArchiveConfig.objects.all().delete()
        WorkflowAuditSetting.objects.all().delete()
        self.ins.delete()
        self.sys_config.purge()

    def test_archive_list_super(self):
        """
        测试管理员获取归档申请列表
        :return:
        """
        data = {"filter_instance_id": self.ins.id, "state": "false", "search": "text"}
        self.client.force_login(self.superuser)
        r = self.client.get(path="/archive/list/", data=data)
        self.assertDictEqual(json.loads(r.content), {"total": 0, "rows": []})

    def test_archive_list_own(self):
        """
        测试非管理员和审核人获取归档申请列表
        :return:
        """
        data = {"filter_instance_id": self.ins.id, "state": "false", "search": "text"}
        self.client.force_login(self.u1)
        r = self.client.get(path="/archive/list/", data=data)
        self.assertDictEqual(json.loads(r.content), {"total": 0, "rows": []})

    def test_archive_list_review(self):
        """
        测试审核人获取归档申请列表
        :return:
        """
        data = {"filter_instance_id": self.ins.id, "state": "false", "search": "text"}
        self.client.force_login(self.u2)
        r = self.client.get(path="/archive/list/", data=data)
        self.assertDictEqual(json.loads(r.content), {"total": 0, "rows": []})

    def test_archive_apply_not_param(self):
        """
        测试申请归档实例数据，参数不完整
        :return:
        """
        data = {
            "group_name": self.res_group.group_name,
            "src_instance_name": self.ins.instance_name,
            "src_db_name": "src_db_name",
            "src_table_name": "src_table_name",
            "mode": "dest",
            "dest_instance_name": self.ins.instance_name,
            "dest_db_name": "dest_db_name",
            "dest_table_name": "dest_table_name",
            "condition": "1=1",
            "no_delete": "true",
            "sleep": 10,
        }
        self.client.force_login(self.superuser)
        r = self.client.post(path="/archive/apply/", data=data)
        self.assertDictEqual(
            json.loads(r.content), {"status": 1, "msg": "请填写完整！", "data": {}}
        )

    def test_archive_apply_not_dest_param(self):
        """
        测试申请归档实例数据，目标实例不完整
        :return:
        """
        data = {
            "title": "title",
            "group_name": self.res_group.group_name,
            "src_instance_name": self.ins.instance_name,
            "src_db_name": "src_db_name",
            "src_table_name": "src_table_name",
            "mode": "dest",
            "condition": "1=1",
            "no_delete": "true",
            "sleep": 10,
        }
        self.client.force_login(self.superuser)
        r = self.client.post(path="/archive/apply/", data=data)
        self.assertDictEqual(
            json.loads(r.content),
            {"status": 1, "msg": "归档到实例时目标实例信息必选！", "data": {}},
        )

    def test_archive_apply_not_exist_review(self):
        """
        测试申请归档实例数据，未配置审批流程
        :return:
        """
        data = {
            "title": "title",
            "group_name": self.res_group.group_name,
            "src_instance_name": self.ins.instance_name,
            "src_db_name": "src_db_name",
            "src_table_name": "src_table_name",
            "mode": "dest",
            "dest_instance_name": self.ins.instance_name,
            "dest_db_name": "dest_db_name",
            "dest_table_name": "dest_table_name",
            "condition": "1=1",
            "no_delete": "true",
            "sleep": 10,
        }
        self.client.force_login(self.superuser)
        r = self.client.post(path="/archive/apply/", data=data)
        self.assertDictEqual(
            json.loads(r.content),
            {"data": {}, "msg": "新建审批流失败, 请联系管理员", "status": 1},
        )

    @patch("sql.archiver.async_task")
    def test_archive_apply(self, _async_task):
        """
        测试申请归档实例数据
        :return:
        """
        WorkflowAuditSetting.objects.create(
            workflow_type=3, group_id=1, audit_auth_groups="1"
        )
        data = {
            "title": "title",
            "group_name": self.res_group.group_name,
            "src_instance_name": self.ins.instance_name,
            "src_db_name": "src_db_name",
            "src_table_name": "src_table_name",
            "mode": "dest",
            "dest_instance_name": self.ins.instance_name,
            "dest_db_name": "dest_db_name",
            "dest_table_name": "dest_table_name",
            "condition": "1=1",
            "no_delete": "true",
            "sleep": 10,
        }
        self.client.force_login(self.superuser)
        r = self.client.post(path="/archive/apply/", data=data)
        self.assertEqual(json.loads(r.content)["status"], 0)

    @patch("sql.utils.workflow_audit.AuditV2.generate_audit_setting")
    def test_archive_apply_auto_pass(self, mock_generate_setting):
        mock_generate_setting.return_value = AuditSetting(
            auto_pass=True,
        )
        data = {
            "title": "title",
            "group_name": self.res_group.group_name,
            "src_instance_name": self.ins.instance_name,
            "src_db_name": "src_db_name",
            "src_table_name": "src_table_name",
            "mode": "dest",
            "dest_instance_name": self.ins.instance_name,
            "dest_db_name": "dest_db_name",
            "dest_table_name": "dest_table_name",
            "condition": "1=1",
            "no_delete": "true",
            "sleep": 10,
        }
        self.client.force_login(self.superuser)
        r = self.client.post(path="/archive/apply/", data=data)
        return_data = r.json()
        self.assertEqual(return_data["status"], 0)
        archive_config = ArchiveConfig.objects.get(id=return_data["data"]["archive_id"])
        assert archive_config.state == True
        assert archive_config.status == WorkflowStatus.PASSED

    @patch("sql.utils.workflow_audit.AuditV2.operate")
    @patch("sql.archiver.async_task")
    def test_archive_audit(self, _async_task, mock_operate):
        """
        测试审核归档实例数据
        :return:
        """
        mock_operate.return_value = None
        data = {
            "archive_id": self.archive_apply.id,
            "audit_status": WorkflowStatus.PASSED,
            "audit_remark": "xxxx",
        }
        # operate 被 patch 了, 这里强制设置一下, 走一下流程
        self.audit_flow.current_status = WorkflowStatus.PASSED
        self.audit_flow.save()
        self.client.force_login(self.superuser)
        r = self.client.post(path="/archive/audit/", data=data)
        self.assertRedirects(
            r, f"/archive/{self.archive_apply.id}/", fetch_redirect_response=False
        )
        self.archive_apply.refresh_from_db()
        assert self.archive_apply.state == True
        assert self.archive_apply.status == WorkflowStatus.PASSED

    @patch("sql.archiver.async_task")
    def test_add_archive_task(self, _async_task):
        """
        测试添加异步归档任务
        :return:
        """
        add_archive_task()

    @patch("sql.archiver.async_task")
    def test_add_archive(self, _async_task):
        """
        测试执行归档任务
        :return:
        """
        with self.assertRaises(Exception):
            archive(self.archive_apply.id)

    @patch("sql.archiver.async_task")
    def test_archive_log(self, _async_task):
        """
        测试获取归档日志
        :return:
        """
        data = {
            "archive_id": self.archive_apply.id,
        }
        self.client.force_login(self.superuser)
        r = self.client.post(path="/archive/log/", data=data)
        self.assertDictEqual(json.loads(r.content), {"total": 0, "rows": []})


def test_archive_detail_view(
    archive_apply,
    resource_group,
    admin_client,
    fake_generate_audit_setting,
    create_auth_group,
):
    audit = AuditV2(workflow=archive_apply, resource_group=resource_group.group_name)
    audit.create_audit()
    audit.workflow.save()
    response = admin_client.get(f"/archive/{archive_apply.id}/")
    assert response.status_code == 200
    assertTemplateUsed(response, "archivedetail.html")
    review_info = response.context["review_info"]
    assert len(review_info.nodes) == len(
        fake_generate_audit_setting.return_value.audit_auth_groups
    )
    assert review_info.nodes[0].group.name == create_auth_group.name
