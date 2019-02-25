# -*- coding: UTF-8 -*- 

class Const(object):
    # 定时任务id的前缀
    workflowJobprefix = {
        'query': 'query',
        'sqlreview': 'sqlreview',
    }


class WorkflowDict:
    # 工作流申请类型，1.query,2.SQL上线申请
    workflow_type = {
        'query': 1,
        'query_display': '查询权限申请',
        'sqlreview': 2,
        'sqlreview_display': 'SQL上线申请',
    }

    # 工作流状态，0.待审核 1.审核通过 2.审核不通过 3.审核取消
    workflow_status = {
        'audit_wait': 0,
        'audit_wait_display': '待审核',
        'audit_success': 1,
        'audit_success_display': '审核通过',
        'audit_reject': 2,
        'audit_reject_display': '审核不通过',
        'audit_abort': 3,
        'audit_abort_display': '审核取消',
    }

class SQLTuning:
    SYS_PARM_FILTER = [
        'BINLOG_CACHE_SIZE',
        'BULK_INSERT_BUFFER_SIZE',
        'HAVE_PARTITION_ENGINE',
        'HAVE_QUERY_CACHE',
        'INTERACTIVE_TIMEOUT',
        'JOIN_BUFFER_SIZE',
        'KEY_BUFFER_SIZE',
        'KEY_CACHE_AGE_THRESHOLD',
        'KEY_CACHE_BLOCK_SIZE',
        'KEY_CACHE_DIVISION_LIMIT',
        'LARGE_PAGES',
        'LOCKED_IN_MEMORY',
        'LONG_QUERY_TIME',
        'MAX_ALLOWED_PACKET',
        'MAX_BINLOG_CACHE_SIZE',
        'MAX_BINLOG_SIZE',
        'MAX_CONNECT_ERRORS',
        'MAX_CONNECTIONS',
        'MAX_JOIN_SIZE',
        'MAX_LENGTH_FOR_SORT_DATA',
        'MAX_SEEKS_FOR_KEY',
        'MAX_SORT_LENGTH',
        'MAX_TMP_TABLES',
        'MAX_USER_CONNECTIONS',
        'OPTIMIZER_PRUNE_LEVEL',
        'OPTIMIZER_SEARCH_DEPTH',
        'QUERY_CACHE_SIZE',
        'QUERY_CACHE_TYPE',
        'QUERY_PREALLOC_SIZE',
        'RANGE_ALLOC_BLOCK_SIZE',
        'READ_BUFFER_SIZE',
        'READ_RND_BUFFER_SIZE',
        'SORT_BUFFER_SIZE',
        'SQL_MODE',
        'TABLE_CACHE',
        'THREAD_CACHE_SIZE',
        'TMP_TABLE_SIZE',
        'WAIT_TIMEOUT'
    ]