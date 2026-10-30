"""Language selection tests that do not require a database."""

import json
from html.parser import HTMLParser
import re
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.template.loader import render_to_string
from django.urls import include, path
from django.utils.translation import gettext, override
from django.views.i18n import JavaScriptCatalog

from common.language import set_language


class _DisplayTextParser(HTMLParser):
    """Collect template text for assertions; this is not an HTML sanitizer."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored_tag = None

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.ignored_tag = tag

    def handle_endtag(self, tag):
        if tag == self.ignored_tag:
            self.ignored_tag = None

    def handle_data(self, data):
        if self.ignored_tag is None:
            self.parts.append(data)


def display_text(html):
    parser = _DisplayTextParser()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)


def language_page(request):
    return render(request, "language_selector.html")


def translated_page(request):
    return HttpResponse(gettext("workflow_finish"))


urlpatterns = [
    path("i18n/setlang/", set_language, name="set_language"),
    path("login/", language_page),
    path("signup/", translated_page),
    path("jsi18n/", JavaScriptCatalog.as_view()),
    path(
        "",
        include(
            (
                [
                    path(
                        "jsi18n/",
                        JavaScriptCatalog.as_view(),
                        name="javascript-catalog",
                    )
                ],
                "sql",
            )
        ),
    ),
]


@override_settings(
    ROOT_URLCONF=__name__,
    TEMPLATES=[
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [Path(__file__).resolve().parent.parent / "sql/templates"],
            "APP_DIRS": True,
            "OPTIONS": {
                "context_processors": ["django.template.context_processors.request"]
            },
        }
    ],
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
    LOCALE_PATHS=[Path(__file__).resolve().parent.parent / "sql" / "locale"],
    SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
    MIDDLEWARE=[
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "common.middleware.check_login_middleware.CheckLoginMiddleware",
    ],
)
class LanguagePreferenceTests(SimpleTestCase):
    def switch(self, language, **extra):
        return self.client.post(
            "/i18n/setlang/",
            {"language": language, "next": "/login/?next=/index/", **extra},
        )

    def test_default_and_supported_languages(self):
        self.assertEqual(settings.LANGUAGE_CODE, "zh-hans")
        self.assertEqual({code for code, _ in settings.LANGUAGES}, {"zh-hans", "en"})
        response = self.client.get("/login/")
        self.assertEqual(response.headers["Content-Language"], "zh-hans")
        self.assertContains(response, 'value="zh-hans" selected')

    def test_switch_and_persist_across_requests(self):
        for language, translated in [
            ("en", "Workflow finished"),
            ("zh-hans", "已正常结束"),
        ]:
            with self.subTest(language=language):
                response = self.switch(language)
                self.assertRedirects(
                    response, "/login/?next=/index/", fetch_redirect_response=False
                )
                cookie = response.cookies[settings.LANGUAGE_COOKIE_NAME]
                self.assertEqual(cookie.value, language)
                self.assertEqual(int(cookie["max-age"]), 365 * 24 * 60 * 60)
                self.assertEqual(cookie["samesite"], "Lax")
                response = self.client.get("/login/", HTTP_ACCEPT_LANGUAGE="fr")
                self.assertEqual(response.headers["Content-Language"], language)
                self.assertContains(response, f'value="{language}" selected')
                self.assertContains(self.client.get("/signup/"), translated)
                with patch(
                    "django.contrib.auth.middleware.get_user",
                    return_value=SimpleNamespace(is_authenticated=True),
                ):
                    response = self.client.get("/jsi18n/")
                self.assertContains(response, json.dumps(translated)[1:-1])

    def test_invalid_language_preserves_preference(self):
        self.switch("en")
        response = self.switch("fr")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)
        self.assertEqual(self.client.get("/login/").headers["Content-Language"], "en")

    def test_page_templates_include_language_form(self):
        request = RequestFactory().get("/login/?next=/index/")
        for template in ["base.html", "login.html"]:
            for language in ["en", "zh-hans"]:
                with self.subTest(template=template, language=language), override(
                    language
                ):
                    html = render_to_string(template, request=request)
                    self.assertIn(f'<html lang="{language}">', html)
                    self.assertIn('action="/i18n/setlang/"', html)
                    self.assertIn(f'value="{language}" selected', html)
                    self.assertIn('value="/login/?next=/index/"', html)

    def test_login_and_navigation_translations(self):
        request = RequestFactory().get("/login/")
        context = {
            "perms": {"sql": defaultdict(lambda: True)},
            "user": SimpleNamespace(is_superuser=True),
            "sign_up_enabled": True,
            "dingding_enabled": True,
        }
        for language, login_text, menu_text, error_title in [
            ("en", "Log in to Archery", "SQL Review", "Notice"),
            ("zh-hans", "登录 Archery", "SQL审核", "提示"),
        ]:
            with self.subTest(language=language), override(language):
                login = render_to_string("login.html", context, request=request)
                navigation = render_to_string("base.html", context, request=request)
                self.assertIn(login_text, login)
                self.assertIn(menu_text, navigation)
                self.assertIn(error_title, login)
                if language == "en":
                    self.assertIn("Log in with DingTalk", login)
                    self.assertIn("Create an account", login)
                    self.assertIn('placeholder="Confirm password"', login)
                    self.assertIn("Permission Groups", navigation)
                    self.assertIn("System information", navigation)
                    self.assertIn("Hello,", navigation)
                    # Include hidden menus and modal labels; allow the native language name.
                    for html in [login, navigation]:
                        visible_text = display_text(html).replace("简体中文", "")
                        self.assertIsNone(re.search(r"[\u4e00-\u9fff]", visible_text))

    def test_workflow_list_translation_and_locales(self):
        request = RequestFactory().get("/sqlworkflow/")
        # Simulate a label eagerly translated at import time; the option must use its stable key.
        context = {"status_list": [("workflow_finish", "已正常结束")]}
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string("sqlworkflow.html", context, request=request)
                if language == "en":
                    for label in [
                        "Submit SQL",
                        "Workflow name",
                        "Submitted by",
                        "Backup",
                        "Activity log",
                        "Last 7 days",
                        "June",
                        "No matching results",
                        "Workflow finished",
                    ]:
                        self.assertIn(label, html)
                    self.assertIn("locale: 'en-US'", html)
                    self.assertNotIn("bootstrap-table-zh-CN.min.js", html)
                    self.assertNotIn("defaults-zh_CN.min.js", html)
                else:
                    self.assertIn("提交SQL", html)
                    self.assertIn("已正常结束", html)
                    self.assertIn("locale: 'zh-CN'", html)
                    self.assertIn("bootstrap-table-zh-CN.min.js", html)
                    self.assertIn("defaults-zh_CN.min.js", html)
                # Values sent to the API stay stable across languages.
                self.assertIn('value="workflow_finish"', html)
                self.assertIn('"syntax_type":[0,1,2]', html)

    def test_user_admin_add_and_edit_labels_follow_language(self):
        from django.contrib.admin import AdminSite
        from sql.admin import UsersAdmin
        from sql.models import Users

        model_admin = UsersAdmin(Users, AdminSite())
        request = RequestFactory().get("/admin/sql/users/")
        request.user = SimpleNamespace(has_perm=lambda *args: True)
        for language in ["en", "zh-hans"]:
            for editing in [False, True]:
                with self.subTest(language=language, editing=editing), override(
                    language
                ):
                    preview = (
                        Users(
                            username="original-user", display="原始显示名", password="!"
                        )
                        if editing
                        else None
                    )
                    form_class = model_admin.get_form(request, obj=preview)
                    form = form_class(instance=preview)
                    for field in form.fields.values():
                        if hasattr(field, "queryset"):
                            field.queryset = field.queryset.none()
                    html = form.as_p()
                    headings = [
                        str(name)
                        for name, options in model_admin.get_fieldsets(request, preview)
                    ]
                    for text in (
                        [
                            "Authentication",
                            "Personal information",
                            "Permissions",
                            "Resource groups",
                        ]
                        if language == "en"
                        else ["认证信息", "个人信息", "权限信息", "资源组"]
                    ):
                        self.assertIn(text, headings)
                    for text in (
                        [
                            "Display name",
                            "DingTalk user ID",
                            "WeCom user ID",
                            "Feishu OpenID",
                            "Resource groups",
                        ]
                        if language == "en"
                        else [
                            "显示的中文名",
                            "钉钉UserID",
                            "企业微信UserID",
                            "飞书OpenID",
                            "资源组",
                        ]
                    ):
                        self.assertIn(text, html)
                    for field in [
                        "username",
                        "display",
                        "is_superuser",
                        "is_staff",
                        "is_active",
                        "user_permissions",
                        "groups",
                        "resource_group",
                    ]:
                        self.assertIn(f'name="{field}"', html)
                    if editing:
                        self.assertIn("original-user", html)
                        self.assertIn("原始显示名", html)
                        self.assertIn(
                            (
                                "Additional information"
                                if language == "en"
                                else "其他信息"
                            ),
                            headings,
                        )
                    else:
                        self.assertIn('name="password1"', html)
                        self.assertIn('name="password2"', html)
                    self.assertEqual(
                        str(Users._meta.verbose_name),
                        "User" if language == "en" else "用户管理",
                    )

    def test_remaining_business_pages_translate_without_changing_actions(self):
        expected = {
            "workflow.html": ("Pending approvals", "待办列表"),
            "sqlanalyze.html": ("Analysis options", "分析选项"),
            "rollback.html": ("Submit rollback request", "提交回滚请求"),
            "audit.html": ("Additional information", "额外信息"),
            "audit_sqlquery.html": ("Returned rows", "返回行数"),
            "audit_sqlworkflow.html": ("Workflow status", "工单状态"),
            "dashboard.html": ("SQL deployment statistics", "SQL上线统计"),
            "2fa.html": ("Enable two-step verification", "启用两步验证"),
        }
        for language in ["en", "zh-hans"]:
            with override(language):
                for name, labels in expected.items():
                    with self.subTest(language=language, page=name):
                        html = render_to_string(
                            name,
                            {
                                "LANGUAGE_CODE": language,
                                "verify_mode": "verify_config",
                                "auth_types": [],
                                "phone": "",
                                "username": "preview",
                                "audit_id": 0,
                            },
                            request=RequestFactory().get("/"),
                        )
                        self.assertIn(labels[language != "en"], html)
                        if name == "dashboard.html":
                            visible = display_text(html)
                            self.assertIn(labels[language != "en"], visible)
                            self.assertNotIn(labels[language == "en"], visible)
                        if name in [
                            "workflow.html",
                            "sqlanalyze.html",
                            "rollback.html",
                            "audit.html",
                            "audit_sqlquery.html",
                            "audit_sqlworkflow.html",
                        ]:
                            self.assertIn(
                                (
                                    "locale: 'en-US'"
                                    if language == "en"
                                    else "locale: 'zh-CN'"
                                ),
                                html,
                            )
        workflow_source = (
            Path(settings.BASE_DIR) / "sql/templates/workflow.html"
        ).read_text()
        self.assertIn('onclick="audit(0)"', workflow_source)
        self.assertIn('onclick="audit(1)"', workflow_source)
        self.assertIn(
            'value="totp"',
            (Path(settings.BASE_DIR) / "common/templates/2fa.html").read_text(),
        )

    def test_query_access_application_admin_preserves_privileges_and_status(self):
        from django.contrib.admin import AdminSite
        from django.contrib.admin.utils import label_for_field
        from sql.admin import QueryPrivilegesApplyAdmin
        from sql.models import QueryPrivilegesApply

        model_admin = QueryPrivilegesApplyAdmin(QueryPrivilegesApply, AdminSite())
        request = RequestFactory().get("/admin/sql/queryprivilegesapply/")
        request.user = SimpleNamespace(has_perm=lambda *args: True)
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language), patch.object(
                QueryPrivilegesApply,
                "save",
                side_effect=AssertionError("Must not change applications"),
            ):
                record = QueryPrivilegesApply(
                    apply_id=123,
                    title="原始申请",
                    db_list="原始数据库",
                    table_list="原始表",
                    status=0,
                    priv_type=1,
                    limit_num=100,
                )
                form = model_admin.get_form(request, obj=record)(instance=record)
                self.assertEqual(form["title"].value(), "原始申请")
                self.assertEqual(form["db_list"].value(), "原始数据库")
                self.assertEqual(form["table_list"].value(), "原始表")
                self.assertEqual(dict(form.fields["priv_type"].choices)[1], "DATABASE")
                self.assertEqual(dict(form.fields["priv_type"].choices)[2], "TABLE")
                if language == "en":
                    for label in dict(form.fields["status"].choices).values():
                        self.assertNotRegex(str(label), r"[\u3400-\u9fff]")
                    for name in model_admin.list_display:
                        self.assertNotRegex(
                            str(
                                label_for_field(name, QueryPrivilegesApply, model_admin)
                            ),
                            r"[\u3400-\u9fff]",
                        )
                self.assertEqual(
                    str(form.fields["title"].label),
                    "Request title" if language == "en" else "申请标题",
                )
                self.assertEqual(
                    (record.status, record.priv_type, record.limit_num), (0, 1, 100)
                )

    def test_query_log_admin_translates_choices_without_rewriting_sql(self):
        from django.contrib.admin import AdminSite
        from django.contrib.admin.utils import label_for_field
        from sql.admin import QueryLogAdmin
        from sql.models import QueryLog

        model_admin = QueryLogAdmin(QueryLog, AdminSite())
        request = RequestFactory().get("/admin/sql/querylog/")
        request.user = SimpleNamespace(has_perm=lambda *args: True)
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language), patch.object(
                QueryLog, "save", side_effect=AssertionError("Must not save logs")
            ):
                record = QueryLog(
                    pk=123,
                    sqllog="-- 原始 SQL，仅显示",
                    alias="原始标识",
                    user_display="原始名称",
                )
                form = model_admin.get_form(request, obj=record)(instance=record)
                self.assertEqual(form["sqllog"].value(), record.sqllog)
                self.assertEqual(form["alias"].value(), "原始标识")
                for name in ["priv_check", "hit_rule", "masking", "favorite"]:
                    choices = dict(QueryLog._meta.get_field(name).choices)
                    self.assertEqual(set(choices), {False, True})
                    if language == "en":
                        for label in choices.values():
                            self.assertNotRegex(str(label), r"[\u3400-\u9fff]")
                if language == "en":
                    for name in model_admin.list_display:
                        self.assertNotRegex(
                            str(label_for_field(name, QueryLog, model_admin)),
                            r"[\u3400-\u9fff]",
                        )
                self.assertEqual(
                    str(form.fields["sqllog"].label),
                    "SQL statement" if language == "en" else "执行的查询语句",
                )

    def test_archive_config_admin_translates_without_saving_or_running(self):
        from django.contrib.admin import AdminSite
        from django.contrib.admin.utils import label_for_field
        from sql.admin import ArchiveConfigAdmin
        from sql.models import ArchiveConfig

        model_admin = ArchiveConfigAdmin(ArchiveConfig, AdminSite())
        request = RequestFactory().get("/admin/sql/archiveconfig/")
        request.user = SimpleNamespace(has_perm=lambda *args: True)
        for language in ["en", "zh-hans"]:
            for editing in [False, True]:
                with self.subTest(language=language, editing=editing), override(
                    language
                ), patch.object(
                    ArchiveConfig,
                    "save",
                    side_effect=AssertionError("Must not save archive configuration"),
                ):
                    record = (
                        ArchiveConfig(
                            id=123,
                            title="原始归档",
                            condition="id < 0",
                            mode="file",
                            state=False,
                            no_delete=True,
                        )
                        if editing
                        else None
                    )
                    form = model_admin.get_form(request, obj=record)(instance=record)
                    self.assertEqual(
                        str(form.fields["title"].label),
                        "Archive description" if language == "en" else "归档配置说明",
                    )
                    modes = dict(form.fields["mode"].choices)
                    self.assertEqual(set(modes) - {""}, {"file", "dest", "purge"})
                    if language == "en":
                        for mode in ["file", "dest", "purge"]:
                            self.assertNotRegex(str(modes[mode]), r"[\u3400-\u9fff]")
                        for name in model_admin.list_display:
                            self.assertNotRegex(
                                str(label_for_field(name, ArchiveConfig, model_admin)),
                                r"[\u3400-\u9fff]",
                            )
                    if editing:
                        self.assertEqual(form["condition"].value(), "id < 0")
                        self.assertEqual(form["title"].value(), "原始归档")
                        self.assertFalse(record.state)
                        self.assertTrue(record.no_delete)

    def test_workflow_log_labels_preserve_stored_operation_text(self):
        from django.contrib.admin import AdminSite
        from sql.admin import WorkflowLogAdmin
        from sql.models import WorkflowLog
        from common.utils.const import WorkflowAction

        model_admin = WorkflowLogAdmin(WorkflowLog, AdminSite())
        request = RequestFactory().get("/admin/sql/workflowlog/")
        request.user = SimpleNamespace(has_perm=lambda *args: True)
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                for code, description in WorkflowAction.choices:
                    record = WorkflowLog(
                        id=123,
                        operation_type=code,
                        operation_type_desc=description,
                        operation_info="原始操作信息",
                        operator="preview",
                        operator_display="原始名称",
                    )
                    form = model_admin.get_form(request, obj=record)(instance=record)
                    if language == "en":
                        self.assertNotRegex(
                            model_admin.operation_description(record),
                            r"[\u3400-\u9fff]",
                        )
                        self.assertNotRegex(
                            str(dict(form.fields["operation_type"].choices)[code]),
                            r"[\u3400-\u9fff]",
                        )
                    else:
                        self.assertEqual(
                            model_admin.operation_description(record), description
                        )
                    self.assertEqual(form["operation_type_desc"].value(), description)
                    self.assertEqual(form["operation_info"].value(), "原始操作信息")
                    self.assertEqual(record.operation_type, code)
                self.assertEqual(
                    model_admin.operation_description(
                        WorkflowLog(operation_type_desc="原始自定义动作")
                    ),
                    "原始自定义动作",
                )

    def test_workflow_approval_admin_translates_choices_without_changing_codes(self):
        from django.contrib.admin import AdminSite
        from django.contrib.admin.utils import label_for_field
        from sql.admin import WorkflowAuditAdmin
        from sql.models import WorkflowAudit
        from common.utils.const import WorkflowType, WorkflowStatus

        model_admin = WorkflowAuditAdmin(WorkflowAudit, AdminSite())
        request = RequestFactory().get("/admin/sql/workflowaudit/")
        request.user = SimpleNamespace(has_perm=lambda *args: True)
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language), patch.object(
                WorkflowAudit,
                "save",
                side_effect=AssertionError("Must not change approvals"),
            ):
                record = WorkflowAudit(
                    audit_id=123,
                    workflow_title="原始申请",
                    workflow_remark="原始备注",
                    current_status=0,
                    workflow_type=2,
                )
                form = model_admin.get_form(request, obj=record)(instance=record)
                self.assertEqual(form["workflow_title"].value(), "原始申请")
                self.assertEqual(form["workflow_remark"].value(), "原始备注")
                for field_name, choices in [
                    ("workflow_type", WorkflowType.choices),
                    ("current_status", WorkflowStatus.choices),
                ]:
                    translated = dict(form.fields[field_name].choices)
                    for value, original in choices:
                        self.assertIn(value, translated)
                        if language == "en":
                            self.assertNotRegex(
                                str(translated[value]), r"[\u3400-\u9fff]"
                            )
                        else:
                            self.assertEqual(str(translated[value]), original)
                for name in model_admin.list_display:
                    if language == "en":
                        self.assertNotRegex(
                            str(label_for_field(name, WorkflowAudit, model_admin)),
                            r"[\u3400-\u9fff]",
                        )
                self.assertEqual(record.current_status, 0)
                self.assertEqual(record.workflow_type, 2)

    def test_parameter_history_labels_preserve_record_values(self):
        from django.contrib.admin import AdminSite
        from django.contrib.admin.utils import label_for_field
        from sql.admin import ParamHistoryAdmin
        from sql.models import ParamHistory

        model_admin = ParamHistoryAdmin(ParamHistory, AdminSite())
        request = RequestFactory().get("/admin/sql/paramhistory/")
        request.user = SimpleNamespace(has_perm=lambda *args: True)
        labels = {
            "variable_name": ("Parameter name", "参数名"),
            "old_var": ("Previous value", "修改前参数值"),
            "new_var": ("New value", "修改后参数值"),
            "set_sql": ("Parameter change SQL", "在线变更配置执行的SQL语句"),
            "user_name": ("Changed by", "修改人"),
            "user_display": ("Changed by (display name)", "修改人中文名"),
        }
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language), patch.object(
                ParamHistory,
                "save",
                side_effect=AssertionError("Must not save history"),
            ), patch(
                "socket.create_connection",
                side_effect=AssertionError("Must not connect"),
            ):
                instance = ParamHistory(
                    pk=123,
                    variable_name="preview_parameter",
                    old_var="原始旧值",
                    new_var="原始新值",
                    set_sql="-- 原始 SQL，仅显示",
                    user_name="preview",
                    user_display="原始名称",
                )
                form = model_admin.get_form(request, obj=instance)(instance=instance)
                for name, translations in labels.items():
                    self.assertEqual(
                        str(form.fields[name].label), translations[language != "en"]
                    )
                    self.assertEqual(form[name].value(), getattr(instance, name))
                for name in model_admin.list_display:
                    if language == "en":
                        self.assertNotRegex(
                            str(label_for_field(name, ParamHistory, model_admin)),
                            r"[\u3400-\u9fff]",
                        )
                self.assertEqual(
                    str(ParamHistory._meta.verbose_name),
                    (
                        "Parameter change history"
                        if language == "en"
                        else "实例参数修改历史"
                    ),
                )
                self.assertEqual(model_admin.list_filter, ("instance", "user_display"))
                self.assertEqual(model_admin.search_fields, ("variable_name",))

    def test_ssh_tunnel_admin_translates_without_credentials_or_connections(self):
        from django.contrib.admin import AdminSite
        from django.contrib.admin.utils import label_for_field
        from sql.admin import TunnelAdmin
        from sql.models import Tunnel

        model_admin = TunnelAdmin(Tunnel, AdminSite())
        request = RequestFactory().get("/admin/sql/tunnel/")
        request.user = SimpleNamespace(has_perm=lambda *args: True)
        expected = {
            "tunnel_name": ("Tunnel name", "隧道名称"),
            "host": ("SSH host", "隧道连接"),
            "port": ("Port", "端口"),
            "user": ("Username", "用户名"),
            "password": ("Password", "密码"),
            "pkey": ("Private key", "密钥"),
            "pkey_path": ("Private key file", "密钥地址"),
            "pkey_password": ("Private key passphrase", "密钥密码"),
        }
        for language in ["en", "zh-hans"]:
            for editing in [False, True]:
                with self.subTest(language=language, editing=editing), override(
                    language
                ), patch.object(
                    Tunnel, "save", side_effect=AssertionError("Must not save tunnels")
                ), patch(
                    "socket.create_connection",
                    side_effect=AssertionError("Must not connect"),
                ):
                    instance = (
                        Tunnel(pk=123, tunnel_name="原始隧道", host="127.0.0.1", port=1)
                        if editing
                        else None
                    )
                    form = model_admin.get_form(request, obj=instance)(
                        instance=instance
                    )
                    for name, labels in expected.items():
                        self.assertEqual(
                            str(form.fields[name].label), labels[language != "en"]
                        )
                    for name in ["password", "pkey_password", "pkey"]:
                        self.assertIn(form[name].value(), (None, ""))
                    self.assertEqual(
                        model_admin.get_readonly_fields(request, instance),
                        ("id",) if editing else (),
                    )
                    for name in model_admin.list_display:
                        if language == "en":
                            self.assertNotRegex(
                                str(label_for_field(name, Tunnel, model_admin)),
                                r"[\u3400-\u9fff]",
                            )
                    if editing:
                        self.assertEqual(instance.tunnel_name, "原始隧道")

    def test_instance_tag_admin_labels_and_readonly_code_follow_language(self):
        from django.contrib.admin import AdminSite
        from django.contrib.admin.utils import label_for_field
        from sql.admin import InstanceTagAdmin
        from sql.models import InstanceTag

        model_admin = InstanceTagAdmin(InstanceTag, AdminSite())
        request = RequestFactory().get("/admin/sql/instancetag/")
        request.user = SimpleNamespace(has_perm=lambda *args: True)
        for language in ["en", "zh-hans"]:
            for editing in [False, True]:
                with self.subTest(language=language, editing=editing), override(
                    language
                ):
                    instance = (
                        InstanceTag(
                            pk=123, tag_code="preview_code", tag_name="原始标签"
                        )
                        if editing
                        else None
                    )
                    form = model_admin.get_form(request, obj=instance)(
                        instance=instance
                    )
                    self.assertEqual(
                        str(form.fields["tag_name"].label),
                        "Tag name" if language == "en" else "标签名称",
                    )
                    self.assertEqual(
                        str(form.fields["active"].label),
                        "Active" if language == "en" else "激活状态",
                    )
                    self.assertEqual(
                        model_admin.get_readonly_fields(request, instance),
                        ("tag_code",) if editing else (),
                    )
                    if editing:
                        self.assertNotIn("tag_code", form.fields)
                        self.assertEqual(form["tag_name"].value(), "原始标签")
                        self.assertEqual(instance.tag_code, "preview_code")
                    else:
                        self.assertEqual(
                            str(form.fields["tag_code"].label),
                            "Tag code" if language == "en" else "标签代码",
                        )
                    for name in model_admin.list_display:
                        label = str(label_for_field(name, InstanceTag, model_admin))
                        if language == "en":
                            self.assertNotRegex(label, r"[\u3400-\u9fff]")

    def test_cloud_credential_admin_translates_without_decrypting_or_saving(self):
        from django.contrib.admin import AdminSite
        from django.contrib.admin.utils import label_for_field
        from sql.admin import CloudAccessKeyAdmin
        from sql.models import CloudAccessKey

        model_admin = CloudAccessKeyAdmin(CloudAccessKey, AdminSite())
        request = RequestFactory().get("/admin/sql/cloudaccesskey/")
        request.user = SimpleNamespace(has_perm=lambda *args: True)
        labels = {
            "type": ("Cloud provider", "云服务商"),
            "key_id": ("Access key ID", "访问密钥ID"),
            "key_secret": ("Access key secret", "访问密钥"),
            "remark": ("Description", "备注"),
        }
        for language in ["en", "zh-hans"]:
            for editing in [False, True]:
                with self.subTest(language=language, editing=editing), override(
                    language
                ), patch.object(
                    CloudAccessKey,
                    "save",
                    side_effect=AssertionError("Must not save credentials"),
                ), patch(
                    "sql.models.Crypto.decrypt",
                    side_effect=AssertionError("Must not decrypt credentials"),
                ):
                    instance = (
                        CloudAccessKey(pk=123, type="aliyun", remark="原始备注")
                        if editing
                        else None
                    )
                    form = model_admin.get_form(request, obj=instance)(
                        instance=instance
                    )
                    for name, values in labels.items():
                        self.assertEqual(
                            str(form.fields[name].label), values[language != "en"]
                        )
                    self.assertEqual(
                        str(dict(form.fields["type"].choices)["aliyun"]),
                        "Alibaba Cloud" if language == "en" else "阿里云",
                    )
                    self.assertIn(form["key_id"].value(), (None, ""))
                    self.assertIn(form["key_secret"].value(), (None, ""))
                    for column in model_admin.list_display:
                        label = str(
                            label_for_field(column, CloudAccessKey, model_admin)
                        )
                        if language == "en":
                            self.assertNotRegex(label, r"[\u3400-\u9fff]")
                    if editing:
                        self.assertEqual(
                            model_admin.cloud_provider(instance),
                            "Alibaba Cloud" if language == "en" else "阿里云",
                        )
                        self.assertEqual(model_admin.description(instance), "原始备注")
                        self.assertEqual(instance.type, "aliyun")
                        self.assertTrue(instance._state.adding)

    def test_twofactor_admin_labels_for_add_and_edit_without_secrets(self):
        from django.contrib.admin import AdminSite
        from sql.admin import TwoFactorAuthConfigAdmin
        from sql.models import TwoFactorAuthConfig

        from django.contrib.admin.utils import label_for_field

        model_admin = TwoFactorAuthConfigAdmin(TwoFactorAuthConfig, AdminSite())
        request = RequestFactory().get("/admin/sql/twofactorauthconfig/")
        request.user = SimpleNamespace(has_perm=lambda *args: True)
        for language in ["en", "zh-hans"]:
            for editing in [False, True]:
                with self.subTest(language=language, editing=editing), override(
                    language
                ):
                    instance = (
                        TwoFactorAuthConfig(
                            pk=123, username="preview", auth_type="totp"
                        )
                        if editing
                        else None
                    )
                    form = model_admin.get_form(request, obj=instance)(
                        instance=instance
                    )
                    form.fields["user"].queryset = form.fields["user"].queryset.none()
                    expected = {
                        "username": ("Username", "用户名"),
                        "auth_type": ("Authentication type", "认证类型"),
                        "phone": ("Phone number", "手机号码"),
                        "secret_key": ("User secret key", "用户密钥"),
                    }
                    for name, labels in expected.items():
                        self.assertEqual(
                            str(form.fields[name].label), labels[language != "en"]
                        )
                    for name in model_admin.list_display:
                        label = str(
                            label_for_field(name, TwoFactorAuthConfig, model_admin)
                        )
                        if language == "en":
                            self.assertNotRegex(label, r"[\u3400-\u9fff]")
                    choices = dict(form.fields["auth_type"].choices)
                    self.assertEqual(
                        str(choices["totp"]),
                        (
                            "Google Authenticator"
                            if language == "en"
                            else "Google身份验证器"
                        ),
                    )
                    self.assertEqual(
                        str(choices["sms"]),
                        "SMS verification code" if language == "en" else "短信验证码",
                    )
                    self.assertIsNone(form["secret_key"].value())
                    self.assertEqual(TwoFactorAuthConfig._meta.db_table, "2fa_config")
                    self.assertEqual(
                        TwoFactorAuthConfig._meta.unique_together,
                        (("user", "auth_type"),),
                    )

    def test_role_admin_translates_permission_choices_and_preserves_behavior(self):
        from django.contrib import admin
        from django.contrib.auth.admin import GroupAdmin
        from django.contrib.auth.models import Group
        from sql.admin import RoleAdmin, user_permission_label
        from sql.models import Users

        model_admin = admin.site._registry[Group]
        self.assertIsInstance(model_admin, RoleAdmin)
        request = RequestFactory().get("/admin/auth/group/")
        request.user = SimpleNamespace(has_perm=lambda *args: True)
        self.assertEqual(model_admin.search_fields, GroupAdmin.search_fields)
        self.assertEqual(model_admin.filter_horizontal, GroupAdmin.filter_horizontal)
        preview = SimpleNamespace(
            name="Can change 用户管理",
            codename="change_users",
            pk=42,
            content_type=SimpleNamespace(
                app_label="sql", model="users", model_class=lambda: Users
            ),
        )
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                form = model_admin.get_form(request)()
                field = form.fields["permissions"]
                self.assertIs(field.label_from_instance, user_permission_label)
                self.assertEqual(
                    field.label_from_instance(preview), user_permission_label(preview)
                )
                self.assertEqual(
                    str(form.fields["name"].label),
                    "Name" if language == "en" else "名称",
                )
                self.assertEqual(
                    str(field.label), "Permissions" if language == "en" else "权限"
                )
                self.assertEqual(preview.pk, 42)
                self.assertEqual(preview.name, "Can change 用户管理")

    def test_user_permission_labels_translate_without_mutating_permissions(self):
        from sql.admin import user_permission_label
        from sql.models import Users, Permission as BusinessPermission

        class PreviewPermission:
            def __init__(
                self, codename, name, model="permission", model_class=BusinessPermission
            ):
                self.pk = 42
                self.codename = codename
                self.name = name
                self.content_type = SimpleNamespace(
                    app_label="sql", model=model, model_class=lambda: model_class
                )

            def __str__(self):
                return self.name

        default = PreviewPermission(
            "change_users", "Can change 用户管理", "users", Users
        )
        with override("en"):
            self.assertEqual(
                user_permission_label(default), "sql | User | Can change User"
            )
            for code, name in BusinessPermission._meta.permissions:
                permission = PreviewPermission(code, name)
                self.assertNotRegex(
                    user_permission_label(permission), r"[\u4e00-\u9fff]"
                )
                self.assertEqual(
                    (permission.pk, permission.codename, permission.name),
                    (42, code, name),
                )
            unknown = PreviewPermission("vendor_permission", "原始自定义权限")
            self.assertTrue(user_permission_label(unknown).endswith("原始自定义权限"))
        with override("zh-hans"):
            self.assertEqual(user_permission_label(default), "Can change 用户管理")
        self.assertEqual(default.name, "Can change 用户管理")

    def test_configuration_translates_sections_help_and_actions_without_rewriting_values(
        self,
    ):
        from html.parser import HTMLParser
        from common.utils.const import WorkflowType

        config = defaultdict(
            str,
            {
                "announcement_content": "原始公告",
                "default_query_template": "原始模板 {{db_type}} {{user_input}}",
                "auto_review_tag": "preview_tag",
                "auto_review_db_type": "mysql",
            },
        )
        context = {
            "config": config,
            "workflow_choices": WorkflowType,
            "group_list": [SimpleNamespace(group_name="原始资源组")],
            "auth_group_list": [SimpleNamespace(name="原始权限组")],
            "instance_tags": [
                SimpleNamespace(tag_code="preview_tag", tag_name="原始实例标签")
            ],
            "db_type": ["mysql"],
        }
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "config.html", context, request=RequestFactory().get("/config/")
                )
                expected = (
                    [
                        "System settings",
                        "Workflow approval settings",
                        "goInception configuration",
                        "Feature configuration",
                        "Data export configuration",
                        "Notification configuration",
                        "SMS service",
                        "OIDC configuration",
                        "OpenAI configuration",
                        "Other settings",
                        "Save configuration",
                        "Test connection",
                        "Sync users",
                        "Update workflow",
                        "Reset",
                        "Backup database host",
                        "Require 2FA at login",
                        "Custom parameters in JSON",
                        "Submission",
                        "Cancellation",
                        "Query access request",
                        "Data archival request",
                    ]
                    if language == "en"
                    else [
                        "系统设置",
                        "工单审核流配置",
                        "功能模块配置",
                        "通知配置",
                        "短信服务",
                        "OIDC 配置",
                        "其他配置",
                        "保存配置",
                        "测试连接",
                        "同步用户",
                        "变更",
                        "刷新",
                    ]
                )
                for text in expected:
                    self.assertIn(text, html)
                for text in [
                    "原始公告",
                    "原始模板 {{db_type}} {{user_input}}",
                    "原始资源组",
                    "原始权限组",
                    "原始实例标签",
                    'key="enforce_2fa"',
                    'key="storage_type"',
                    'key="default_query_template"',
                    'value="s3c"',
                    "['Apply', 'Pass', 'Execute', 'Cancel']",
                    "phaseLabels[phases[i]]",
                    "/config/change/",
                    "/group/changeauditors/",
                ]:
                    self.assertIn(text, html)
                if language == "en":

                    class HelpAttributes(HTMLParser):
                        def handle_starttag(self, tag, attributes):
                            for name, value in attributes:
                                if (
                                    name
                                    in [
                                        "placeholder",
                                        "data-placeholder",
                                        "data-name",
                                        "data-none-selected-text",
                                        "data-on-text",
                                        "data-off-text",
                                    ]
                                    and value
                                ):
                                    if re.search(r"[\u4e00-\u9fff]", value):
                                        raise AssertionError((name, value))

                    HelpAttributes().feed(html)

    def test_resource_group_pages_translate_controls_and_keep_relation_codes(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                request = RequestFactory().get("/group/")
                listing = render_to_string("group.html", request=request)
                relations = render_to_string(
                    "groupmgmt.html",
                    {
                        "group": SimpleNamespace(group_id=1, group_name="原始组名"),
                    },
                    request=request,
                )
                for text in (
                    ["Add group", "Group name", "Linked objects", "Manage", "en-US"]
                    if language == "en"
                    else ["添加组", "组名称", "关联对象", "管理", "zh-CN"]
                ):
                    self.assertIn(text, listing)
                for text in (
                    [
                        "All types",
                        "User",
                        "Instance",
                        "Add linked objects",
                        "Linked object type",
                        "{0} selected",
                        "Cancel",
                        "Submit",
                        "en-US",
                    ]
                    if language == "en"
                    else [
                        "全部",
                        "用户",
                        "实例",
                        "新增关联对象",
                        "关联对象类型",
                        "已选中{0}项",
                        "取消",
                        "提交",
                        "zh-CN",
                    ]
                ):
                    self.assertIn(text, relations)
                for text in [
                    "原始组名",
                    "value=0",
                    "value=1",
                    "case 0:",
                    "case 1:",
                    "/group/unassociated/",
                    "/group/addrelation/",
                    "JSON.stringify(object_info)",
                ]:
                    self.assertIn(text, relations)
                if language == "en":
                    self.assertIn('onclick="addRelation()">Submit</button>', relations)
                self.assertIn("switch (Number(value))", relations)
                self.assertIn("/admin/sql/resourcegroup/add/", listing)
                self.assertIn("/change/", listing)
                self.assertNotIn("queryParams(e)", listing + relations)

    def test_resource_group_add_and_edit_fields_follow_active_language(self):
        from django.forms import modelform_factory
        from sql.models import ResourceGroup

        fields = [
            "group_name",
            "ding_webhook",
            "feishu_webhook",
            "qywx_webhook",
            "is_deleted",
        ]
        for language in ["en", "zh-hans"]:
            for editing in [False, True]:
                with self.subTest(language=language, editing=editing), override(
                    language
                ):
                    form_class = modelform_factory(ResourceGroup, fields=fields)
                    instance = (
                        ResourceGroup(group_id=1, group_name="原始组名", is_deleted=0)
                        if editing
                        else None
                    )
                    html = form_class(instance=instance).as_p()
                    for text in (
                        [
                            "Group name",
                            "DingTalk webhook URL",
                            "Feishu webhook URL",
                            "WeCom webhook URL",
                            "Deleted",
                            "No",
                            "Yes",
                        ]
                        if language == "en"
                        else [
                            "组名称",
                            "钉钉webhook地址",
                            "飞书webhook地址",
                            "企业微信webhook地址",
                            "是否删除",
                            "否",
                            "是",
                        ]
                    ):
                        self.assertIn(text, html)
                    for value in ['value="0"', 'value="1"', 'name="group_name"']:
                        self.assertIn(value, html)
                    if editing:
                        self.assertIn("原始组名", html)

    def test_schemasync_translates_selectors_and_empty_difference_tables(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "schemasync.html", request=RequestFactory().get("/schemasync/")
                )
                for text in (
                    [
                        "Options",
                        "Select a source instance:",
                        "Select a source database:",
                        "Select a target instance:",
                        "Select a target database:",
                        "All databases",
                        "Compare schemas",
                        "Difference log",
                        "Patch SQL",
                        "Revert SQL",
                        "No comparison results yet.",
                    ]
                    if language == "en"
                    else [
                        "操作选项",
                        "请选择源实例",
                        "请选择目标数据库",
                        "全部",
                        "Schema对比",
                        "差异日志",
                        "变更SQL",
                        "回滚SQL",
                        "尚无对比结果",
                    ]
                ):
                    self.assertIn(text, html)
                for text in [
                    'value="all"',
                    "--sync-auto-inc",
                    "--sync-comments",
                    "sync_auto_inc:",
                    "sync_comments:",
                    "/instance/schemasync/",
                    "target_instance_name:",
                    "target_db_name:",
                    ".text(result.diff_stdout",
                    ".text(result.patch_stdout",
                    ".text(result.revert_stdout",
                ]:
                    self.assertIn(text, html)
                self.assertEqual(
                    html.count('class="table schema-comparison-result"'), 3
                )
                self.assertNotIn(".html(finalHtml)", html)
                self.assertNotIn('id="schemadiff-result" style="display:none;"', html)

    def test_my2sql_translates_filters_and_renders_empty_results_without_parsing(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "my2sql.html", request=RequestFactory().get("/my2sql/")
                )
                for text in (
                    [
                        "Options",
                        "Parser threads:",
                        "Parsing range:",
                        "Object filters:",
                        "Get SQL",
                        "Submit workflow",
                        "Extra information",
                        "Full SQL",
                        "Full extra information",
                        "Save to file (background task)",
                        "en-US",
                        "language: 'en'",
                    ]
                    if language == "en"
                    else [
                        "操作选项",
                        "解析线程数",
                        "获取SQL",
                        "提交工单",
                        "完整SQL",
                        "zh-CN",
                    ]
                ):
                    self.assertIn(text, html)
                for text in [
                    "-work-type rollback",
                    "-ignore-primaryKey-forInsert",
                    "-do-not-add-prifixDb",
                    'value="insert"',
                    'value="update"',
                    'value="delete"',
                    "split('Size:')",
                    "my2sqlSubmitSqlContent",
                    "/binlog/my2sql/",
                    "hasGeneratedMy2sqlRows = false",
                    "renderMy2sqlTable([])",
                    "data: rows",
                    "hasGeneratedMy2sqlRows && hasSqlRows",
                ]:
                    self.assertIn(text, html)
                self.assertIn(
                    'id="btn-submit-my2sql-workflow" class="btn btn-success disabled" disabled',
                    html,
                )

    def test_archive_detail_translates_actions_and_preserves_archive_values(self):
        for language in ["en", "zh-hans"]:
            for mode in ["file", "dest", "purge"]:
                for status in [0, 1]:
                    config = SimpleNamespace(
                        id=42,
                        title="原始归档申请",
                        status=status,
                        state=False,
                        mode=mode,
                        no_delete=True,
                        sleep=1,
                        user_display="Developer",
                        src_instance="原始源实例",
                        src_db_name="原始数据库",
                        src_table_name="原始表",
                        dest_instance="原始目标实例",
                        dest_db_name="目标数据库",
                        dest_table_name="目标表",
                        resource_group="原始组",
                        condition="id < 3 AND label = '原始条件'",
                    )
                    with self.subTest(
                        language=language, mode=mode, status=status
                    ), override(language):
                        html = render_to_string(
                            "archivedetail.html",
                            {
                                "archive_config": config,
                                "can_review": True,
                                "perms": {"sql": {"archive_mgt": True}},
                                "review_info": SimpleNamespace(nodes=[]),
                            },
                            request=RequestFactory().get("/archive/42/"),
                        )
                        for text in (
                            [
                                "Request information",
                                "Archive configuration",
                                "Execution logs",
                                "Source information",
                                "Target information",
                                "Error details",
                                "en-US",
                            ]
                            if language == "en"
                            else [
                                "其他信息",
                                "归档配置信息",
                                "归档日志",
                                "源信息",
                                "目标信息",
                                "错误信息",
                                "zh-CN",
                            ]
                        ):
                            self.assertIn(text, html)
                        for text in [
                            "原始归档申请",
                            "原始源实例",
                            "原始条件",
                            "archive_id:",
                            "/archive/log/",
                            "/archive/once/",
                            "archive_enabled",
                        ]:
                            self.assertIn(text, html)
                        if status == 0:
                            self.assertIn('id="btnPass"', html)
                            self.assertNotIn('id="btn_archive_once"', html)
                            self.assertIn('name="audit_status" value="2"', html)
                            if language == "en":
                                self.assertIn('value="Approve"', html)
                                self.assertIn('value="Reject request"', html)
                        else:
                            self.assertIn('id="btn_archive_once"', html)
                            self.assertNotIn('id="btnPass"', html)

    def test_archive_execution_logs_include_original_statistics(self):
        from sql.archiver import archive_log

        row = {
            "statistics": "原始统计 <value>",
            "cmd": "pt-archiver --preview-only",
            "error_info": "原始错误",
        }
        with patch("sql.archiver.ArchiveLog.objects.filter") as filtered:
            logs = filtered.return_value.annotate.return_value
            logs.count.return_value = 1
            values = logs.order_by.return_value.__getitem__.return_value.values
            values.return_value = [row]
            request = RequestFactory().get(
                "/archive/log/", {"archive_id": 42, "limit": 20}
            )
            request.user = SimpleNamespace(has_perms=lambda permissions: True)
            response = archive_log(request)
            self.assertIn("statistics", values.call_args.args)
            self.assertEqual(json.loads(response.content)["rows"], [row])

    def test_archive_list_translates_controls_and_preserves_archive_codes(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "archive.html",
                    {
                        "ins_list": [SimpleNamespace(id=2, instance_name="原始实例")],
                        "group_list": [SimpleNamespace(group_name="原始组")],
                        "perms": {"sql": {"archive_mgt": True}},
                    },
                    request=RequestFactory().get("/archive/"),
                )
                expected = (
                    [
                        "All instances",
                        "Enabled status",
                        "Enabled",
                        "Disabled",
                        "Request archival",
                        "Add configuration",
                        "Archive mode",
                        "Source data",
                        "Archive to file",
                        "Archive to another instance",
                        "Delete directly",
                        "Activity log",
                        "en-US",
                    ]
                    if language == "en"
                    else [
                        "全部实例",
                        "启用状态",
                        "申请归档",
                        "添加配置",
                        "归档模式",
                        "保留",
                        "操作日志",
                        "zh-CN",
                    ]
                )
                for text in expected:
                    self.assertIn(text, html)
                for text in [
                    "原始实例",
                    "原始组",
                    "value='file'",
                    "value='dest'",
                    "value='purge'",
                    'value="true"',
                    'value="false"',
                    "filter_instance_id:",
                    "workflow_type = 3",
                    "/archive/list/",
                    "/archive/apply/",
                    "return labels[value] || value",
                ]:
                    self.assertIn(text, html)
                self.assertNotIn("queryParams(e)", html)
                self.assertIn('id="archive_state"', html)
                self.assertIn('state: $("#archive_state").val()', html)

    def test_export_detail_translates_information_actions_and_download(self):
        for language in ["en", "zh-hans"]:
            for status in ["workflow_manreviewing", "workflow_finish"]:
                waiting = status == "workflow_manreviewing"
                workflow = SimpleNamespace(
                    id=42,
                    workflow_name="原始导出标题",
                    engineer="devadmin",
                    status=status,
                    engineer_display="Developer",
                    db_name="原始数据库",
                    instance=SimpleNamespace(instance_name="原始实例"),
                    group_name="原始组",
                    sqlworkflowcontent=SimpleNamespace(
                        sql_content="SELECT '原始 SQL';"
                    ),
                    get_syntax_type_display="数据导出",
                    is_offline_export=True,
                    is_backup=False,
                    export_format="xlsx",
                    file_name="",
                )
                with self.subTest(language=language, status=status), override(language):
                    html = render_to_string(
                        "detail.html",
                        {
                            "workflow_detail": workflow,
                            "audit_id": 84,
                            "user": SimpleNamespace(
                                username="devadmin", is_superuser=True
                            ),
                            "is_can_review": waiting,
                            "is_can_cancel": waiting,
                            "review_info": SimpleNamespace(nodes=[]),
                        },
                        request=RequestFactory().get("/workflow/84/"),
                    )
                    for text in (
                        [
                            "Request information",
                            "Export format",
                            "Export file",
                            "No file generated",
                            "Excel",
                            "Workflow logs",
                            "Download error",
                        ]
                        if language == "en"
                        else [
                            "申请信息",
                            "导出格式",
                            "导出文件",
                            "尚未生成文件",
                            "工单日志",
                        ]
                    ):
                        self.assertIn(text, html)
                    for text in [
                        "原始导出标题",
                        "原始 SQL",
                        "原始实例",
                        "原始组",
                        "/api/v1/sql-workflows/84/logs/",
                        "encodeURIComponent(file_name)",
                    ]:
                        self.assertIn(text, html)
                    if waiting:
                        self.assertIn('id="btnPass"', html)
                        self.assertIn('id="btnReject"', html)
                        self.assertNotIn('id="btnDownload"', html)
                    else:
                        self.assertIn('id="btnDownload"', html)
                        self.assertNotIn('id="btnPass"', html)

    def test_workflow_detail_translations_preserve_commands_and_content(self):
        workflow = SimpleNamespace(
            id=42,
            workflow_name="Original workflow",
            engineer="devadmin",
            status="workflow_review_pass",
            engineer_display="Developer",
            instance=SimpleNamespace(instance_name="Original instance"),
            sqlworkflowcontent=SimpleNamespace(sql_content="SELECT '原始SQL';"),
            get_syntax_type_display="其他",
            is_offline_export=False,
            is_backup=True,
        )
        context = {
            "workflow_detail": workflow,
            "audit_id": 84,
            "user": SimpleNamespace(username="devadmin", is_superuser=True),
            "is_can_review": True,
            "is_can_execute": True,
            "is_can_cancel": True,
            "is_can_timingtask": True,
            "manual": True,
            "review_info": SimpleNamespace(nodes=[SimpleNamespace(is_auto_pass=True)]),
        }
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "detail.html",
                    context,
                    request=RequestFactory().get("/workflow/84/"),
                )
                if language == "en":
                    for text in [
                        "Approval workflow",
                        "No approval required",
                        "Workflow information",
                        "Unrestricted",
                        "Review passed",
                        "Workflow details",
                        "Expand all",
                        "Collapse all",
                        "Approve",
                        "Execute now",
                        "Schedule execution",
                        "Review / execution details",
                    ]:
                        self.assertIn(text, html)
                    self.assertIn("locale: 'en-US'", html)
                else:
                    for text in [
                        "审批流",
                        "无需审批",
                        "工单详情",
                        "审核通过",
                        "展开全部",
                    ]:
                        self.assertIn(text, html)
                    self.assertIn("locale: 'zh-CN'", html)
                self.assertIn("Original workflow", html)
                self.assertIn("原始SQL", html)
                self.assertIn('name="mode" value="auto"', html)
                self.assertIn("/api/v1/sql-workflows/84/execution/", html)
                self.assertIn("status === 'workflow_executing'", html)

    def test_sql_submission_translations_and_stable_fields(self):
        context = {
            "group_list": [SimpleNamespace(group_id=1, group_name="原始组名")],
            "engines": {},
            "enable_backup_switch": True,
        }
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "sqlsubmit.html",
                    context,
                    request=RequestFactory().get("/submitsql/"),
                )
                if language == "en":
                    for text in [
                        "SQL Deployment",
                        "Select a group",
                        "Search your groups",
                        "Choose whether to back up data",
                        "Check SQL",
                        "Confirm submission",
                        "SQL files up to 10 MB only",
                        "Warnings",
                        "Errors",
                    ]:
                        self.assertIn(text, html)
                    self.assertIn("language: 'en'", html)
                    self.assertIn("locale: 'en-US'", html)
                else:
                    self.assertIn("SQL上线", html)
                    self.assertIn("请选择组", html)
                    self.assertIn("language: 'zh'", html)
                self.assertIn('name="sql_content"', html)
                self.assertIn('name="workflow_name"', html)
                self.assertIn('value="原始组名"', html)
                self.assertIn('id="CheckWarningCount"', html)
                self.assertIn('id="CheckErrorCount"', html)

    def test_document_markdown_is_json_encoded(self):
        markdown = (
            '# "Quoted" heading\n</script><script>alert(1)</script>\nBackslash: \\'
        )
        html = render_to_string(
            "dbaprinciples.html",
            {"md": markdown},
            request=RequestFactory().get("/dbaprinciples/"),
        )
        payload = re.search(
            r'<script id="principles-markdown" type="application/json">(.*?)</script>',
            html,
            re.S,
        ).group(1)
        self.assertEqual(json.loads(payload), markdown)
        self.assertNotIn("</script>", payload)

    def test_query_page_translations_keep_data_and_audit_actions(self):
        context = {
            "favorites": [{"id": 7, "alias": "原始别名"}],
            "engines": {},
            "can_download": 1,
            "can_offline_download": 1,
            "storage_type": "local",
        }
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "sqlquery.html", context, request=RequestFactory().get("/sqlquery/")
                )
                if language == "en":
                    for text in [
                        "SQL Query",
                        "Saved queries",
                        "Favorites",
                        "Not favorited",
                        "Query history",
                        "Select an instance:",
                        "Select a database:",
                        "Select a schema:",
                        "View table structure",
                        "Format SQL",
                        "Explain",
                        "Copy as Markdown",
                        "Rows returned",
                        "Duration (seconds)",
                        "No matching results",
                    ]:
                        self.assertIn(text, html)
                    self.assertIn("locale: 'en-US'", html)
                else:
                    self.assertIn("查询历史", html)
                    self.assertIn("复制为Markdown", html)
                    self.assertIn("locale: 'zh-CN'", html)
                self.assertIn("原始别名", html)
                self.assertIn('value="true"', html)
                self.assertIn('value="false"', html)
                self.assertIn("action: '复制Markdown'", html)
                self.assertIn('action:"下载"', html)
                self.assertIn('name="copyMarkdown"', html)
                self.assertIn("data-query-result", html)
                self.assertNotIn("active_li_title.match(", html)
                self.assertNotIn("queryParams(e)", html)

    def test_export_submit_translates_controls_and_preserves_request_values(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "sqlexportsubmit.html",
                    {
                        "group_list": [
                            SimpleNamespace(group_id=1, group_name="原始组")
                        ],
                        "engines": {"mysql": SimpleNamespace(name="MySQL")},
                        "max_export_rows": 10000,
                    },
                    request=RequestFactory().get("/sqlexportsubmit/"),
                )
                expected = (
                    [
                        "Select an export format",
                        "Select an instance",
                        "Select a database",
                        "Validate export",
                        "Submit export",
                        "Validation succeeded",
                        "Counting rows...",
                        "{ActualRows}",
                        "{minutes}",
                        "June",
                        "language: 'en'",
                    ]
                    if language == "en"
                    else [
                        "请选择导出数据格式",
                        "导出校验",
                        "导出提交",
                        "校验成功",
                        "六月",
                        "language: 'zh'",
                    ]
                )
                for text in expected:
                    self.assertIn(text, html)
                for text in [
                    'value="csv"',
                    'value="xlsx"',
                    'value="sql"',
                    'value="json"',
                    'value="xml"',
                    "原始组",
                    "can_read",
                    "/sqlexport/pre_check/",
                    "is_offline_export: 1",
                    "countRow.affected_rows",
                    "values[key] ?? ''",
                ]:
                    self.assertIn(text, html)

    def test_export_list_translates_filters_columns_and_preserves_codes(self):
        context = {
            "status_list": [("workflow_abort", "原始状态缓存")],
            "instance": [SimpleNamespace(id=2, instance_name="原始实例")],
            "resource_group": [SimpleNamespace(group_id=1, group_name="原始组")],
            "storage_type": "local",
            "can_offline_download": 1,
        }
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "sqlexportworkflow.html",
                    context,
                    request=RequestFactory().get("/sqlexportworkflow/"),
                )
                expected = (
                    [
                        "Status",
                        "Submit export workflow",
                        "Workflow name",
                        "Target instance",
                        "Data export:",
                        "Activity log",
                        "June",
                        "en-US",
                    ]
                    if language == "en"
                    else ["提交导出工单", "目标实例", "数据导出:", "六月", "zh-CN"]
                )
                for text in expected:
                    self.assertIn(text, html)
                for text in [
                    'value="workflow_abort"',
                    "原始实例",
                    "原始组",
                    '"syntax_type":[3]',
                    "row.export_format",
                    "/api/v1/sql-workflows/list/",
                    "/logs/",
                ]:
                    self.assertIn(text, html)
                self.assertNotIn("原始状态缓存", html)
                self.assertNotIn("row.export_format =", html)
                self.assertNotIn("queryParams(e)", html)
        with override("en"):
            html = render_to_string(
                "sqlexportworkflow.html",
                {**context, "storage_type": ""},
                request=RequestFactory().get("/sqlexportworkflow/"),
            )
            self.assertNotIn('id="btn_exportsubmit"', html)

    def test_query_access_details_translate_status_actions_and_preserve_data(self):
        from datetime import datetime, date

        for language in ["en", "zh-hans"]:
            for status, label in [
                (0, "Pending review"),
                (1, "Approved"),
                (2, "Rejected"),
                (3, "Canceled"),
            ]:
                context = {
                    "workflow_detail": SimpleNamespace(
                        apply_id=7,
                        title="原始申请标题",
                        user_display="原始申请人",
                        instance=SimpleNamespace(instance_name="原始实例"),
                        priv_type=2,
                        get_priv_type_display=lambda: "TABLE",
                        db_list="原始数据库",
                        table_list="原始表",
                        limit_num=100,
                        valid_date=date(2026, 12, 31),
                        create_time=datetime(2026, 1, 1),
                        status=status,
                        group_name="原始组",
                    ),
                    "review_info": SimpleNamespace(
                        nodes=[SimpleNamespace(is_auto_pass=True)]
                    ),
                    "current_reviewers": [],
                    "last_operation_info": "原始审核备注",
                    "is_can_review": True,
                    "user": SimpleNamespace(username="reviewer"),
                }
                with self.subTest(language=language, status=status), override(language):
                    html = render_to_string(
                        "queryapplydetail.html",
                        context,
                        request=RequestFactory().get("/queryapplydetail/7/"),
                    )
                    for text in [
                        "原始申请标题",
                        "原始申请人",
                        "原始实例",
                        "原始数据库",
                        "原始表",
                        "原始审核备注",
                        "/workflow/log/",
                        "workflow_type: 1",
                        "field: 'operation_info'",
                    ]:
                        self.assertIn(text, html)
                    if language == "en":
                        for text in [
                            "Request title:",
                            "Request information",
                            "Activity log",
                            "Tables",
                            "Submitted",
                            "en-US",
                            label,
                        ]:
                            self.assertIn(text, html)
                    if status == 0:
                        for text in (
                            ["Approve", "Reject request", "Enter a review comment."]
                            if language == "en"
                            else ["审核通过", "终止流程", "请填写审核备注"]
                        ):
                            self.assertIn(text, html)
                        self.assertIn('name="audit_status" value="1"', html)
                        self.assertIn('name="audit_status" value="2"', html)
                    else:
                        self.assertNotIn('id="btnPass"', html)
                        self.assertNotIn('id="btnReject"', html)

    def test_query_permission_pages_translate_controls_and_keep_identifiers(self):
        context = {
            "engines": {},
            "group_list": [],
            "user": SimpleNamespace(is_superuser=True),
            "perms": SimpleNamespace(sql=SimpleNamespace(query_mgtpriv=True)),
            "user_list": [SimpleNamespace(user_display="原始显示名")],
        }
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                applications = render_to_string(
                    "queryapplylist.html",
                    context,
                    request=RequestFactory().get("/queryapplylist/"),
                )
                permissions = render_to_string(
                    "queryuserprivileges.html",
                    context,
                    request=RequestFactory().get("/queryuserprivileges/"),
                )
                for text in (
                    [
                        "Request access",
                        "Request database query access",
                        "One month",
                        "Pending review",
                        "en-US",
                    ]
                    if language == "en"
                    else ["权限申请", "一月", "待审核", "zh-CN"]
                ):
                    self.assertIn(text, applications)
                for text in (
                    [
                        "Bulk edit",
                        "Bulk revoke",
                        "Selected permissions: {count}",
                        "The row limit cannot exceed {max}.",
                        "Row limit",
                        "Expires on",
                        "en-US",
                    ]
                    if language == "en"
                    else ["批量变更", "批量删除权限", "结果集", "有效时间", "zh-CN"]
                ):
                    self.assertIn(text, permissions)
                for text in [
                    "原始显示名",
                    "privilege_ids",
                    'value="all"',
                    "modifyqueryprivileges(2)",
                    "batchModifyPrivileges(1)",
                ]:
                    self.assertIn(text, permissions)
                for html in [applications, permissions]:
                    self.assertNotIn("queryParams(e)", html)
                if language == "en":
                    self.assertNotIn("January", applications)
                    self.assertNotIn("All time", permissions)

    def test_dictionary_page_translates_controls_and_metadata_labels(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "data_dictionary.html",
                    {
                        "perms": SimpleNamespace(
                            sql=SimpleNamespace(data_dictionary_export=True)
                        )
                    },
                    request=RequestFactory().get("/data_dictionary/"),
                )
                expected = (
                    [
                        "Select an instance",
                        "Select a database",
                        "Object type",
                        "Tables",
                        "Views",
                        "Export",
                        "Object metadata",
                        "Column",
                        "Indexes",
                        "Create table SQL",
                        "en-US",
                    ]
                    if language == "en"
                    else ["请选择实例", "对象类型", "表元数据展示", "列信息", "zh-CN"]
                )
                for text in expected:
                    self.assertIn(text, html)
                for text in [
                    'value="table"',
                    'value="view"',
                    'id="showModal"',
                    'id="TABLE_NAME"',
                    '"title": column',
                    "/data_dictionary/table_info/",
                ]:
                    self.assertIn(text, html)

    def test_dictionary_export_translates_fixed_text_and_preserves_data(self):
        context = {
            "db_name": "原始数据库",
            "tables": [
                {
                    "TABLE_INFO": {"TABLE_NAME": "原始表", "TABLE_COMMENT": "原始注释"},
                    "ENGINE_KEYS": [{"key": "COLUMN_NAME", "value": "Column name"}],
                    "COLUMNS": [{"COLUMN_NAME": "原始列名"}],
                }
            ],
        }
        with override("en"):
            html = render_to_string("dictionaryexport.html", context)
            for text in [
                "Database schema documentation",
                "data dictionary (Tables: 1)",
                "Table name:",
                "Comment:",
                "原始数据库",
                "原始表",
                "原始注释",
                "原始列名",
            ]:
                self.assertIn(text, html)

    def test_parameter_comparison_page_translates_display_not_difference_codes(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "param_compare.html", request=RequestFactory().get("/paramcompare/")
                )
                expected = (
                    [
                        "Comparison options",
                        "Select a source instance:",
                        "Select a target instance:",
                        "Show differences only",
                        "Comparison results",
                        "Matching parameters",
                        "Different parameters",
                        "Source value",
                        "Target value",
                        "Different values",
                        "Source only",
                        "Target only",
                        "Match",
                        "en-US",
                    ]
                    if language == "en"
                    else [
                        "操作选项",
                        "仅显示差异项",
                        "对比结果",
                        "值不同",
                        "一致",
                        "zh-CN",
                    ]
                )
                for text in expected:
                    self.assertIn(text, html)
                for text in [
                    "row.diff_type === '值不同'",
                    "value === '仅源实例存在'",
                    "field: 'instance1_value'",
                    "field: 'instance2_value'",
                    "escapeHtml(result.instance1_name)",
                    "/param/compare/",
                ]:
                    self.assertIn(text, html)

    def test_parameter_page_translations_keep_names_values_and_routes(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "param.html", request=RequestFactory().get("/instanceparam/")
                )
                expected = (
                    [
                        "Editable parameters",
                        "Change history",
                        "Add parameter",
                        "Current value",
                        "Allowed values",
                        "Change parameter value",
                        "A parameter value is required.",
                        "Previous value",
                        "New value",
                        "Save",
                        "Cancel",
                        "en-US",
                    ]
                    if language == "en"
                    else [
                        "可修改参数",
                        "修改历史",
                        "修改参数值",
                        "参数值不能为空",
                        "zh-CN",
                    ]
                )
                for text in expected:
                    self.assertIn(text, html)
                for text in [
                    "field: 'variable_name'",
                    "field: 'runtime_value'",
                    "return row.description",
                    "/param/edit/",
                    "/param/history/",
                    'value="true"',
                ]:
                    self.assertIn(text, html)

    def test_parameter_template_labels_translate_per_request(self):
        from django.forms import modelform_factory
        from sql.models import ParamTemplate

        with override("en"):
            form = modelform_factory(
                ParamTemplate,
                fields=["variable_name", "default_value", "editable", "description"],
            )()
            for text in [
                "Parameter name",
                "Default value",
                "Allow changes",
                "Description",
            ]:
                self.assertIn(text, form.as_p())

    def test_account_page_translations_keep_security_controls_and_identifiers(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "instanceaccount.html",
                    request=RequestFactory().get("/instanceaccount/"),
                )
                expected = (
                    [
                        "Create account",
                        "Edit account details",
                        "Grant privileges",
                        "Change password",
                        "Lock account",
                        "Unlock account",
                        "Lock this account?",
                        "Unlock this account?",
                        "Confirm password",
                        "{0} selected",
                        "en-US",
                    ]
                    if language == "en"
                    else [
                        "创建账号",
                        "修改/录入账号",
                        "授权变更",
                        "确认锁定该账号？",
                        "zh-CN",
                    ]
                )
                for text in expected:
                    self.assertIn(text, html)
                for text in [
                    "user_host",
                    "db_name_user",
                    'id="password1"',
                    'id="edit-password"',
                    'name="SELECT"',
                    "is_locked === 'Y'",
                    "/instance/user/create/",
                    "/instance/user/edit/",
                ]:
                    self.assertIn(text, html)
                self.assertNotIn("queryParams(e)", html)
                self.assertNotIn("operation +", html)
                if language == "en":
                    self.assertNotIn("All time", html)

    def test_database_page_translations_keep_modal_fields_and_data(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "database.html",
                    {
                        "active_user": [
                            SimpleNamespace(username="preview", display="原始用户")
                        ]
                    },
                    request=RequestFactory().get("/database/"),
                )
                for text in (
                    [
                        "Select an instance",
                        "Recorded",
                        "Create database",
                        "Database name",
                        "Select a database owner",
                        "Edit database details",
                        "Collation",
                        "Granted accounts",
                        "Save",
                        "en-US",
                    ]
                    if language == "en"
                    else [
                        "已录入",
                        "创建数据库",
                        "编辑/录入数据库信息",
                        "保存",
                        "zh-CN",
                    ]
                ):
                    self.assertIn(text, html)
                for text in [
                    "原始用户(preview)",
                    'value="true"',
                    "field: 'owner_display'",
                    "field: 'grantees'",
                    "/instance/database/create/",
                    "/instance/database/edit/",
                    'id="edit_db_name"',
                    'readonly="readonly"',
                ]:
                    self.assertIn(text, html)
                self.assertNotIn("queryParams(e)", html)
                if language == "en":
                    self.assertNotIn("All time", html)

    def test_session_page_translations_keep_command_values_and_api_fields(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "dbdiagnostic.html", request=RequestFactory().get("/dbdiagnostic/")
                )
                for text in (
                    [
                        "Process status",
                        "Top table sizes",
                        "Transactions",
                        "Locks",
                        "Command type",
                        "Terminate sessions",
                        "Confirm termination",
                        "Free space (%)",
                        "Waiting thread ID",
                        "en-US",
                    ]
                    if language == "en"
                    else ["进程状态", "终止会话", "确定终止", "碎片率(%)", "zh-CN"]
                ):
                    self.assertIn(text, html)
                for text in [
                    "field: '等待事务线程ID'",
                    "key === '等待事务的sql'",
                    "ThreadIDs",
                    "command_types[i]",
                    "/db_diagnostic/create_kill_session/",
                    "/db_diagnostic/kill_session/",
                ]:
                    self.assertIn(text, html)
                self.assertNotIn("queryParams(e)", html)

    def test_session_script_catalog_translates_titles_without_changing_filters(self):
        source = (
            Path(__file__).resolve().parent / "static/dbdiagnostic/js/db_info.js"
        ).read_text()
        self.assertIn('["All", "Not Sleep", "Query"]', source)
        self.assertIn("field: 'info'", source)
        self.assertNotIn("THEEAD ID", source)
        request = RequestFactory().get("/jsi18n/")
        with override("en"):
            response = JavaScriptCatalog.as_view()(request)
            catalog = response.content.decode()
            for text in [
                "Full SQL text",
                "Client address",
                "Application name",
                "Estimated total rows",
            ]:
                self.assertIn(text, catalog)

    def test_instance_page_translations_preserve_data_and_routes(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "instance.html",
                    {
                        "engines": {},
                        "tags": [SimpleNamespace(id=7, tag_name="自定义标签")],
                    },
                    request=RequestFactory().get("/instance/"),
                )
                for text in (
                    [
                        "Instance type",
                        "Database type",
                        "Filter by tags",
                        "Add instance",
                        "Test connection",
                        "Clean up binlogs",
                        "en-US",
                    ]
                    if language == "en"
                    else ["实例类型", "数据库类型", "添加实例", "测试", "zh-CN"]
                ):
                    self.assertIn(text, html)
                for text in [
                    "自定义标签",
                    "/admin/sql/instance/add/",
                    "/instance/list/",
                    "instance_name",
                    "db_type",
                    'value="master"',
                    'value="slave"',
                ]:
                    self.assertIn(text, html)
                self.assertNotIn("queryParams(e)", html)

    def test_instance_editor_labels_follow_active_language(self):
        from django.forms import modelform_factory
        from sql.models import Instance, AliyunRdsConfig

        for language, expected in [
            (
                "en",
                [
                    "Instance name",
                    "Primary",
                    "Replica",
                    "Deployment mode",
                    "Standalone",
                    "Cluster",
                    "Verify server SSL certificate",
                    "Hidden databases take precedence",
                ],
            ),
            (
                "zh-hans",
                [
                    "实例名称",
                    "主库",
                    "从库",
                    "运行模式",
                    "单机",
                    "集群",
                    "是否验证服务端SSL证书",
                    "隐藏大于显示",
                ],
            ),
        ]:
            with self.subTest(language=language), override(language):
                form = modelform_factory(
                    Instance,
                    fields=[
                        "instance_name",
                        "type",
                        "mode",
                        "verify_ssl",
                        "denied_db_name_regex",
                    ],
                )()
                html = form.as_p()
                for text in expected:
                    self.assertIn(text, html)
                self.assertIn('value="master"', html)
                self.assertIn('value="cluster"', html)
                if language == "en":
                    self.assertEqual(
                        str(AliyunRdsConfig._meta.verbose_name),
                        "Alibaba Cloud RDS configuration",
                    )

    def test_slow_query_page_translations_preserve_fields(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "slowquery.html", request=RequestFactory().get("/slowquery/")
                )
                for text in (
                    [
                        "Slow query statistics",
                        "Slow query details",
                        "All databases",
                        "Total executions",
                        "Redis node",
                        "Full SQL statement",
                        "Execution time (95th percentile)",
                        "95th percentile time (µs)",
                        "en-US",
                    ]
                    if language == "en"
                    else ["慢日志统计", "慢日志明细", "全部数据库", "zh-CN"]
                ):
                    self.assertIn(text, html)
                for field in [
                    "SQLText",
                    "SQLId",
                    "MySQLTotalExecutionCounts",
                    "slowsqlinfo-list",
                ]:
                    self.assertIn(field, html)
                self.assertNotIn("queryParams(e)", html)

    def test_optimization_page_translations_keep_tool_options(self):
        for language in ["en", "zh-hans"]:
            with self.subTest(language=language), override(language):
                html = render_to_string(
                    "sqladvisor.html",
                    {"engines": {}},
                    request=RequestFactory().get("/sqladvisor/"),
                )
                if language == "en":
                    for text in [
                        "SQL Optimization Tools",
                        "Select an instance:",
                        "Select a database:",
                        "Select an optimization tool:",
                        "Show optimization details:",
                        "Format SQL",
                        "Explain",
                        "Get optimization advice",
                        "Optimization advice",
                        "Show table and index statistics",
                        "executes the SQL; choose carefully",
                        "Table statistics are unavailable.",
                    ]:
                        self.assertIn(text, html)
                    self.assertIn("locale: 'en-US'", html)
                else:
                    self.assertIn("SQL优化工具", html)
                    self.assertIn("获取优化建议", html)
                    self.assertIn("locale: 'zh-CN'", html)
                self.assertIn('value="1" selected="selected"', html)
                self.assertIn('value="0"', html)
                self.assertIn('id="sql_profile" type="checkbox" value=""', html)
                self.assertNotIn(
                    'id="sql_profile" type="checkbox" value="" checked', html
                )
                self.assertIn('"title": column', html)
                self.assertIn("/query/explain/", html)

    def test_get_does_not_change_preference(self):
        response = self.client.get("/i18n/setlang/?language=en")
        self.assertEqual(response.status_code, 405)
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)

    def test_external_redirect_is_rejected(self):
        response = self.switch("en", next="https://example.com/phishing")
        self.assertEqual(response.url, "/")

    def test_cookie_takes_precedence_over_browser_language(self):
        self.switch("zh-hans")
        response = self.client.get("/login/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(response.headers["Content-Language"], "zh-hans")

    def test_switch_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/i18n/setlang/", {"language": "en"})
        self.assertEqual(response.status_code, 403)
        page = client.get("/login/")
        self.assertContains(page, "csrfmiddlewaretoken")
        response = client.post(
            "/i18n/setlang/",
            {
                "language": "en",
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            },
        )
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "en")


class QueryPermissionMessageTests(SimpleTestCase):
    def test_invalid_privilege_ids_translate_without_mutation(self):
        from sql.query_privileges import query_priv_modify

        request = RequestFactory().post(
            "/query/modifyprivileges/", {"type": "2", "privilege_ids": "not-an-id"}
        )
        request.user = SimpleNamespace()
        with override("en"), patch(
            "sql.query_privileges.QueryPrivileges.objects.filter"
        ) as records:
            result = json.loads(query_priv_modify.__wrapped__(request).content)
            self.assertEqual(result["msg"], "Invalid privilege_ids format.")
            records.assert_not_called()


class DictionaryMetadataLanguageTests(SimpleTestCase):
    def test_only_known_display_headers_translate(self):
        from sql.data_dictionary import localize_dictionary_columns
        import copy

        original = {
            "meta_data": {"column_list": ["TABLE_NAME"], "rows": ["原始表"]},
            "desc": {
                "column_list": ["列名", "列类型", "原始扩展字段"],
                "rows": [["原始列名", "varchar(20)", "原始注释"]],
            },
            "index": {"column_list": ["索引名", "唯一性"], "rows": [["原始索引", 0]]},
            "create_sql": [
                ["原始表", "CREATE TABLE `原始表` (`原始列名` varchar(20))"]
            ],
        }
        with override("en"):
            translated = localize_dictionary_columns(copy.deepcopy(original))
            self.assertEqual(
                translated["desc"]["column_list"],
                ["Column name", "Column type", "原始扩展字段"],
            )
            self.assertEqual(
                translated["index"]["column_list"], ["Index name", "Uniqueness"]
            )
            for key in ["meta_data", "create_sql"]:
                self.assertEqual(translated[key], original[key])
            self.assertEqual(translated["desc"]["rows"], original["desc"]["rows"])
        with override("zh-hans"):
            self.assertEqual(
                localize_dictionary_columns(copy.deepcopy(original)), original
            )

    def test_dictionary_invalid_request_is_translated_before_engine_call(self):
        from sql.data_dictionary import table_info

        request = RequestFactory().get("/data_dictionary/table_info/")
        request.user = SimpleNamespace()
        with override("en"), patch("sql.data_dictionary.get_engine") as engine:
            response = json.loads(table_info.__wrapped__(request).content)
            self.assertEqual(response["msg"], "Invalid request.")
            engine.assert_not_called()


class ParameterComparisonLanguageTests(SimpleTestCase):
    def test_invalid_source_id_is_translated_without_engine_call(self):
        from sql.instance import param_compare

        request = RequestFactory().post(
            "/param/compare/", {"instance_id1": "bad", "instance_id2": "2"}
        )
        request.user = SimpleNamespace()
        with override("en"), patch("sql.instance.get_engine") as engine:
            response = json.loads(param_compare.__wrapped__(request).content)
            self.assertEqual(response["msg"], "Invalid source instance ID")
            engine.assert_not_called()

    def test_comparison_preserves_original_values_and_difference_codes(self):
        from sql.instance import param_compare
        from unittest.mock import MagicMock

        for diff_only in ["false", "true"]:
            request = RequestFactory().post(
                "/param/compare/",
                {"instance_id1": "1", "instance_id2": "2", "diff_only": diff_only},
            )
            request.user = SimpleNamespace()
            source, target = MagicMock(), MagicMock()
            source.get_variables.return_value = SimpleNamespace(
                error="",
                rows=[
                    ("same", "原始值"),
                    ("different", "中文A"),
                    ("source_only", "源值"),
                ],
            )
            target.get_variables.return_value = SimpleNamespace(
                error="",
                rows=[
                    ("same", "原始值"),
                    ("different", "中文B"),
                    ("target_only", "目标值"),
                ],
            )
            with self.subTest(diff_only=diff_only), override("en"), patch(
                "sql.instance.Instance.objects.get",
                side_effect=[
                    SimpleNamespace(db_type="mysql", instance_name="源实例"),
                    SimpleNamespace(db_type="mysql", instance_name="目标实例"),
                ],
            ), patch("sql.instance.get_engine", side_effect=[source, target]), patch(
                "sql.instance.ParamTemplate.objects.filter"
            ) as templates:
                templates.return_value.values.return_value = [
                    {
                        "variable_name": "different",
                        "default_value": "默认值",
                        "description": "原始描述",
                    }
                ]
                data = json.loads(param_compare.__wrapped__(request).content)["data"]
                self.assertEqual(
                    (data["same_count"], data["diff_count"], data["total"]), (1, 3, 4)
                )
                self.assertEqual(len(data["rows"]), 3 if diff_only == "true" else 4)
                row = next(
                    row for row in data["rows"] if row["variable_name"] == "different"
                )
                self.assertEqual(
                    (
                        row["instance1_value"],
                        row["instance2_value"],
                        row["description"],
                        row["diff_type"],
                    ),
                    ("中文A", "中文B", "原始描述", "值不同"),
                )
                self.assertEqual(data["instance1_name"], "源实例")


class ParameterMessageTests(SimpleTestCase):
    def test_same_parameter_value_translates_without_changing_runtime(self):
        from sql.instance import param_edit

        request = RequestFactory().post(
            "/param/edit/",
            {
                "instance_id": 2,
                "variable_name": "max_execution_time",
                "runtime_value": "0",
            },
        )
        request.user = SimpleNamespace()
        for language, expected in [
            ("en", "The value matches the current value. No changes were made."),
            ("zh-hans", "参数值与实际运行值一致，未调整！"),
        ]:
            with self.subTest(language=language), override(language), patch(
                "sql.instance.Instance.objects.get",
                return_value=SimpleNamespace(db_type="mysql"),
            ), patch("sql.instance.ParamTemplate.objects.filter"), patch(
                "sql.instance.ParamHistory.objects.create"
            ) as history, patch(
                "sql.instance.get_engine"
            ) as engine:
                engine.return_value.escape_string.side_effect = lambda value: value
                engine.return_value.get_variables.return_value.rows = [
                    ("max_execution_time", "0")
                ]
                response = json.loads(param_edit.__wrapped__(request).content)
                self.assertEqual(response["msg"], expected)
                engine.return_value.set_variable.assert_not_called()
                history.assert_not_called()


class AccountManagementMessageTests(SimpleTestCase):
    def test_account_creation_required_fields_translate_without_engine_call(self):
        from sql.instance_account import create

        request = RequestFactory().post("/instance/user/create/", {"instance_id": 2})
        request.user = SimpleNamespace()
        with override("en"), patch(
            "sql.instance_account.user_instances"
        ) as instances, patch("sql.instance_account.get_engine") as engine:
            instances.return_value.get.return_value = SimpleNamespace(db_type="mysql")
            result = json.loads(create.__wrapped__(request).content)
            self.assertEqual(
                result["msg"], "Complete the required fields before submitting."
            )
            engine.assert_not_called()

    def test_account_metadata_edit_without_password_keeps_stored_password(self):
        from sql.instance_account import edit

        request = RequestFactory().post(
            "/instance/user/edit/",
            {
                "instance_id": 2,
                "user": "原始账号",
                "host": "%",
                "password": "",
                "remark": "原始备注",
            },
        )
        request.user = SimpleNamespace()
        with override("en"), patch(
            "sql.instance_account.user_instances"
        ) as instances, patch(
            "sql.instance_account.InstanceAccount.objects.update_or_create"
        ) as save, patch(
            "sql.instance_account.get_engine"
        ) as engine:
            instances.return_value.get.return_value = SimpleNamespace(db_type="mysql")
            result = json.loads(edit.__wrapped__(request).content)
            self.assertEqual(result["status"], 0)
            self.assertEqual(save.call_args.kwargs["defaults"], {"remark": "原始备注"})
            self.assertEqual(save.call_args.kwargs["user"], "原始账号")
            engine.assert_not_called()


class DatabaseManagementMessageTests(SimpleTestCase):
    def test_missing_database_name_is_translated_without_engine_call(self):
        from sql.instance_database import create, edit

        for view in [create, edit]:
            request = RequestFactory().post("/instance/database/", {"db_name": ""})
            request.user = SimpleNamespace()
            with self.subTest(view=view.__name__), override("en"), patch(
                "sql.instance_database.get_engine"
            ) as engine:
                result = json.loads(view.__wrapped__(request).content)
                self.assertEqual(result["status"], 1)
                self.assertEqual(
                    result["msg"], "Complete the required fields before submitting."
                )
                engine.assert_not_called()

    def test_metadata_edit_keeps_user_values_without_target_database_write(self):
        from sql.instance_database import edit

        request = RequestFactory().post(
            "/instance/database/edit/",
            {
                "instance_id": 2,
                "db_name": "原始数据库",
                "owner": "preview",
                "remark": "原始备注",
            },
        )
        request.user = SimpleNamespace()
        with override("en"), patch("sql.instance_database.user_instances"), patch(
            "sql.instance_database.Users.objects.get",
            return_value=SimpleNamespace(display="原始用户"),
        ), patch(
            "sql.instance_database.InstanceDatabase.objects.update_or_create"
        ) as save, patch(
            "sql.instance_database.get_engine"
        ) as engine:
            result = json.loads(edit.__wrapped__(request).content)
            self.assertEqual(result["status"], 0)
            self.assertEqual(save.call_args.kwargs["db_name"], "原始数据库")
            self.assertEqual(save.call_args.kwargs["defaults"]["remark"], "原始备注")
            engine.assert_not_called()


class SessionDiagnosticMessageTests(SimpleTestCase):
    def test_process_response_keeps_sql_and_filter_values(self):
        from sql.db_diagnostic import process

        for command in ["All", "Not Sleep", "Query"]:
            request = RequestFactory().post(
                "/db_diagnostic/process/",
                {"instance_name": "Preview", "command_type": command},
            )
            request.user = SimpleNamespace()
            rows = [{"info": "SELECT '原始中文'", "command": "Query"}]
            with override("en"), patch("sql.db_diagnostic.user_instances"), patch(
                "sql.db_diagnostic.get_engine"
            ) as engine:
                engine.return_value.processlist.return_value = SimpleNamespace(
                    error="", to_dict=lambda: rows
                )
                response = json.loads(process.__wrapped__(request).content)
                self.assertEqual(response["rows"], rows)
                self.assertEqual(
                    engine.return_value.processlist.call_args.kwargs["command_type"],
                    command,
                )

    def test_unsupported_session_termination_message_without_killing(self):
        from sql.db_diagnostic import kill_session

        request = RequestFactory().post(
            "/db_diagnostic/kill_session/",
            {"instance_name": "Preview", "ThreadIDs": "[1]"},
        )
        request.user = SimpleNamespace()
        with override("en"), patch(
            "sql.db_diagnostic.user_instances"
        ) as instances, patch("sql.db_diagnostic.get_engine") as engine:
            instances.return_value.get.return_value = SimpleNamespace(db_type="redis")
            response = json.loads(kill_session.__wrapped__(request).content)
            self.assertEqual(
                response["msg"], "Terminating sessions is not supported for redis."
            )
            engine.return_value.kill.assert_not_called()


class InstanceConnectionMessageTests(SimpleTestCase):
    def test_connection_error_translates_prefix_and_keeps_driver_detail(self):
        from common.check import instance

        request = RequestFactory().post("/check/instance/", {"instance_id": 1})
        request.user = SimpleNamespace(is_superuser=True)
        for language, prefix in [
            ("en", "Unable to connect to the instance."),
            ("zh-hans", "无法连接实例"),
        ]:
            with self.subTest(language=language), override(language), patch(
                "common.check.Instance.objects.get"
            ), patch("common.check.get_engine") as engine:
                engine.return_value.test_connection.return_value.error = (
                    "原始 driver error"
                )
                data = json.loads(instance(request).content)
                self.assertEqual(data["status"], 1)
                self.assertTrue(data["msg"].startswith(prefix))
                self.assertIn("原始 driver error", data["msg"])


class AuthenticationTranslationTests(SimpleTestCase):
    def test_invalid_credentials_in_both_languages(self):
        from common.auth import authenticate_entry, Users

        request = RequestFactory().post(
            "/authenticate/", {"username": "missing", "password": "invalid"}
        )
        for language, expected in [
            ("en", "Incorrect username or password. Please try again."),
            ("zh-hans", "用户名或密码错误，请重新输入！"),
        ]:
            with self.subTest(language=language), override(language), patch(
                "common.auth.Users.objects.get", side_effect=Users.DoesNotExist
            ), patch("common.auth.ArcheryAuth.challenge", return_value=None):
                response = authenticate_entry(request)
                self.assertEqual(json.loads(response.content)["msg"], expected)

    def test_locked_account_message_interpolates_duration(self):
        import datetime
        from common.auth import ArcheryAuth

        request = RequestFactory().post(
            "/authenticate/", {"username": "locked", "password": "invalid"}
        )
        user = SimpleNamespace(
            failed_login_count=5, last_login_failed_at=datetime.datetime.now()
        )
        with override("en"), patch(
            "common.auth.Users.objects.get", return_value=user
        ), patch("common.auth.SysConfig.get", side_effect=lambda key, default: default):
            result = ArcheryAuth(request).authenticate()
            self.assertEqual(result["status"], 3)
            self.assertIn("300 seconds", result["msg"])

    def test_registration_validation_is_translated(self):
        from common.auth import sign_up

        with override("en"), patch("common.auth.SysConfig.get", return_value=True):
            response = sign_up(RequestFactory().post("/signup/", {}))
            self.assertEqual(
                json.loads(response.content)["msg"],
                "Username and password are required.",
            )


class WorkflowLogTranslationTests(SimpleTestCase):
    def test_log_labels_follow_language_and_preserve_details(self):
        import datetime
        from sql_api.api_workflow_operations import WorkflowLogView

        view = WorkflowLogView()
        request = SimpleNamespace(user=SimpleNamespace())
        for language, expected in [("en", "Submitted"), ("zh-hans", "提交")]:
            rows = [
                {
                    "operation_type_desc": label,
                    "operation_info": "保留原始日志",
                    "operator_display": "User",
                    "operation_time": datetime.datetime(2026, 1, 1),
                }
                for label in ["提交", "自定义操作"]
            ]
            with self.subTest(language=language), override(language), patch.object(
                view,
                "get_audit_workflow",
                return_value=(SimpleNamespace(), SimpleNamespace(id=1)),
            ), patch(
                "sql_api.api_workflow_operations.ensure_log_viewable"
            ) as permission_check, patch(
                "sql_api.api_workflow_operations.WorkflowLog.objects.filter"
            ) as query:
                query.return_value.order_by.return_value.values.return_value = rows
                response = view.get(request, 1)
                permission_check.assert_called_once_with(request.user, 1)
                self.assertEqual(
                    response.data["rows"][0]["operation_type_desc"], expected
                )
                self.assertEqual(
                    response.data["rows"][1]["operation_type_desc"], "自定义操作"
                )
                self.assertEqual(
                    response.data["rows"][0]["operation_info"], "保留原始日志"
                )


class DocumentationLanguageTests(SimpleTestCase):
    def test_english_document_and_custom_document_fallback(self):
        from tempfile import TemporaryDirectory
        from sql.views import dbaprinciples

        with TemporaryDirectory() as directory:
            docs = Path(directory) / "docs"
            docs.mkdir()
            (docs / "docs.md").write_text("中文自定义规范", encoding="utf-8")
            english = docs / "docs.en.md"
            english.write_text("English guidelines", encoding="utf-8")
            for language, expected in [
                ("en", "English guidelines"),
                ("zh-hans", "中文自定义规范"),
            ]:
                with override_settings(BASE_DIR=directory), override(language), patch(
                    "sql.views.render"
                ) as render:
                    dbaprinciples.__wrapped__(RequestFactory().get("/dbaprinciples/"))
                    self.assertEqual(render.call_args.args[2]["md"], expected)
            english.unlink()
            with override_settings(BASE_DIR=directory), override("en"), patch(
                "sql.views.render"
            ) as render:
                dbaprinciples.__wrapped__(RequestFactory().get("/dbaprinciples/"))
                self.assertEqual(render.call_args.args[2]["md"], "中文自定义规范")


class OptimizationMessageTests(SimpleTestCase):
    def test_missing_tool_configuration_is_translated(self):
        from sql.sql_optimize import optimize_sqladvisor

        request = RequestFactory().post(
            "/slowquery/optimize_sqladvisor/",
            {
                "instance_name": "Preview",
                "db_name": "preview",
                "sql_content": "SELECT 1",
            },
        )
        request.user = SimpleNamespace()
        for language, expected in [
            ("en", "Configure the SQLAdvisor executable path."),
            ("zh-hans", "请配置SQLAdvisor路径！"),
        ]:
            with self.subTest(language=language), override(language), patch(
                "sql.sql_optimize.user_instances"
            ), patch("sql.sql_optimize.SysConfig.get", return_value=None):
                response = optimize_sqladvisor.__wrapped__(request)
                self.assertEqual(json.loads(response.content)["msg"], expected)

    def test_explain_rejects_non_explain_without_calling_engine(self):
        from sql.sql_optimize import explain

        request = RequestFactory().post(
            "/query/explain/",
            {
                "instance_name": "Preview",
                "db_name": "preview",
                "sql_content": "SELECT 1",
            },
        )
        request.user = SimpleNamespace()
        with override("en"), patch("sql.sql_optimize.user_instances"), patch(
            "sql.sql_optimize.get_engine"
        ) as engine:
            response = explain(request)
            self.assertEqual(
                json.loads(response.content)["msg"],
                "Only statements beginning with EXPLAIN are supported.",
            )
            engine.assert_not_called()


class SQLAdvisorReportTests(SimpleTestCase):
    def test_advisor_response_keeps_original_report(self):
        from sql.sql_optimize import optimize_sqladvisor

        report = "[Note] 第1步: SQLAdvisor结束!\n"
        request = RequestFactory().post(
            "/slowquery/optimize_sqladvisor/",
            {
                "instance_name": "Preview",
                "db_name": "preview",
                "sql_content": "SELECT 1",
            },
        )
        request.user = SimpleNamespace()
        with override("en"), patch("sql.sql_optimize.user_instances"), patch(
            "sql.sql_optimize.SysConfig.get", return_value="/tool"
        ), patch("sql.sql_optimize.SQLAdvisor") as advisor:
            advisor.return_value.check_args.return_value = {"status": 0}
            advisor.return_value.execute_cmd.return_value.communicate.return_value = (
                report,
                "",
            )
            data = json.loads(optimize_sqladvisor.__wrapped__(request).content)
            self.assertEqual(data["raw_report"], report)
            self.assertIn("Step 1: SQLAdvisor finished", data["data"])

    def test_report_translation_preserves_sql_and_original_language(self):
        from sql.utils.sqladvisor_report import localize_sqladvisor_report

        original = "[Note] 第1步: 对SQL解析优化之后得到的SQL:select '原始SQL' from `表名`\n[Note] 第2步：表表名 的SQL太逆天,没有优化建议\n[Note] unknown report 原文\n"
        with override("en"):
            translated = localize_sqladvisor_report(original)
            self.assertIn(
                "SQL after parsing and optimization: select '原始SQL' from `表名`",
                translated,
            )
            self.assertIn("No optimization advice for table 表名", translated)
            self.assertIn("unknown report 原文", translated)
        with override("zh-hans"):
            self.assertEqual(localize_sqladvisor_report(original), original)


class RemainingPromptLanguageTests(SimpleTestCase):
    def test_validation_prompts_do_not_reach_external_services(self):
        from sql.query import generate_sql
        from sql.resource_group import auditors

        for language, expected_query, expected_group in [
            ("en", "query_desc or db_type is missing", "Invalid parameters"),
            ("zh-hans", "query_desc or db_type不存在", "参数错误"),
        ]:
            with override(language), patch(
                "sql.query.Instance.objects.get"
            ) as lookup, patch("sql.query.OpenaiClient") as ai:
                response = generate_sql.__wrapped__(
                    RequestFactory().post("/generate_sql/", {})
                )
                self.assertEqual(json.loads(response.content)["msg"], expected_query)
                lookup.assert_not_called()
                ai.assert_not_called()
                response = auditors(
                    RequestFactory().post("/auditors/", {"workflow_type": "2"})
                )
                self.assertEqual(json.loads(response.content)["msg"], expected_group)

    def test_invalid_dashboard_date_is_a_translated_json_error(self):
        from common.dashboard import DashboardApi

        for language, expected in [("en", "Invalid date"), ("zh-hans", "日期有误")]:
            with override(language), patch("common.dashboard.get_chart_data") as charts:
                response = DashboardApi.__wrapped__(
                    RequestFactory().get(
                        "/dashboardapi/",
                        {"start_date": "invalid", "end_date": "invalid"},
                    )
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(json.loads(response.content), {"error": expected})
                charts.assert_not_called()

    def test_shared_prompts_and_twofactor_catalog(self):
        for language, expected in [
            ("en", "Retry in %s seconds"),
            ("zh-hans", "%s 秒后重试"),
        ]:
            with override(language):
                response = JavaScriptCatalog.as_view(packages=["sql"])(
                    RequestFactory().get("/jsi18n/")
                )
                if language == "en":
                    self.assertContains(response, expected)
                else:
                    self.assertNotContains(response, "Retry in %s seconds")
                html = render_to_string("2fa.html", {"verify_mode": "verify_config"})
                self.assertLess(html.index("/jsi18n/"), html.index("dist/js/utils."))


class QueryServiceLanguageTests(SimpleTestCase):
    def test_resource_denial_translates_without_engine_access(self):
        from sql.services import resource_service as service

        for language, expected in [
            ("en", "Instance does not exist or access is denied"),
            ("zh-hans", "实例不存在或无权限"),
        ]:
            with override(language), patch.object(service, "get_engine") as engine:
                result = service.list_instance_resources(SimpleNamespace(), "database")
                self.assertEqual(result, {"status": 1, "msg": expected, "data": []})
                engine.assert_not_called()

    def test_query_validation_and_favorite_denial_do_not_write(self):
        from sql.services import sqlquery_service, querylog_service

        for language, limit_msg, log_msg in [
            ("en", "Invalid limit_num", "Query log does not exist or access is denied"),
            ("zh-hans", "limit_num 非法", "查询记录不存在或无权限"),
        ]:
            with override(language), patch.object(
                sqlquery_service, "get_engine"
            ) as engine, patch.object(
                sqlquery_service, "user_instances"
            ) as instances, patch.object(
                querylog_service.QueryLog.objects, "filter"
            ) as logs:
                result = sqlquery_service.execute_sql_query(
                    SimpleNamespace(), None, None, None, "invalid"
                )
                self.assertEqual(result["msg"], limit_msg)
                self.assertEqual(result["status"], 1)
                instances.assert_not_called()
                engine.assert_not_called()
                logs.return_value.exists.return_value = False
                result = querylog_service.update_favorite(
                    SimpleNamespace(is_superuser=True), -1, True, ""
                )
                self.assertEqual(result["msg"], log_msg)
                logs.return_value.update.assert_not_called()

    def test_permission_messages_preserve_database_and_table_names(self):
        from sql import query_privileges as privileges

        user = SimpleNamespace(has_perm=lambda permission: False)
        instance = SimpleNamespace(db_type="mysql")
        for language in ["en", "zh-hans"]:
            with override(language), patch.object(
                privileges,
                "_table_ref",
                return_value=[{"schema": "原始库", "name": "原始表"}],
            ), patch.object(privileges, "_db_priv", return_value=False), patch.object(
                privileges, "_tb_priv", return_value=False
            ):
                result = privileges.query_priv_check(
                    user, instance, "原始库", "unused", 5
                )
                self.assertEqual(result["status"], 2)
                self.assertIn("原始库.原始表", result["msg"])
                self.assertIn(
                    "query access to table" if language == "en" else "表的查询权限",
                    result["msg"],
                )

    def test_resource_serializer_validation_is_bilingual(self):
        from sql_api.serializers import SqlQueryResourceQuerySerializer

        for language, expected in [
            ("en", "Provide either instance_id or instance_name"),
            ("zh-hans", "instance_id 或 instance_name 必须提供一个"),
        ]:
            with override(language):
                serializer = SqlQueryResourceQuerySerializer(
                    data={"resource_type": "database"}
                )
                self.assertFalse(serializer.is_valid())
                self.assertEqual(
                    str(serializer.errors["non_field_errors"][0]), expected
                )


class ApiFormLanguageTests(SimpleTestCase):
    def test_labels_follow_request_language_without_changing_choice_codes(self):
        from sql_api.serializers import TwoFASerializer, InstanceResourceSerializer

        auth = TwoFASerializer()
        resource = InstanceResourceSerializer()
        for language, username, instance in [
            ("en", "Username", "Instance ID"),
            ("zh-hans", "用户名", "实例id"),
        ]:
            with override(language):
                self.assertEqual(str(auth.fields["engineer"].label), username)
                self.assertEqual(str(resource.fields["instance_id"].label), instance)
                self.assertEqual(
                    list(auth.fields["auth_type"].choices), ["totp", "sms"]
                )
                self.assertEqual(list(auth.fields["enable"].choices), ["true", "false"])

    def test_missing_resource_validation_does_not_open_engine(self):
        from sql_api import serializers as api

        for language, expected in [
            ("en", "Instance does not exist"),
            ("zh-hans", "不存在该实例"),
        ]:
            with override(language), patch.object(
                api.Instance.objects, "get", side_effect=api.Instance.DoesNotExist
            ), patch.object(api, "get_engine") as engine:
                serializer = api.InstanceResourceSerializer(
                    data={"instance_id": -1, "resource_type": "database"}
                )
                self.assertFalse(serializer.is_valid())
                self.assertEqual(str(serializer.errors["errors"][0]), expected)
                engine.assert_not_called()

    def test_execution_validation_stops_before_user_or_workflow_lookup(self):
        from sql_api import serializers as api

        for language, expected in [
            ("en", "mode is required"),
            ("zh-hans", "缺少 mode"),
        ]:
            with override(language), patch.object(
                api.Users.objects, "get"
            ) as users, patch.object(api.WorkflowAudit.objects, "get") as audits:
                serializer = api.ExecuteWorkflowSerializer(
                    data={"workflow_id": 1, "workflow_type": 2}
                )
                self.assertFalse(serializer.is_valid())
                self.assertEqual(str(serializer.errors["errors"][0]), expected)
                users.assert_not_called()
                audits.assert_not_called()

    def test_dynamic_resource_error_preserves_id(self):
        from sql_api import serializers as api

        for language, expected in [
            ("en", "Instance does not exist: -12"),
            ("zh-hans", "不存在该实例：-12"),
        ]:
            with override(language), patch.object(
                api.Instance.objects, "get", side_effect=api.Instance.DoesNotExist
            ):
                serializer = api.ExecuteCheckSerializer(
                    data={
                        "instance_id": -12,
                        "db_name": "fixture",
                        "full_sql": "unused",
                    }
                )
                self.assertFalse(serializer.is_valid())
                self.assertEqual(
                    str(serializer.errors["instance_id"]["errors"]), expected
                )


class ApiDocumentationLanguageTests(SimpleTestCase):
    def test_schema_translates_without_calling_endpoints(self):
        from drf_spectacular.generators import SchemaGenerator
        from sql_api.api_instance import InstanceResource
        from sql_api.api_user import UserAuth
        from sql_api.api_workflow import ExecuteWorkflow

        routes = [
            path("resource/", InstanceResource.as_view()),
            path("auth/", UserAuth.as_view()),
            path("execute/", ExecuteWorkflow.as_view()),
        ]
        for language, resource, auth, execute in [
            ("en", "Instance resources", "Verify user credentials", "Execute workflow"),
            ("zh-hans", "实例资源", "用户认证校验", "执行工单"),
        ]:
            with override(language), patch(
                "sql_api.api_instance.get_engine"
            ) as engine, patch("sql_api.api_workflow.async_task") as task, patch(
                "sql_api.api_user.authenticate"
            ) as authenticate:
                schema = SchemaGenerator(patterns=routes).get_schema(public=True)
                self.assertEqual(
                    str(schema["paths"]["/resource/"]["post"]["summary"]), resource
                )
                self.assertEqual(
                    str(schema["paths"]["/auth/"]["post"]["summary"]), auth
                )
                self.assertEqual(
                    str(schema["paths"]["/execute/"]["post"]["summary"]), execute
                )
                props = schema["components"]["schemas"]["InstanceResource"][
                    "properties"
                ]
                self.assertEqual(
                    str(props["db_name"]["title"]),
                    "Database name" if language == "en" else "数据库名",
                )
                self.assertEqual(set(schema["paths"]["/resource/"]), {"post"})
                engine.assert_not_called()
                task.assert_not_called()
                authenticate.assert_not_called()

    def test_execution_denial_translates_and_does_not_queue_tasks(self):
        from sql_api import api_workflow as api
        from rest_framework.exceptions import ValidationError

        request = SimpleNamespace(
            data={
                "workflow_type": 2,
                "workflow_id": 1,
                "mode": "auto",
                "engineer": "fixture",
            }
        )
        for language in ["en", "zh-hans"]:
            for permitted, english, chinese in [
                (
                    False,
                    "You do not have permission to execute this workflow",
                    "你无权执行当前工单！",
                ),
                (
                    True,
                    "Outside the execution window. Submit the workflow again to change the execution window",
                    "不在可执行时间范围内，如果需要修改执行时间请重新提交工单!",
                ),
            ]:
                with override(language), patch.object(
                    api, "ExecuteWorkflowSerializer"
                ) as serializer, patch.object(
                    api.Users.objects,
                    "get",
                    return_value=SimpleNamespace(has_perm=lambda code: permitted),
                ), patch.object(
                    api, "can_execute", return_value=True
                ), patch.object(
                    api, "on_correct_time_period", return_value=False
                ), patch.object(
                    api, "get_engine"
                ) as engine, patch.object(
                    api, "async_task"
                ) as task:
                    serializer.return_value.is_valid.return_value = True
                    with self.assertRaises(ValidationError) as error:
                        api.ExecuteWorkflow().post(request)
                    self.assertEqual(
                        str(error.exception.detail["errors"]),
                        english if language == "en" else chinese,
                    )
                    engine.assert_not_called()
                    task.assert_not_called()


class WorkflowOperationPromptLanguageTests(SimpleTestCase):
    def test_missing_workflow_is_translated_without_engine_calls(self):
        from sql_api import api_workflow_operations as api
        from rest_framework.exceptions import NotFound

        for language, expected in [
            ("en", "Request does not exist."),
            ("zh-hans", "工单不存在"),
        ]:
            with override(language), patch.object(
                api.WorkflowAudit.objects,
                "get",
                side_effect=api.WorkflowAudit.DoesNotExist,
            ), patch.object(api, "get_engine") as engine:
                with self.assertRaises(NotFound) as error:
                    api.get_sql_workflow_by_audit_id(-1)
                self.assertEqual(str(error.exception.detail), expected)
                engine.assert_not_called()

    def test_view_permission_denial_is_translated(self):
        from sql_api import api_workflow_operations as api
        from rest_framework.exceptions import PermissionDenied

        for language, expected in [
            ("en", "You do not have permission to view this workflow"),
            ("zh-hans", "你无权查看当前工单！"),
        ]:
            with override(language), patch.object(api, "can_view", return_value=False):
                with self.assertRaises(PermissionDenied) as error:
                    api.ensure_viewable(SimpleNamespace(), 1)
                self.assertEqual(str(error.exception.detail), expected)

    def test_past_schedule_rejected_without_saving_or_queuing(self):
        from sql_api import api_workflow_operations as api
        from rest_framework.exceptions import ValidationError
        import datetime
        from unittest.mock import Mock

        for language, expected in [
            ("en", "The scheduled time cannot be in the past"),
            ("zh-hans", "时间不能小于当前时间"),
        ]:
            workflow = Mock(id=1)
            with override(language), patch.object(
                api.WorkflowScheduleView,
                "validated_data",
                return_value={
                    "run_date": api.timezone.now() - datetime.timedelta(days=1)
                },
            ), patch.object(
                api.WorkflowScheduleView,
                "get_audit_workflow",
                return_value=(None, workflow),
            ), patch.object(
                api, "add_sql_schedule"
            ) as schedule, patch.object(
                api, "async_task"
            ) as task:
                with self.assertRaises(ValidationError) as error:
                    api.WorkflowScheduleView().post(SimpleNamespace(), 1)
                self.assertEqual(str(error.exception.detail["run_date"]), expected)
                workflow.save.assert_not_called()
                schedule.assert_not_called()
                task.assert_not_called()

    def test_shared_permission_denial_does_not_call_protected_view(self):
        from common.utils.permission import superuser_required, role_required
        from unittest.mock import Mock

        for language, expected in [
            ("en", "Permission denied. Contact an administrator"),
            ("zh-hans", "您无权操作，请联系管理员"),
        ]:
            for decorator in [superuser_required, role_required(("admin",))]:
                request = RequestFactory().get(
                    "/", HTTP_X_REQUESTED_WITH="XMLHttpRequest"
                )
                request.user = SimpleNamespace(is_superuser=False, role="none")
                protected = Mock()
                with override(language):
                    response = decorator(protected)(request)
                self.assertEqual(
                    json.loads(response.content),
                    {"status": 1, "msg": expected, "data": []},
                )
                protected.assert_not_called()


class ConfigurationCheckPromptLanguageTests(SimpleTestCase):
    def test_email_preconditions_do_not_send_messages(self):
        from common import check

        for language, disabled, port in [
            (
                "en",
                "Enable email notifications first",
                "The port must be a positive integer",
            ),
            ("zh-hans", "请先开启邮件通知！", "端口号只能为正整数"),
        ]:
            with override(language), patch.object(check, "MsgSender") as sender:
                for payload, expected in [
                    ({}, disabled),
                    ({"mail": "true", "mail_smtp_port": "invalid"}, port),
                ]:
                    request = RequestFactory().post("/check/email/", payload)
                    request.user = SimpleNamespace(is_superuser=True)
                    self.assertEqual(
                        json.loads(check.email(request).content)["msg"], expected
                    )
                sender.assert_not_called()

    def test_invalid_storage_json_does_not_connect(self):
        from common import check

        for language, expected in [
            ("en", "Invalid custom parameters. Enter valid JSON"),
            ("zh-hans", "自定义参数格式错误，请输入有效的JSON格式"),
        ]:
            request = RequestFactory().post(
                "/check/file_storage_connect/",
                {"storage_type": "sftp", "sftp_custom_params": "{"},
            )
            request.user = SimpleNamespace(is_superuser=True)
            with override(language), patch.object(check, "DynamicStorage") as storage:
                self.assertEqual(
                    json.loads(check.file_storage_connect(request).content)["msg"],
                    expected,
                )
                storage.assert_not_called()

    def test_sms_throttle_and_expiry_without_sending_or_cache_writes(self):
        from common.twofa import sms

        for language, retry, expired in [
            (
                "en",
                "Too many verification code requests. Retry in 50 seconds",
                "No verification code was requested, or the code has expired",
            ),
            (
                "zh-hans",
                "获取验证码太频繁，请于50秒后再试",
                "未获取验证码或验证码已过期！",
            ),
        ]:
            with override(language), patch.object(
                sms, "SysConfig"
            ) as config, patch.object(
                sms, "get_redis_connection"
            ) as redis, patch.object(
                sms.time, "time", return_value=110
            ):
                config.return_value.get.return_value = "disabled"
                authenticator = sms.SMS()
                redis.return_value.get.return_value = b'{"update_time":100}'
                self.assertEqual(
                    authenticator.get_captcha(phone="fixture")["msg"], retry
                )
                redis.return_value.get.return_value = None
                self.assertEqual(
                    authenticator.verify("unused", phone="fixture")["msg"], expired
                )
                redis.return_value.set.assert_not_called()
                self.assertIsNone(authenticator.client)

    def test_totp_error_uses_language_without_real_keys(self):
        from common.twofa import totp

        for language, expected in [
            ("en", "Incorrect verification code"),
            ("zh-hans", "验证码不正确！"),
        ]:
            with override(language), patch.object(totp.pyotp, "TOTP") as verifier:
                verifier.return_value.verify.return_value = False
                self.assertEqual(
                    totp.TOTP().verify("unused", key="mock-only")["msg"], expected
                )


class LocatorAndStorageLanguageTests(SimpleTestCase):
    def test_invalid_table_name_does_not_look_up_instances(self):
        from sql_api import api_instance as api

        for language, expected in [
            ("en", "Invalid table_name:"),
            ("zh-hans", "参数table_name错误:"),
        ]:
            with override(language), patch.object(
                api, "user_instances"
            ) as instances, patch.object(api, "resolve_table_instances") as lookup:
                result = api.TableInstanceLookup().post(SimpleNamespace(data={})).data
                self.assertEqual(result["status"], 1)
                self.assertEqual(result["count"], 0)
                self.assertEqual(result["data"], [])
                self.assertIn(expected, result["msg"])
                instances.assert_not_called()
                lookup.assert_not_called()

    def test_storage_messages_use_mock_connections_and_preserve_errors(self):
        from sql.storage import DynamicStorage
        from unittest.mock import MagicMock

        for language in ["en", "zh-hans"]:
            for kind, method, success in [
                ("sftp", "_check_sftp_connection", "SFTP connection successful"),
                ("s3c", "_check_s3c_connection", "S3 storage connection successful"),
                (
                    "azure",
                    "_check_azure_connection",
                    "Azure Blob storage connection successful",
                ),
            ]:
                adapter = DynamicStorage.__new__(DynamicStorage)
                adapter.storage_type = kind
                adapter.storage = MagicMock()
                with override(language):
                    ok, message = getattr(adapter, method)()
                    self.assertTrue(ok)
                    if language == "en":
                        self.assertEqual(message, success)
                    if kind == "sftp":
                        adapter.storage.__enter__.side_effect = RuntimeError("原始错误")
                    elif kind == "s3c":
                        adapter.storage.connection.meta.client.head_bucket.side_effect = RuntimeError(
                            "原始错误"
                        )
                    else:
                        adapter.storage.client.get_container_properties.side_effect = (
                            RuntimeError("原始错误")
                        )
                    ok, message = getattr(adapter, method)()
                    self.assertFalse(ok)
                    self.assertIn("原始错误", message)
                    self.assertIn("failed" if language == "en" else "失败", message)

    def test_unsupported_storage_type_is_translated_without_initializing_backend(self):
        from sql.storage import DynamicStorage

        adapter = DynamicStorage.__new__(DynamicStorage)
        adapter.storage_type = "fixture-unsupported"
        for language, expected in [
            ("en", "Unsupported storage type: fixture-unsupported"),
            ("zh-hans", "不支持的存储类型: fixture-unsupported"),
        ]:
            with override(language):
                self.assertEqual(adapter.check_connection(), (False, expected))


class AdminNavigationLanguageTests(SimpleTestCase):
    def test_workflow_and_masking_rule_names_in_rendered_navigation(self):
        from django.contrib import admin

        request = RequestFactory().get("/admin/sql/datamaskingcolumns/add/")
        request.user = SimpleNamespace(
            is_active=True,
            is_staff=True,
            is_superuser=True,
            has_perm=lambda *args: True,
            has_module_perms=lambda *args: True,
        )
        for language, workflow, masking in [
            ("en", "SQL workflows", "Masking rule configuration"),
            ("zh-hans", "SQL工单", "脱敏规则配置"),
            ("en", "SQL workflows", "Masking rule configuration"),
        ]:
            with override(language):
                app_list = admin.site.get_app_list(request, app_label="sql")
                names = {
                    model["object_name"]: str(model["name"])
                    for app in app_list
                    for model in app["models"]
                }
                self.assertEqual(names["SqlWorkflow"], workflow)
                self.assertEqual(names["DataMaskingRules"], masking)
                html = render_to_string(
                    "admin/app_list.html",
                    {"app_list": app_list, "show_changelinks": True},
                )
                self.assertIn(workflow, html)
                self.assertIn(masking, html)
                if language == "en":
                    self.assertNotIn("SQL工单", html)
                    self.assertNotIn("脱敏规则配置", html)


class EngineQueryCheckLanguageTests(SimpleTestCase):
    def test_rejected_query_messages_do_not_execute_sql(self):
        from sql.engines.mysql import MysqlEngine
        from sql.engines.pgsql import PgSQLEngine
        from sql.engines.redis import RedisEngine
        from unittest.mock import Mock

        for language in ["en", "zh-hans"]:
            for engine_type, statement, english, chinese in [
                (
                    MysqlEngine,
                    "SHOW GRANTS",
                    "You do not have permission to view this table",
                    "您无权查看该表",
                ),
                (
                    PgSQLEngine,
                    "UPDATE fixture SET id=1",
                    "This query syntax is not supported.",
                    "不支持的查询语法类型!",
                ),
                (
                    RedisEngine,
                    "FLUSHALL",
                    "This command is not allowed",
                    "禁止执行该命令！",
                ),
            ]:
                engine = engine_type.__new__(engine_type)
                engine.query = Mock()
                with override(language):
                    result = engine.query_check(db_name="fixture", sql=statement)
                self.assertTrue(result["bad_query"])
                self.assertEqual(
                    result["msg"], english if language == "en" else chinese
                )
                engine.query.assert_not_called()

    def test_postgres_star_warning_preserves_sql(self):
        from sql.engines.pgsql import PgSQLEngine

        statement = 'SELECT * FROM "原始表"'
        for language in ["en", "zh-hans"]:
            with override(language):
                result = PgSQLEngine.__new__(PgSQLEngine).query_check(sql=statement)
                self.assertEqual(result["filtered_sql"], statement)
                self.assertTrue(result["has_star"])
                self.assertFalse(result["bad_query"])
                self.assertEqual(
                    result["msg"],
                    (
                        "The SQL statement contains * "
                        if language == "en"
                        else "SQL语句中含有 * "
                    ),
                )


class AdditionalEngineQueryCheckLanguageTests(SimpleTestCase):
    def test_mssql_oracle_and_clickhouse_reject_without_querying(self):
        from sql.engines.mssql import MssqlEngine
        from sql.engines.oracle import OracleEngine
        from sql.engines.clickhouse import ClickHouseEngine
        from unittest.mock import Mock, PropertyMock

        cases = [
            (
                MssqlEngine,
                "UPDATE fixture SET id=1",
                "Only select,sp_helptext syntax is supported",
                "仅支持select,sp_helptext语法!",
            ),
            (
                MssqlEngine,
                "SET SHOWPLAN_ALL ON",
                "No valid SQL statement found in the execution plan request",
                "执行计划查询中未找到有效的SQL语句",
            ),
            (
                OracleEngine,
                "UPDATE fixture SET id=1",
                "Unsupported syntax",
                "不支持语法!",
            ),
            (
                ClickHouseEngine,
                "EXPLAIN SELECT 1",
                "This ClickHouse instance is older than 20.6.3 and does not support EXPLAIN",
                "当前ClickHouse实例版本低于20.6.3，不支持explain!",
            ),
        ]
        for language in ["en", "zh-hans"]:
            for engine_type, statement, english, chinese in cases:
                engine = engine_type.__new__(engine_type)
                engine.query = Mock()
                with override(language), patch.object(
                    ClickHouseEngine,
                    "server_version",
                    new_callable=PropertyMock,
                    return_value=(20, 1, 0),
                ):
                    result = engine.query_check(sql=statement)
                self.assertTrue(result["bad_query"])
                self.assertEqual(
                    result["msg"], english if language == "en" else chinese
                )
                engine.query.assert_not_called()

    def test_star_warning_preserves_sql_for_mssql_and_oracle(self):
        from sql.engines.mssql import MssqlEngine
        from sql.engines.oracle import OracleEngine

        statement = "SELECT * FROM fixture"
        for language in ["en", "zh-hans"]:
            for engine_type in [MssqlEngine, OracleEngine]:
                with override(language):
                    result = engine_type.__new__(engine_type).query_check(sql=statement)
                self.assertEqual(result["filtered_sql"], statement)
                self.assertTrue(result["has_star"])
                self.assertEqual(
                    result["msg"],
                    (
                        "The * keyword is not allowed\n"
                        if language == "en"
                        else "禁止使用 * 关键词\n"
                    ),
                )


class TemplateDisplayTextTests(SimpleTestCase):
    def test_parser_ignores_script_style_and_comments(self):
        html = "<SCRIPT>hidden</SCRIPT ><STYLE>hidden</STYLE ><!-- hidden --><h1>Visible &amp; text</h1>"
        self.assertEqual(display_text(html), "Visible & text")


class ApiValidationGuardLanguageTests(SimpleTestCase):
    def test_twofactor_missing_inputs_do_not_save_configuration(self):
        from sql_api import serializers as api
        from sql.models import TwoFactorAuthConfig
        from rest_framework.exceptions import ValidationError

        cases = [
            (
                api.TwoFASerializer,
                {"engineer": "fixture", "enable": "true", "auth_type": "sms"},
                "phone",
            ),
            (
                api.TwoFASaveSerializer,
                {"engineer": "fixture", "auth_type": "sms"},
                "phone",
            ),
            (
                api.TwoFASaveSerializer,
                {"engineer": "fixture", "auth_type": "totp"},
                "key",
            ),
            (
                api.TwoFAVerifySerializer,
                {"engineer": "fixture", "auth_type": "sms", "otp": 1},
                "phone",
            ),
        ]
        for language in ["en", "zh-hans"]:
            for serializer, attrs, field in cases:
                with override(language), patch.object(
                    api.Users.objects, "get", return_value=SimpleNamespace()
                ), patch.object(TwoFactorAuthConfig.objects, "create") as save:
                    with self.assertRaises(ValidationError) as error:
                        serializer().validate(attrs)
                    self.assertEqual(
                        str(error.exception.detail["errors"]),
                        f"{field} is required" if language == "en" else f"缺少 {field}",
                    )
                    save.assert_not_called()

    def test_missing_users_in_auth_and_audit_validation_preserve_identifiers(self):
        from sql_api import serializers as api
        from rest_framework.exceptions import ValidationError

        for language in ["en", "zh-hans"]:
            with override(language), patch.object(
                api.Users.objects, "get", side_effect=api.Users.DoesNotExist
            ), patch.object(api.WorkflowAudit.objects, "get") as audits:
                for serializer, attrs in [
                    (api.TwoFASerializer, {"engineer": "原始用户"}),
                    (api.TwoFAStateSerializer, {"engineer": "原始用户"}),
                    (
                        api.TwoFASaveSerializer,
                        {"engineer": "原始用户", "auth_type": "disabled"},
                    ),
                    (
                        api.TwoFAVerifySerializer,
                        {"engineer": "原始用户", "auth_type": "totp"},
                    ),
                    (api.AuditWorkflowSerializer, {"engineer": "原始用户"}),
                    (
                        api.ExecuteWorkflowSerializer,
                        {"engineer": "原始用户", "workflow_type": 2, "mode": "auto"},
                    ),
                ]:
                    with self.assertRaises(ValidationError) as error:
                        serializer().validate(attrs)
                    message = str(error.exception.detail["errors"])
                    self.assertIn(
                        "User does not exist" if language == "en" else "不存在", message
                    )
                with self.assertRaises(ValidationError) as error:
                    api.WorkflowAuditSerializer().validate_engineer("原始用户")
                self.assertIn("原始用户", str(error.exception.detail["errors"]))
                audits.assert_not_called()

    def test_missing_workflows_in_validators_do_not_create_records(self):
        from sql_api import serializers as api
        from rest_framework.exceptions import ValidationError

        for language in ["en", "zh-hans"]:
            with override(language), patch.object(
                api.Users.objects, "get", return_value=SimpleNamespace()
            ), patch.object(
                api.WorkflowAudit.objects,
                "get",
                side_effect=api.WorkflowAudit.DoesNotExist,
            ), patch.object(
                api.WorkflowAudit.objects, "create"
            ) as create:
                for serializer in [
                    api.AuditWorkflowSerializer,
                    api.WorkflowLogSerializer,
                    api.ExecuteWorkflowSerializer,
                ]:
                    with self.assertRaises(ValidationError) as error:
                        serializer().validate(
                            {
                                "engineer": "fixture",
                                "workflow_id": -1,
                                "workflow_type": 3,
                            }
                        )
                    self.assertEqual(
                        str(error.exception.detail["errors"]),
                        (
                            "Workflow does not exist"
                            if language == "en"
                            else "不存在该工单"
                        ),
                    )
                create.assert_not_called()


class WorkflowGuardCoverageTests(SimpleTestCase):
    def test_operation_permission_guards_do_not_save_or_queue(self):
        from sql_api import api_workflow_operations as api
        from rest_framework.exceptions import PermissionDenied
        from unittest.mock import Mock

        user = SimpleNamespace(
            username="fixture", is_superuser=False, has_perm=lambda code: False
        )
        request = SimpleNamespace(user=user)
        workflow = Mock(id=1, engineer="another-user")
        cases = [
            (api.WorkflowRollbackView, "get"),
            (api.WorkflowExecutionWindowView, "post"),
            (api.WorkflowApprovalView, "post"),
            (api.WorkflowRejectionView, "post"),
            (api.WorkflowExecutionView, "post"),
            (api.WorkflowTerminationView, "post"),
        ]
        for language in ["en", "zh-hans"]:
            for view, method in cases:
                with override(language), patch.object(
                    api.WorkflowOperationAPIView, "validated_data", return_value={}
                ), patch.object(
                    api.WorkflowOperationAPIView,
                    "get_audit_workflow",
                    return_value=(Mock(), workflow),
                ), patch.object(
                    api, "can_rollback", return_value=False
                ), patch.object(
                    api, "can_cancel", return_value=False
                ), patch.object(
                    api, "get_engine"
                ) as engine, patch.object(
                    api, "async_task"
                ) as task:
                    with self.assertRaises(PermissionDenied) as error:
                        getattr(view(), method)(request, 1)
                    self.assertIn(
                        "permission" if language == "en" else "无权",
                        str(error.exception.detail),
                    )
                    engine.assert_not_called()
                    task.assert_not_called()
                    workflow.save.assert_not_called()
            with override(language), self.assertRaises(PermissionDenied):
                api.WorkflowAuditListView().post(request)
            with override(language), self.assertRaises(PermissionDenied):
                api.ensure_workflow_executable(user, workflow)

    def test_auditor_failures_preserve_error_without_saving_or_notifying(self):
        from sql_api import api_workflow_operations as api
        from rest_framework.exceptions import ValidationError
        from unittest.mock import Mock
        from contextlib import nullcontext

        request = SimpleNamespace(
            user=SimpleNamespace(username="fixture", has_perm=lambda code: True)
        )
        workflow = Mock(id=1, engineer="fixture", status="workflow_manreviewing")
        for language in ["en", "zh-hans"]:
            for view, field in [
                (api.WorkflowApprovalView, "audit_remark"),
                (api.WorkflowRejectionView, "reject_remark"),
                (api.WorkflowTerminationView, "cancel_remark"),
            ]:
                auditor = Mock()
                auditor.operate.side_effect = api.AuditException("原始错误")
                with override(language), patch.object(
                    api.WorkflowOperationAPIView,
                    "validated_data",
                    return_value={field: "fixture"},
                ), patch.object(
                    api.WorkflowOperationAPIView,
                    "get_audit_workflow",
                    return_value=(Mock(), workflow),
                ), patch.object(
                    api, "can_cancel", return_value=True
                ), patch.object(
                    api, "SysConfig"
                ), patch.object(
                    api.transaction, "atomic", return_value=nullcontext()
                ), patch.object(
                    api, "get_auditor", return_value=auditor
                ), patch.object(
                    api, "async_task"
                ) as task:
                    with self.assertRaises(ValidationError) as error:
                        view().post(request, 1)
                    self.assertIn("原始错误", str(error.exception.detail))
                    self.assertIn(
                        "failed" if language == "en" else "失败",
                        str(error.exception.detail),
                    )
                    workflow.save.assert_not_called()
                    task.assert_not_called()

    def test_rollback_read_error_is_translated_with_empty_rows(self):
        from sql_api import api_workflow_operations as api
        from unittest.mock import Mock

        for language, expected in [
            ("en", "Failed to retrieve rollback SQL"),
            ("zh-hans", "获取回滚语句失败"),
        ]:
            with override(language), patch.object(
                api.WorkflowOperationAPIView,
                "get_audit_workflow",
                return_value=(Mock(), Mock(id=1)),
            ), patch.object(api, "can_rollback", return_value=True), patch.object(
                api, "get_engine"
            ) as engine, patch.object(
                api, "logger"
            ):
                engine.return_value.get_rollback.side_effect = RuntimeError("fixture")
                result = (
                    api.WorkflowRollbackView().get(SimpleNamespace(user=Mock()), 1).data
                )
                self.assertEqual(result, {"status": 1, "msg": expected, "rows": []})


class InstanceManagementGuardLanguageTests(SimpleTestCase):
    def test_missing_instances_block_account_database_and_diagnostic_operations(self):
        from sql import instance_account, instance_database, db_diagnostic

        cases = [
            (
                instance_account,
                ["users", "create", "edit", "grant", "reset_pwd", "lock", "delete"],
            ),
            (instance_database, ["databases", "create", "edit"]),
            (
                db_diagnostic,
                [
                    "process",
                    "create_kill_session",
                    "kill_session",
                    "tablespace",
                    "trxandlocks",
                    "innodb_trx",
                ],
            ),
        ]
        for language in ["en", "zh-hans"]:
            for module, names in cases:
                for name in names:
                    request = RequestFactory().post(
                        "/",
                        {
                            "instance_id": -1,
                            "instance_name": "fixture",
                            "db_name": "fixture",
                            "user_host": "fixture",
                            "ThreadIDs": "[]",
                        },
                    )
                    request.user = SimpleNamespace()
                    with override(language), patch.object(
                        module, "user_instances"
                    ) as instances, patch.object(module, "get_engine") as engine:
                        instances.return_value.get.side_effect = (
                            module.Instance.DoesNotExist
                        )
                        result = json.loads(
                            getattr(module, name).__wrapped__(request).content
                        )
                        self.assertEqual(result["status"], 1)
                        self.assertIn(
                            "not associated" if language == "en" else "未关联",
                            result["msg"],
                        )
                        engine.assert_not_called()

    def test_password_and_privilege_validation_do_not_change_accounts(self):
        from sql import instance_account as api

        for language in ["en", "zh-hans"]:
            for name, payload in [
                (
                    "create",
                    {
                        "user": "fixture",
                        "host": "localhost",
                        "password1": "mock-one",
                        "password2": "mock-two",
                    },
                ),
                (
                    "reset_pwd",
                    {
                        "user": "fixture",
                        "host": "localhost",
                        "reset_pwd1": "mock-one",
                        "reset_pwd2": "mock-two",
                    },
                ),
                ("grant", {"privs": "{"}),
            ]:
                request = RequestFactory().post("/", payload)
                request.user = SimpleNamespace()
                with override(language), patch.object(
                    api, "user_instances"
                ) as instances, patch.object(api, "get_engine") as engine:
                    instances.return_value.get.return_value = SimpleNamespace(
                        db_type="mysql"
                    )
                    result = json.loads(getattr(api, name).__wrapped__(request).content)
                    self.assertEqual(result["status"], 1)
                    if name == "grant":
                        self.assertIn(
                            "Invalid" if language == "en" else "不合法", result["msg"]
                        )
                        engine.return_value.execute.assert_not_called()
                    else:
                        self.assertIn(
                            "match" if language == "en" else "不一致", result["msg"]
                        )
                        engine.assert_not_called()

    def test_connection_check_failures_preserve_external_error_text(self):
        from common import check
        from unittest.mock import MagicMock

        for language in ["en", "zh-hans"]:
            request = RequestFactory().post(
                "/",
                {"go_inception_port": "3306", "inception_remote_backup_port": "3306"},
            )
            request.user = SimpleNamespace(is_superuser=True)
            for backup in [False, True]:
                connection = MagicMock()
                outcomes = (
                    [connection, RuntimeError("原始错误")]
                    if backup
                    else [RuntimeError("原始错误")]
                )
                with override(language), patch.object(
                    check.MySQLdb, "connect", side_effect=outcomes
                ), patch.object(check, "logger"):
                    result = json.loads(check.go_inception(request).content)
                    self.assertEqual(result["status"], 1)
                    self.assertIn("原始错误", result["msg"])
                    self.assertIn(
                        "Unable to connect" if language == "en" else "无法连接",
                        result["msg"],
                    )
                    if backup:
                        connection.close.assert_called_once()
            with override(language), patch.object(
                check, "DynamicStorage"
            ) as storage, patch.object(check.logging, "error"):
                storage.return_value.check_connection.return_value = (False, "fixture")
                result = json.loads(check.file_storage_connect(request).content)
                self.assertIn("failed" if language == "en" else "失败", result["msg"])
                storage.side_effect = RuntimeError("fixture")
                result = json.loads(check.file_storage_connect(request).content)
                self.assertIn("error" if language == "en" else "异常", result["msg"])


class OptimizationGuardCoverageTests(SimpleTestCase):
    def test_validation_failures_do_not_query_engines_or_start_tools(self):
        from sql import sql_optimize as api

        funcs = [
            api.optimize_sqladvisor,
            api.optimize_soar,
            api.optimize_sqltuning,
            api.explain,
            api.optimize_sqltuningadvisor,
        ]
        full = {
            "instance_name": "fixture",
            "db_name": "fixture",
            "sql_content": "SELECT 1",
            "sql": "SELECT 1",
            "sqltext": "SELECT 1",
        }
        for language in ["en", "zh-hans"]:
            for func in funcs:
                request = RequestFactory().post("/", full)
                request.user = SimpleNamespace()
                with override(language), patch.object(
                    api, "user_instances"
                ) as instances, patch.object(api, "get_engine") as engine, patch.object(
                    api, "SQLAdvisor"
                ) as advisor, patch.object(
                    api, "Soar"
                ) as soar, patch.object(
                    api, "SqlTuning"
                ) as tuning:
                    instances.return_value.get.side_effect = api.Instance.DoesNotExist
                    result = json.loads(
                        getattr(func, "__wrapped__", func)(request).content
                    )
                    self.assertEqual(result["status"], 1)
                    if language == "en":
                        self.assertIsNone(re.search(r"[\u4e00-\u9fff]", result["msg"]))
                    else:
                        self.assertIsNotNone(
                            re.search(r"[\u4e00-\u9fff]", result["msg"])
                        )
                    engine.assert_not_called()
                    advisor.assert_not_called()
                    soar.assert_not_called()
                    tuning.assert_not_called()
            for func in [api.explain, api.optimize_sqltuningadvisor]:
                for payload in [{}, dict(full, sql_content="")]:
                    request = RequestFactory().post("/", payload)
                    request.user = SimpleNamespace()
                    with override(language), patch.object(
                        api, "user_instances"
                    ) as instances, patch.object(api, "get_engine") as engine:
                        instances.return_value.get.return_value = SimpleNamespace(
                            db_type="mysql"
                        )
                        result = json.loads(
                            getattr(func, "__wrapped__", func)(request).content
                        )
                        self.assertEqual(result["status"], 1)
                        engine.assert_not_called()
            request = RequestFactory().post("/", full)
            request.user = SimpleNamespace()
            with override(language), patch.object(
                api, "user_instances"
            ) as instances, patch.object(api, "get_engine") as engine:
                instances.return_value.get.return_value = SimpleNamespace(
                    db_type="mysql"
                )
                result = json.loads(
                    getattr(
                        api.optimize_sqltuningadvisor,
                        "__wrapped__",
                        api.optimize_sqltuningadvisor,
                    )(request).content
                )
                self.assertEqual(result["status"], 1)
                self.assertIn("Oracle" if language == "en" else "oracle", result["msg"])
                engine.assert_not_called()


class AdminFilterCoverageTests(SimpleTestCase):
    def test_workflow_status_filter_and_form_keep_stable_codes(self):
        from sql.admin import SqlWorkflowStatusFilter, SqlWorkflowAdmin
        from sql.models import SqlWorkflow
        from django.contrib import admin

        source = {
            "display": "旧的显示名",
            "query_string": "?status__exact=workflow_finish",
            "selected": True,
        }
        status_filter = SqlWorkflowStatusFilter.__new__(SqlWorkflowStatusFilter)
        status_filter.field = SimpleNamespace(
            flatchoices=[("workflow_finish", "旧的显示名")]
        )
        request = RequestFactory().get("/admin/sql/sqlworkflow/")
        for language, expected in [
            ("en", "Workflow finished"),
            ("zh-hans", "已正常结束"),
        ]:
            with override(language), patch.object(
                admin.ChoicesFieldListFilter, "choices", return_value=iter([source])
            ):
                choices = list(status_filter.choices(None))
                self.assertEqual(choices[0]["display"], expected)
                self.assertEqual(choices[0]["query_string"], source["query_string"])
                self.assertTrue(choices[0]["selected"])
                model_admin = SqlWorkflowAdmin(SqlWorkflow, admin.site)
                self.assertEqual(
                    model_admin.workflow_status(
                        SimpleNamespace(status="workflow_finish")
                    ),
                    expected,
                )
                field = model_admin.formfield_for_choice_field(
                    SqlWorkflow._meta.get_field("status"), request
                )
                self.assertEqual(str(dict(field.choices)["workflow_finish"]), expected)
                self.assertIn("workflow_finish", dict(field.choices))

    def test_log_operation_filter_translates_label_only(self):
        from sql.admin import WorkflowLogOperationFilter
        from django.contrib import admin

        source = {
            "display": "提交",
            "query_string": "?operation_type_desc=submit",
            "selected": False,
        }
        log_filter = WorkflowLogOperationFilter.__new__(WorkflowLogOperationFilter)
        for language in ["en", "zh-hans"]:
            with override(language), patch.object(
                admin.AllValuesFieldListFilter, "choices", return_value=iter([source])
            ):
                result = list(log_filter.choices(None))[0]
                self.assertEqual(result["query_string"], source["query_string"])
                self.assertEqual(result["selected"], False)
                if language == "en":
                    self.assertNotEqual(str(result["display"]), "提交")
                else:
                    self.assertEqual(str(result["display"]), "提交")


class RemainingValidationCoverageTests(SimpleTestCase):
    def test_resource_and_execution_required_fields_fail_before_lookup(self):
        from sql_api import serializers as api
        from rest_framework.exceptions import ValidationError

        for language in ["en", "zh-hans"]:
            with override(language), patch.object(api.Users.objects, "get") as users:
                for kind in ["table", "schema", "column"]:
                    with self.assertRaises(ValidationError) as error:
                        api.SqlQueryResourceQuerySerializer().validate(
                            {"instance_id": 1, "resource_type": kind}
                        )
                    self.assertIn("db_name", str(error.exception.detail))
                with self.assertRaises(ValidationError) as error:
                    api.ExecuteWorkflowSerializer().validate(
                        {"workflow_type": 2, "mode": "auto"}
                    )
                self.assertIn("engineer", str(error.exception.detail))
                users.assert_not_called()
            with override(language), patch.object(
                api.ResourceGroup.objects,
                "get",
                side_effect=api.ResourceGroup.DoesNotExist,
            ):
                with self.assertRaises(ValidationError) as error:
                    api.WorkflowSerializer.validate_group_id(-123)
                self.assertIn("-123", str(error.exception.detail))

    def test_sms_without_provider_or_with_wrong_code_never_sends(self):
        from common.twofa import sms

        for language in ["en", "zh-hans"]:
            with override(language), patch.object(
                sms, "SysConfig"
            ) as config, patch.object(
                sms, "get_redis_connection"
            ) as redis, patch.object(
                sms.time, "time", return_value=110
            ):
                config.return_value.get.return_value = "disabled"
                authenticator = sms.SMS()
                for cached in [None, b'{"update_time":0}']:
                    redis.return_value.get.return_value = cached
                    result = authenticator.get_captcha(phone="fixture")
                    self.assertEqual(result["status"], 1)
                    self.assertIn("SMS" if language == "en" else "短信", result["msg"])
                redis.return_value.get.return_value = b'{"otp":"fixture"}'
                result = authenticator.verify("wrong", phone="fixture")
                self.assertEqual(result["status"], 1)
                self.assertIn(
                    "Incorrect" if language == "en" else "不正确", result["msg"]
                )
                self.assertIsNone(authenticator.client)
                redis.return_value.set.assert_not_called()

    def test_storage_invalid_row_limit_does_not_initialize_storage(self):
        from common import check

        for language in ["en", "zh-hans"]:
            request = RequestFactory().post("/", {"max_export_rows": "invalid"})
            request.user = SimpleNamespace(is_superuser=True)
            with override(language), patch.object(check, "DynamicStorage") as storage:
                result = json.loads(check.file_storage_connect(request).content)
                self.assertEqual(result["status"], 1)
                self.assertIn("max_export_rows", result["msg"])
                storage.assert_not_called()

    def test_twofactor_setup_requires_matching_verified_session(self):
        from sql_api import api_user as api

        payload = {"engineer": "fixture", "enable": "true", "auth_type": "totp"}
        for language in ["en", "zh-hans"]:
            for session in [{}, {"user": "another-user"}]:
                request = SimpleNamespace(
                    data=payload,
                    user=SimpleNamespace(is_authenticated=False),
                    session=session,
                )
                with override(language), patch.object(
                    api.Users.objects, "get", return_value=SimpleNamespace()
                ), patch.object(api, "get_authenticator") as authenticator:
                    result = api.TwoFA().post(request).data
                    self.assertEqual(result["status"], 1)
                    self.assertTrue(result["msg"])
                    if language == "en":
                        self.assertIsNone(re.search(r"[\u4e00-\u9fff]", result["msg"]))
                    else:
                        self.assertIsNotNone(
                            re.search(r"[\u4e00-\u9fff]", result["msg"])
                        )
                    authenticator.assert_not_called()
