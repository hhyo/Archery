#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import json
import time
import traceback
import requests
from common.config import SysConfig
from sql.utils.ding_api import get_access_token, rs

logger = logging.getLogger('default')
sys_config = SysConfig()
username2ding = sys_config.get('ding_archer_username')
ding_dept_ids = sys_config.get('ding_dept_ids', '')


def get_dept_list_id_fetch_child(token, parent_dept_id):
    ids = [int(parent_dept_id)]
    url = 'https://oapi.dingtalk.com/department/list_ids?id={0}&access_token={1}'.format(parent_dept_id, token)
    resp = requests.get(url, timeout=3)
    ret = str(resp.content, encoding="utf8")
    s = json.loads(ret)
    if s["errcode"] == 0:
        for dept_id in s["sub_dept_id_list"]:
            ids.extend(get_dept_list_id_fetch_child(token, dept_id))
    return ids


def sync_ding_user_id():
    """
    使用工号（username）登陆archery，并且工号对应钉钉系统中字段 "jobnumber"。
    所以可根据钉钉中 jobnumber 查到该用户的 ding_user_id。
    """
    try:
        token = get_access_token()
        for dept_id in ding_dept_ids.split(','):
            sub_dept_id_list = get_dept_list_id_fetch_child(token, dept_id)
            for sdi in sub_dept_id_list:
                url = 'https://oapi.dingtalk.com/user/list?access_token={0}&department_id={1}'.format(token, sdi)
                try:
                    resp = requests.get(url, timeout=3)
                    ret = str(resp.content, encoding="utf8")
                    # logger.debug('user_list_by_dept_id: %s' % ret)
                    s = json.loads(ret)
                    if s["errcode"] == 0:
                        for u in s["userlist"]:
                            try:
                                cmd = """SETEX {} 86400 {}""".format(u[username2ding], u["userid"])
                                rs.execute_command(cmd)
                            except:
                                logger.error(traceback.print_exc())
                    else:
                        logger.error(ret)
                except:
                    logger.error(traceback.print_exc())
                time.sleep(1)
    except:
        logger.error(traceback.print_exc())
