#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import requests
from django.http import JsonResponse
from django_redis import get_redis_connection
from common.config import SysConfig
from common.utils.permission import superuser_required
from sql.models import Users
from sql.utils.tasks import add_sync_ding_user_schedule

logger = logging.getLogger('default')
rs = get_redis_connection('dingding')


def get_access_token():
    """获取access_token:https://ding-doc.dingtalk.com/doc#/serverapi2/eev437"""
    # 优先获取缓存
    try:
        access_token = rs.execute_command(f"get ding_access_token")
    except Exception as e:
        logger.error(f"获取access_token缓存出错:{e}")
        access_token = None
    if access_token:
        return access_token
    # 请求钉钉接口获取
    sys_config = SysConfig()
    app_key = sys_config.get('ding_app_key')
    app_secret = sys_config.get('ding_app_secret')
    url = f"https://oapi.dingtalk.com/gettoken?appkey={app_key}&appsecret={app_secret}"
    resp = requests.get(url, timeout=3).json()
    if resp.get('errcode') == 0:
        rs.execute_command(f"SETEX access_token 7000 {access_token}")
        return resp.get('access_token')
    else:
        logger.error(f"获取access_token出错:{resp}")
        return None


def get_ding_user_id(username):
    """更新用户ding_user_id"""
    try:
        ding_user_id = rs.execute_command('GET {}'.format(username.lower()))
        if ding_user_id:
            user = Users.objects.get(username=username)
            if user.ding_user_id != str(ding_user_id, encoding="utf8"):
                user.ding_user_id = str(ding_user_id, encoding="utf8")
                user.save(update_fields=['ding_user_id'])
    except Exception as e:
        logger.error(f"更新用户ding_user_id失败:{e}")


def get_dept_list_id_fetch_child(token, parent_dept_id):
    """获取所有子部门列表"""
    ids = [int(parent_dept_id)]
    url = 'https://oapi.dingtalk.com/department/list_ids?id={0}&access_token={1}'.format(parent_dept_id, token)
    resp = requests.get(url, timeout=3).json()
    if resp.get('errcode') == 0:
        for dept_id in resp.get("sub_dept_id_list"):
            ids.extend(get_dept_list_id_fetch_child(token, dept_id))
    return list(set(ids))


def sync_ding_user_id():
    """
    使用工号（username）登陆archery，并且工号对应钉钉系统中字段 "jobnumber"。
    所以可根据钉钉中 jobnumber 查到该用户的 ding_user_id。
    """
    sys_config = SysConfig()
    ding_dept_ids = sys_config.get('ding_dept_ids', '')
    username2ding = sys_config.get('ding_archery_username')
    token = get_access_token()
    if not token:
        return False
    # 获取全部部门列表
    sub_dept_id_list = []
    for dept_id in list(set(ding_dept_ids.split(','))):
        sub_dept_id_list.extend(get_dept_list_id_fetch_child(token, dept_id))
    # 遍历部门下的用户
    user_ids = []
    for sdi in sub_dept_id_list:
        url = f'https://oapi.dingtalk.com/user/getDeptMember?access_token={token}&deptId={sdi}'
        try:
            resp = requests.get(url, timeout=3).json()
            if resp.get('errcode') == 0:
                user_ids.extend(resp.get('userIds'))
            else:
                raise Exception(f'获取部门用户出错:{resp}')
        except Exception as e:
            raise Exception(f'获取部门用户出错:{e}')
    # 获取所有用户信息并缓存
    for user_id in list(set(user_ids)):
        url = f'https://oapi.dingtalk.com/user/get?access_token={token}&userid={user_id}'
        try:
            resp = requests.get(url, timeout=3).json()
            if resp.get('errcode') == 0:
                if not resp.get(username2ding):
                    raise Exception(f'钉钉用户信息不包含{username2ding}字段，无法获取id信息，请确认ding_archery_username配置{resp}')
                rs.execute_command(f"SETEX {resp.get(username2ding).lower()} 86400 {resp.get('userid')}")
            else:
                raise Exception(f'获取用户信息出错:{resp}')
        except Exception as e:
            raise Exception(f'获取用户信息出错:{e}')
    return True


@superuser_required
def sync_ding_user(request):
    """主动触发同步接口，同时写入schedule每天进行同步"""
    try:
        # 添加schedule并触发同步
        add_sync_ding_user_schedule()
        return JsonResponse({"status": 0, "msg": f"触发同步成功"})
    except Exception as e:
        return JsonResponse({"status": 1, "msg": f"触发同步异常:{e}"})
