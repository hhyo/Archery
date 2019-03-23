# -*- coding: UTF-8 -*- 

from django.urls import path
from django.views.i18n import JavaScriptCatalog

import sql.sql_optimize
from common import auth, config, workflow, dashboard, check
from sql import views, sql_workflow, sql_analyze, query, slowlog, instance, db_diagnostic, resource_group, binlog
from sql.utils import jobs

urlpatterns = [
    path('', views.sqlworkflow),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    path('index/', views.sqlworkflow),
    path('login/', views.login, name='login'),
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
    path('instanceuser/<int:instance_id>/', views.instanceuser),
    path('binlog2sql/', views.binlog2sql),
    path('schemasync/', views.schemasync),
    path('config/', views.config),

    path('authenticate/', auth.authenticate_entry),
    path('sqlworkflow_list/', sql_workflow.sql_workflow_list),
    path('simplecheck/', sql_workflow.check),
    path('getWorkflowStatus/', sql_workflow.get_workflow_status),
    path('del_sqlcronjob/', jobs.del_sqlcronjob),

    path('sql_analyze/generate/', sql_analyze.generate),
    path('sql_analyze/analyze/', sql_analyze.analyze),

    path('workflow/list/', workflow.lists),
    path('workflow/log/', workflow.log),
    path('config/change/', config.change_config),

    path('check/inception/', check.inception),
    path('check/email/', check.email),
    path('check/instance/', check.instance),

    path('group/group/', resource_group.group),
    path('group/addrelation/', resource_group.addrelation),
    path('group/relations/', resource_group.associated_objects),
    path('group/instances/', resource_group.instances),
    path('group/unassociated/', resource_group.unassociated_objects),
    path('group/auditors/', resource_group.auditors),
    path('group/changeauditors/', resource_group.changeauditors),

    path('instance/list/', instance.lists),
    path('instance/users/', instance.users),
    path('instance/schemasync/', instance.schemasync),
    path('instance/getdbNameList/', instance.get_db_name_list),
    path('instance/getTableNameList/', instance.get_table_name_list),
    path('instance/getColumnNameList/', instance.get_column_name_list),
    path('instance/describetable/', instance.describe),

    path('query/', query.query),
    path('query/querylog/', query.querylog),
    path('query/explain/', query.explain),
    path('query/applylist/', query.getqueryapplylist),
    path('query/userprivileges/', query.getuserprivileges),
    path('query/applyforprivileges/', query.applyforprivileges),
    path('query/modifyprivileges/', query.modifyqueryprivileges),
    path('query/privaudit/', query.queryprivaudit),

    path('binlog2sql/sql/', binlog.binlog2sql),
    path('binlog2sql/binlog_list/', binlog.binlog_list),

    path('slowquery/review/', slowlog.slowquery_review),
    path('slowquery/review_history/', slowlog.slowquery_review_history),
    path('slowquery/optimize_sqladvisor/', sql.sql_optimize.optimize_sqladvisor),
    path('slowquery/optimize_sqltuning/', sql.sql_optimize.optimize_sqltuning),
    path('slowquery/optimize_soar/', sql.sql_optimize.optimize_soar),

    path('db_diagnostic/process/', db_diagnostic.process),
    path('db_diagnostic/create_kill_session/', db_diagnostic.create_kill_session),
    path('db_diagnostic/kill_session/', db_diagnostic.kill_session),
    path('db_diagnostic/tablesapce/', db_diagnostic.tablesapce),
    path('db_diagnostic/trxandlocks/', db_diagnostic.trxandlocks),
]
