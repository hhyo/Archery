import re
import sqlparse

from sql.models import SqlWorkflow, Instance
from common.config import SysConfig
from sql.utils.resource_group import user_groups
from sql.engines import get_engine


# 判断SQL上线是否无需审批
def is_auto_review(workflow_id):
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    sql_content = workflow_detail.sql_content
    instance_name = workflow_detail.instance_name
    db_name = workflow_detail.db_name
    is_manual = workflow_detail.is_manual

    # 获取正则表达式
    auto_review_regex = SysConfig().get('auto_review_regex',
                                        '^alter|^create|^drop|^truncate|^rename|^delete')
    p = re.compile(auto_review_regex)

    # 判断是否匹配到需要手动审核的语句
    is_autoreview = True
    for statement in sqlparse.split(sql_content):
        # 删除注释语句
        statement = sqlparse.format(statement, strip_comments=True)
        if p.match(statement.strip().lower()):
            is_autoreview = False
            break
        if is_autoreview:
            # 更新影响行数加测,总语句影响行数超过指定数量则需要人工审核
            instance = Instance.objects.get(instance_name=instance_name)
            review_engine = get_engine(instance=instance)
            inception_review = review_engine.execute_check(db_name=db_name, sql=sql_content).to_dict()
            all_affected_rows = 0
            for review_result in inception_review:
                sql = review_result.get('sql', '')
                affected_rows = review_result.get('affected_rows', 0)
                if re.match(r"^update", sql.strip().lower()):
                    all_affected_rows = all_affected_rows + int(affected_rows)
            if int(all_affected_rows) > int(SysConfig().get('auto_review_max_update_rows', 50)):
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
    if workflow_detail.status in ['workflow_review_pass', 'workflow_timingtask']:
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
    if workflow_detail.status in ['workflow_review_pass', 'workflow_timingtask']:
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
    if workflow_detail.status == 'workflow_manreviewing':
        from sql.utils.workflow_audit import Audit
        if Audit.can_review(user, workflow_id, 2) or user.username == workflow_detail.engineer:
            result = True
    # 审核通过但未执行的工单，执行人可以打回
    if workflow_detail.status in ['workflow_review_pass', 'workflow_timingtask']:
        result = True if can_execute(user, workflow_id) else False
    return result
