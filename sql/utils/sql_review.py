import datetime
import re
import sqlparse

from sql.models import SqlWorkflow
from common.config import SysConfig
from sql.utils.resource_group import user_groups
from sql.engines import get_engine


def is_auto_review(workflow_id):
    """
    判断SQL上线是否无需审批，无需审批的提交会自动审核通过
    :param workflow_id:
    :return:
    """
    workflow = SqlWorkflow.objects.get(id=workflow_id)
    # TODO 这里也可以放到engine中实现，但是配置项可能会相对复杂
    if workflow.instance.db_type == 'mysql':
        # 获取正则表达式
        auto_review_regex = SysConfig().get('auto_review_regex',
                                            '^alter|^create|^drop|^truncate|^rename|^delete')
        p = re.compile(auto_review_regex, re.I)

        # 判断是否匹配到需要手动审核的语句
        auto_review = True
        sql_content = workflow.sqlworkflowcontent.sql_content
        for statement in sqlparse.split(sql_content):
            # 删除注释语句
            statement = sqlparse.format(statement, strip_comments=True)
            if p.match(statement.strip()):
                auto_review = False
                break
            if auto_review:
                # 更新影响行数加测,总语句影响行数超过指定数量则需要人工审核
                review_engine = get_engine(instance=workflow.instance)
                inception_review = review_engine.execute_check(db_name=workflow.db_name, sql=sql_content).to_dict()
                all_affected_rows = 0
                for review_result in inception_review:
                    sql = review_result.get('sql', '')
                    affected_rows = review_result.get('affected_rows', 0)
                    if re.match(r"^update", sql.strip().lower()):
                        all_affected_rows = all_affected_rows + int(affected_rows)
                if int(all_affected_rows) > int(SysConfig().get('auto_review_max_update_rows', 50)):
                    auto_review = False
    else:
        auto_review = False
    return auto_review


def can_execute(user, workflow_id):
    """
    判断用户当前是否可执行，两种情况下用户有执行权限
    1.登录用户有资源组粒度执行权限，并且为组内用户
    2.当前登录用户为提交人，并且有执行权限
    :param user:
    :param workflow_id:
    :return:
    """
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = False
    # 只有审核通过和定时执行的数据才可以立即执行
    if workflow_detail.status in ['workflow_review_pass', 'workflow_timingtask']:
        # 当前登录用户有资源组粒度执行权限，并且为组内用户
        group_ids = [group.group_id for group in user_groups(user)]
        if workflow_detail.group_id in group_ids and user.has_perm('sql.sql_execute_for_resource_group'):
            result = True
        # 当前登录用户为提交人，并且有执行权限
        if workflow_detail.engineer == user.username and user.has_perm('sql.sql_execute'):
            result = True
    return result


def on_correct_time_period(workflow_id, run_date=None):
    """
    判断是否在可执行时间段内，包括人工执行和定时执行
    :param workflow_id:
    :param run_date:
    :return:
    """
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = True
    ctime = run_date or datetime.datetime.now()
    stime = workflow_detail.run_date_start
    etime = workflow_detail.run_date_end
    if (stime and stime > ctime) or (etime and etime < ctime):
        result = False
    return result


def can_timingtask(user, workflow_id):
    """
    判断用户当前是否可定时执行，两种情况下用户有定时执行权限
    1.登录用户有资源组粒度执行权限，并且为组内用户
    2.当前登录用户为提交人，并且有执行权限
    :param user:
    :param workflow_id:
    :return:
    """
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = False
    # 只有审核通过和定时执行的数据才可以执行
    if workflow_detail.status in ['workflow_review_pass', 'workflow_timingtask']:
        # 当前登录用户有资源组粒度执行权限，并且为组内用户
        group_ids = [group.group_id for group in user_groups(user)]
        if workflow_detail.group_id in group_ids and user.has_perm('sql.sql_execute_for_resource_group'):
            result = True
        # 当前登录用户为提交人，并且有执行权限
        if workflow_detail.engineer == user.username and user.has_perm('sql.sql_execute'):
            result = True
    return result


def can_cancel(user, workflow_id):
    """
    判断用户当前是否是可终止，
    审核中的工单，审核人和提交人可终止
    审核通过但未执行的工单，有执行权限的用户终止
    :param user:
    :param workflow_id:
    :return:
    """
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
