import datetime
import json
import re
from django.db import transaction

from sql.engines.models import ReviewResult
from sql.models import SqlWorkflow
from common.config import SysConfig
from sql.utils.resource_group import user_groups
from sql.utils.sql_utils import remove_comments


def is_auto_review(workflow_id):
    """
    判断SQL上线是否无需审批，无需审批的提交会自动审核通过
    :param workflow_id:
    :return:
    """

    workflow = SqlWorkflow.objects.get(id=workflow_id)
    auto_review_tags = SysConfig().get('auto_review_tag', '').split(',')
    auto_review_db_type = SysConfig().get('auto_review_db_type', '').split(',')
    # TODO 这里也可以放到engine中实现，但是配置项可能会相对复杂
    if workflow.instance.db_type in auto_review_db_type and workflow.instance.instance_tag.filter(
            tag_code__in=auto_review_tags).exists():
        # 获取正则表达式
        auto_review_regex = SysConfig().get(
            'auto_review_regex', '^alter|^create|^drop|^truncate|^rename|^delete')
        p = re.compile(auto_review_regex, re.I)

        # 判断是否匹配到需要手动审核的语句
        auto_review = True
        all_affected_rows = 0
        review_content = workflow.sqlworkflowcontent.review_content
        for review_row in json.loads(review_content):
            review_result = ReviewResult(**review_row)
            # 去除SQL注释 https://github.com/hhyo/Archery/issues/949
            sql = remove_comments(review_result.sql).replace("\n","").replace("\r", "")
            # 正则匹配
            if p.match(sql):
                auto_review = False
                break
            # 影响行数加测, 总语句影响行数超过指定数量则需要人工审核
            all_affected_rows += int(review_result.affected_rows)
        if all_affected_rows > int(SysConfig().get('auto_review_max_update_rows', 50)):
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
    result = False
    # 保证工单当前是可执行状态
    with transaction.atomic():
        workflow_detail = SqlWorkflow.objects.select_for_update().get(id=workflow_id)
        # 只有审核通过和定时执行的数据才可以立即执行
        if workflow_detail.status not in ['workflow_review_pass', 'workflow_timingtask']:
            return False
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
    审核中、审核通过的的工单，审核人和提交人可终止
    :param user:
    :param workflow_id:
    :return:
    """
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = False
    # 审核中的工单，审核人和提交人可终止
    if workflow_detail.status == 'workflow_manreviewing':
        from sql.utils.workflow_audit import Audit
        return any([Audit.can_review(user, workflow_id, 2), user.username == workflow_detail.engineer])
    elif workflow_detail.status in ['workflow_review_pass', 'workflow_timingtask']:
        return any([can_execute(user, workflow_id), user.username == workflow_detail.engineer])
    return result


def can_view(user, workflow_id):
    """
    判断用户当前是否可以查看工单信息，和列表过滤逻辑保存一致
    :param user:
    :param workflow_id:
    :return:
    """
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = False
    # 管理员，可查看所有工单
    if user.is_superuser:
        result = True
    # 非管理员，拥有审核权限、资源组粒度执行权限的，可以查看组内所有工单
    elif user.has_perm('sql.sql_review') or user.has_perm('sql.sql_execute_for_resource_group'):
        # 先获取用户所在资源组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        if workflow_detail.group_id in group_ids:
            result = True
    # 其他人只能查看自己提交的工单
    else:
        if workflow_detail.engineer == user.username:
            result = True
    return result


def can_rollback(user, workflow_id):
    """
    判断用户当前是否可以查看回滚信息，和工单详情保持一致
    执行结束并且开启备份的工单可以查看回滚信息
    :param user:
    :param workflow_id:
    :return:
    """
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = False
    # 执行结束并且开启备份的工单可以查看回滚信息
    if workflow_detail.is_backup and workflow_detail.status in ('workflow_finish', 'workflow_exception'):
        return can_view(user, workflow_id)
    return result
