# -*- coding: UTF-8 -*-

from django.urls import path
from django.views.i18n import JavaScriptCatalog

import sql.instance_database
import sql.query_privileges
import sql.sql_optimize
from common import auth, config, workflow, dashboard, check
from common.twofa import totp
from sql import views, sql_workflow, sql_analyze, query, slowlog, instance, instance_account, db_diagnostic, \
    resource_group, binlog, data_dictionary, archiver, audit_log, user
from sql.utils import tasks
from common.utils import ding_api

urlpatterns = [
    path('', views.index),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    path('index/', views.index),
    path('login/', views.login, name='login'),
    path('login/2fa/', views.twofa, name='twofa'),
    path('logout/', auth.sign_out),
    path('signup/', auth.sign_up),
    path('sqlworkflow/', views.sqlworkflow),
    path('submitsql/', views.submit_sql),
    path('editsql/', views.submit_sql),
    path('submitotherinstance/', views.submit_sql),
    path('detail/<int:workflow_id>/', views.detail, name='detail'),
    path('autoreview/', sql_workflow.submit),
    path('passed/', sql_workflow.passed),
    path('execute/', sql_workflow.execute),
    path('timingtask/', sql_workflow.timing_task),
    path('alter_run_date/', sql_workflow.alter_run_date),
    path('cancel/', sql_workflow.cancel),
    path('rollback/', views.rollback),
    path('sqlanalyze/', views.sqlanalyze),
    path('sqlquery/', views.sqlquery),
    path('slowquery/', views.slowquery),
    path('sqladvisor/', views.sqladvisor),
    path('slowquery_advisor/', views.sqladvisor),
    path('queryapplylist/', views.queryapplylist),
    path('queryapplydetail/<int:apply_id>/', views.queryapplydetail, name='queryapplydetail'),
    path('queryuserprivileges/', views.queryuserprivileges),
    path('dbdiagnostic/', views.dbdiagnostic),
    path('workflow/', views.workflows),
    path('workflow/<int:audit_id>/', views.workflowsdetail),
    path('dbaprinciples/', views.dbaprinciples),
    path('dashboard/', dashboard.pyecharts),
    path('group/', views.group),
    path('grouprelations/<int:group_id>/', views.groupmgmt),
    path('instance/', views.instance),
    path('instanceaccount/', views.instanceaccount),
    path('database/', views.database),
    path('instanceparam/', views.instance_param),
    path('binlog2sql/', views.binlog2sql),
    path('my2sql/', views.my2sql),
    path('schemasync/', views.schemasync),
    path('archive/', views.archive),
    path('archive/<int:id>/', views.archive_detail, name='archive_detail'),
    path('config/', views.config),
    path('audit/', views.audit),
    path('audit_sqlquery/', views.audit_sqlquery),
    path('audit_sqlworkflow/', views.audit_sqlworkflow),

    path('authenticate/', auth.authenticate_entry),
    path('sqlworkflow_list/', sql_workflow.sql_workflow_list),
    path('sqlworkflow_list_audit/', sql_workflow.sql_workflow_list_audit),
    path('sqlworkflow/detail_content/', sql_workflow.detail_content),
    path('sqlworkflow/backup_sql/', sql_workflow.backup_sql),
    path('simplecheck/', sql_workflow.check),
    path('getWorkflowStatus/', sql_workflow.get_workflow_status),
    path('del_sqlcronjob/', tasks.del_schedule),
    path('inception/osc_control/', sql_workflow.osc_control),

    path('sql_analyze/generate/', sql_analyze.generate),
    path('sql_analyze/analyze/', sql_analyze.analyze),

    path('workflow/list/', workflow.lists),
    path('workflow/log/', workflow.log),
    path('config/change/', config.change_config),

    path('check/inception/', check.inception),
    path('check/go_inception/', check.go_inception),
    path('check/email/', check.email),
    path('check/instance/', check.instance),

    path('group/group/', resource_group.group),
    path('group/addrelation/', resource_group.addrelation),
    path('group/relations/', resource_group.associated_objects),
    path('group/instances/', resource_group.instances),
    path('group/unassociated/', resource_group.unassociated_objects),
    path('group/auditors/', resource_group.auditors),
    path('group/changeauditors/', resource_group.changeauditors),
    path('group/user_all_instances/', resource_group.user_all_instances),

    path('instance/list/', instance.lists),

    path('instance/user/list', instance_account.users),
    path('instance/user/create/', instance_account.create),
    path('instance/user/edit/', instance_account.edit),
    path('instance/user/grant/', instance_account.grant),
    path('instance/user/reset_pwd/', instance_account.reset_pwd),
    path('instance/user/lock/', instance_account.lock),
    path('instance/user/delete/', instance_account.delete),

    path('instance/database/list/', sql.instance_database.databases),
    path('instance/database/create/', sql.instance_database.create),
    path('instance/database/edit/', sql.instance_database.edit),

    path('instance/schemasync/', instance.schemasync),
    path('instance/instance_resource/', instance.instance_resource),
    path('instance/describetable/', instance.describe),

    path('data_dictionary/', views.data_dictionary),
    path('data_dictionary/table_list/', data_dictionary.table_list),
    path('data_dictionary/table_info/', data_dictionary.table_info),
    path('data_dictionary/export/', data_dictionary.export),

    path('param/list/', instance.param_list),
    path('param/history/', instance.param_history),
    path('param/edit/', instance.param_edit),

    path('query/', query.query),
    path('query/querylog/', query.querylog),
    path('query/querylog_audit/', query.querylog_audit),
    path('query/favorite/', query.favorite),
    path('query/explain/', sql.sql_optimize.explain),
    path('query/applylist/', sql.query_privileges.query_priv_apply_list),
    path('query/userprivileges/', sql.query_privileges.user_query_priv),
    path('query/applyforprivileges/', sql.query_privileges.query_priv_apply),
    path('query/modifyprivileges/', sql.query_privileges.query_priv_modify),
    path('query/privaudit/', sql.query_privileges.query_priv_audit),

    path('binlog/list/', binlog.binlog_list),
    path('binlog/binlog2sql/', binlog.binlog2sql),
    path('binlog/my2sql/', binlog.my2sql),
    path('binlog/del_log/', binlog.del_binlog),

    path('slowquery/review/', slowlog.slowquery_review),
    path('slowquery/review_history/', slowlog.slowquery_review_history),
    path('slowquery/optimize_sqladvisor/', sql.sql_optimize.optimize_sqladvisor),
    path('slowquery/optimize_sqltuning/', sql.sql_optimize.optimize_sqltuning),
    path('slowquery/optimize_soar/', sql.sql_optimize.optimize_soar),
    path('slowquery/optimize_sqltuningadvisor/', sql.sql_optimize.optimize_sqltuningadvisor),
    path('slowquery/report/', slowlog.report),

    path('db_diagnostic/process/', db_diagnostic.process),
    path('db_diagnostic/create_kill_session/', db_diagnostic.create_kill_session),
    path('db_diagnostic/kill_session/', db_diagnostic.kill_session),
    path('db_diagnostic/tablesapce/', db_diagnostic.tablesapce),
    path('db_diagnostic/trxandlocks/', db_diagnostic.trxandlocks),
    path('db_diagnostic/innodb_trx/', db_diagnostic.innodb_trx),

    path('archive/list/', archiver.archive_list),
    path('archive/apply/', archiver.archive_apply),
    path('archive/audit/', archiver.archive_audit),
    path('archive/switch/', archiver.archive_switch),
    path('archive/once/', archiver.archive_once),
    path('archive/log/', archiver.archive_log),

    path('4admin/sync_ding_user/', ding_api.sync_ding_user),

    path('audit/log/', audit_log.audit_log),
    path('audit/input/', audit_log.audit_input),
    path('user/list/', user.lists),
    path('user/qrcode/<str:data>/', totp.generate_qrcode),
]
