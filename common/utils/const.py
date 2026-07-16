from django.db import models
from django.utils.translation import gettext_lazy as _


class Const(object):
    # 定时任务id的前缀
    workflowJobprefix = {
        "query": "query",
        "sqlreview": "sqlreview",
        "archive": "archive",
    }


class WorkflowType(models.IntegerChoices):
    QUERY = 1, _("Query Privilege Request")
    SQL_REVIEW = 2, _("SQL Deployment Request")
    ARCHIVE = 3, _("Data Archive Request")


class WorkflowStatus(models.IntegerChoices):
    WAITING = 0, _("Pending Review")
    PASSED = 1, _("Approved")
    REJECTED = 2, _("Rejected")
    ABORTED = 3, _("Cancelled")


class WorkflowAction(models.IntegerChoices):
    """工单操作列表, 必须是动词, 不是一种状态"""

    SUBMIT = 0, _("Submit")
    PASS = 1, _("Approve")
    REJECT = 2, _("Reject")
    ABORT = 3, _("Cancel")
    EXECUTE_SET_TIME = 4, _("Schedule Execution")
    EXECUTE_START = 5, _("Execution Started")
    EXECUTE_END = 6, _("Execution Finished")


class SQLTuning:
    SYS_PARM_FILTER = [
        "BINLOG_CACHE_SIZE",
        "BULK_INSERT_BUFFER_SIZE",
        "HAVE_PARTITION_ENGINE",
        "HAVE_QUERY_CACHE",
        "INTERACTIVE_TIMEOUT",
        "JOIN_BUFFER_SIZE",
        "KEY_BUFFER_SIZE",
        "KEY_CACHE_AGE_THRESHOLD",
        "KEY_CACHE_BLOCK_SIZE",
        "KEY_CACHE_DIVISION_LIMIT",
        "LARGE_PAGES",
        "LOCKED_IN_MEMORY",
        "LONG_QUERY_TIME",
        "MAX_ALLOWED_PACKET",
        "MAX_BINLOG_CACHE_SIZE",
        "MAX_BINLOG_SIZE",
        "MAX_CONNECT_ERRORS",
        "MAX_CONNECTIONS",
        "MAX_JOIN_SIZE",
        "MAX_LENGTH_FOR_SORT_DATA",
        "MAX_SEEKS_FOR_KEY",
        "MAX_SORT_LENGTH",
        "MAX_TMP_TABLES",
        "MAX_USER_CONNECTIONS",
        "OPTIMIZER_PRUNE_LEVEL",
        "OPTIMIZER_SEARCH_DEPTH",
        "QUERY_CACHE_SIZE",
        "QUERY_CACHE_TYPE",
        "QUERY_PREALLOC_SIZE",
        "RANGE_ALLOC_BLOCK_SIZE",
        "READ_BUFFER_SIZE",
        "READ_RND_BUFFER_SIZE",
        "SORT_BUFFER_SIZE",
        "SQL_MODE",
        "TABLE_CACHE",
        "THREAD_CACHE_SIZE",
        "TMP_TABLE_SIZE",
        "WAIT_TIMEOUT",
    ]
