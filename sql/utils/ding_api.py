#!/usr/bin/env python
# -*- coding: utf-8 -*-

import traceback
import logging
import threading
import time
import requests
import json
from django_redis import get_redis_connection
from common.config import SysConfig
from sql.models import Users

logger = logging.getLogger('default')
rs = get_redis_connection('dingding')
sys_config = SysConfig()
corp_id = sys_config.get('ding_corp_id')
corp_secret = sys_config.get('ding_corp_secret')


def async_func(func):
    def wrapper(*args, **kwargs):
        thr = threading.Thread(target=func, args=args, kwargs=kwargs)
        thr.start()
    return wrapper


def get_ding_user_id(username):
    try:
        ding_user_id = rs.execute_command('GET {}'.format(username.upper()))
        if ding_user_id:
            user = Users.objects.get(username=username)
            if user.ding_user_id != str(ding_user_id, encoding="utf8"):
                user.ding_user_id = str(ding_user_id, encoding="utf8")
                user.save(update_fields=['ding_user_id'])
    except Exception as e:
        logger.error(traceback.print_exc())


def get_access_token():
    now_time = int(time.time())
    expire_time = rs.execute_command('TTL token')
    if expire_time and (int(expire_time) - now_time) > 60:
        # 还没到超时时间
        return rs.execute_command('GET token').decode()
    else:
        # token 已过期
        url = "https://oapi.dingtalk.com/gettoken?corpid={0}&corpsecret={1}".format(corp_id, corp_secret)
        resp = requests.get(url, timeout=3)
        ret = str(resp.content, encoding="utf8")
        s = json.loads(ret)
        rs.execute_command('SETEX token {} {}'.format(s["expires_in"], s["access_token"]))
        return s["access_token"]


class DingSender(object):
    def __init__(self):
        self.app_id = sys_config.get('ding_agent_id', None)
        self.token = get_access_token()

    @async_func
    def send_msg(self, ding_user_id, content):
        if self.app_id is None:
            return "No app id."
        data = {
            "touser": ding_user_id,
            "agentid": self.app_id,
            "msgtype": "text",
            "text": {
                "content": "{}".format(content)
            },
        }
        url = 'https://oapi.dingtalk.com/message/send?access_token=' + self.token
        resp = requests.post(url, data)
        logger.info(resp.content)

    def send_msg_sync(self, ding_user_id, content):
        if self.app_id is None:
            return "No app id."
        data = {
            "touser": ding_user_id,
            "agentid": self.app_id,
            "msgtype": "text",
            "text": {
                "content": "{}".format(content)
            },
        }
        url = 'https://oapi.dingtalk.com/message/send?access_token=' + self.token
        resp = requests.post(url, data)
        logger.info(resp.content)
