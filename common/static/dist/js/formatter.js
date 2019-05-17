// 工作流申请类型，1.sql 2.query
workflow_type = {
    'query': 1,
    'query_display': '查询权限申请',
    'sqlreview': 2,
    'sqlreview_display': 'SQL上线申请'
}

// 0.待审核 1.审核通过/等待执行 2.审核不通过 3.审核取消 101执行中，102执行成功，103执行失败
workflow_status = {
    'audit_wait': 0,
    'audit_wait_display': '待审核',
    'audit_success': 1,
    'audit_success_display': '审核通过',
    'audit_reject': 2,
    'audit_reject_display': '审核不通过',
    'audit_abort': 3,
    'audit_abort_display': '审核取消'
}


function sqlworkflowStatus_formatter(value) {
    if (value === "workflow_finish") {
        return "<span class=\"label label-success\">" + gettext(value) + "</span>"
    }
    else if (value === "workflow_abort") {
        return "<span class=\"label label-default\">" + gettext(value) + "</span>"
    }
    else if (value === "workflow_manreviewing") {
        return "<span class=\"label label-info\">" + gettext(value) + "</span>"
    }
    else if (value === "workflow_review_pass") {
        return "<span class=\"label label-warning\">" + gettext(value) + "</span>"
    }
    else if (value === "workflow_timingtask") {
        return "<span class=\"label label-warning\">" + gettext(value) + "</span>"
    }
    else if (value === "workflow_executing") {
        return "<span class=\"label label-primary\">" + gettext(value) + "</span>"
    }
    else if (value === "workflow_autoreviewwrong") {
        return "<span class=\"label label-danger\">" + gettext(value) + "</span>"
    }
    else if (value === "workflow_exception") {
        return "<span class=\"label label-danger\">" + gettext(value) + "</span>"
    }
    else if (value === "workflow_finish_manual") {
        return "<span class=\"label label-success\">" + gettext(value) + "</span>"
    }
    else {
        return "<span class=\"label label-danger\">" + "未知状态" + "</span>"
    }
}

function workflow_type_formatter(value) {
    if (value === workflow_type.query) {
        return workflow_type.query_display
    }
    else if (value === workflow_type.sqlreview) {
        return workflow_type.sqlreview_display
    }
    else {
        return '未知状态'
    }
}

function workflow_status_formatter(value) {
    if (value === workflow_status.audit_wait) {
        return "<span class='label label-info'>" + workflow_status.audit_wait_display + " </span>"
    }
    else if (value === workflow_status.audit_success) {
        return "<span class='label label-success'> " + workflow_status.audit_success_display + " </span>"
    }
    else if (value === workflow_status.audit_reject) {
        return "<span class='label label-danger'>" + workflow_status.audit_reject_display + " </span>"
    }
    else if (value === workflow_status.audit_abort) {
        return "<span class='label label-default'>" + workflow_status.audit_abort_display + " </span>"
    }
    else {
        return "<span class=\"label label-danger\">" + '未知状态' + "</span>"
    }
}
