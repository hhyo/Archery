import re
import sqlparse

from common.utils.const import Const
from sql.models import SqlWorkflow
from common.config import SysConfig
from sql.utils.resource_group import user_groups
from sql.utils.inception import InceptionDao


# 获取工单地址
def get_detail_url(request, workflow_id):
    scheme = request.scheme
    host = request.META['HTTP_HOST']
    from sql.utils.workflow_audit import Audit
    audit_id = Audit.detail_by_workflow_id(workflow_id, 2).audit_id
    return "{}://{}/workflow/{}/".format(scheme, host, audit_id)


# 判断SQL上线是否无需审批
def is_auto_review(workflow_id):
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    sql_content = workflow_detail.sql_content
    instance_name = workflow_detail.instance_name
    db_name = workflow_detail.db_name
    is_manual = workflow_detail.is_manual

    # 删除注释语句
    sql_content = ''.join(
        map(lambda x: re.compile(r'(^--\s+.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
            sql_content.splitlines(1))).strip()

    # 获取正则表达式
    auto_review_regex = SysConfig().sys_config.get('auto_review_regex',
                                                   '^alter|^create|^drop|^truncate|^rename|^delete')
    p = re.compile(auto_review_regex)

    # 判断是否匹配到需要手动审核的语句
    is_autoreview = True
    for statement in sqlparse.split(sql_content):
        if p.match(statement.strip().lower()):
            is_autoreview = False
            break
        if is_autoreview:
            # 更新影响行数加测,总语句影响行数超过指定数量则需要人工审核
            inception_review = InceptionDao(instance_name=instance_name).sqlauto_review(sql_content, db_name)
            all_affected_rows = 0
            for review_result in inception_review:
                SQL = review_result[5]
                affected_rows = review_result[6]
                if re.match(r"^update", SQL.strip().lower()):
                    all_affected_rows = all_affected_rows + int(affected_rows)
            if int(all_affected_rows) > int(SysConfig().sys_config.get('auto_review_max_update_rows', 50)):
                is_autoreview = False

    # inception不支持语法都需要审批
    if is_manual == 1:
        is_autoreview = False
    return is_autoreview


# 判断用户当前是否可执行
def can_execute(user, workflow_id):
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = False
    # 只有审核通过和定时执行的数据才可以立即执行
    if workflow_detail.status in [Const.workflowStatus['pass'], Const.workflowStatus['timingtask']]:
        # 当前登录用户必须为有执行权限的组内用户
        group_ids = [group.group_id for group in user_groups(user)]
        if workflow_detail.group_id in group_ids and user.has_perm('sql.sql_execute'):
            return True
    return result


# 判断用户当前是否可定时执行
def can_timingtask(user, workflow_id):
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = False
    # 只有审核通过和定时执行的数据才可以执行
    if workflow_detail.status in [Const.workflowStatus['pass'], Const.workflowStatus['timingtask']]:
        # 当前登录用户必须为有执行权限的组内用户
        group_ids = [group.group_id for group in user_groups(user)]
        if workflow_detail.group_id in group_ids and user.has_perm('sql.sql_execute'):
            result = True
    return result


# 判断用户当前是否是可终止
def can_cancel(user, workflow_id):
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = False
    # 审核中的工单，审核人和提交人可终止
    if workflow_detail.status == Const.workflowStatus['manreviewing']:
        from sql.utils.workflow_audit import Audit
        if Audit.can_review(user, workflow_id, 2) or user.username == workflow_detail.engineer:
            result = True
    # 审核通过但未执行的工单，执行人可以打回
    if workflow_detail.status in [Const.workflowStatus['pass'], Const.workflowStatus['timingtask']]:
        result = True if can_execute(user, workflow_id) else False
    return result
