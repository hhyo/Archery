#!/usr/bin/env python
# coding=utf-8
# author:LJX
# createdate:2022-07-27 13:56:09

import json
import requests
from common.config import SysConfig


class FSMessage(object):
    def __init__(self):
        self.url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=user_id"
        sys_config = SysConfig()
        self.app_id = sys_config.get("feishu_appid")
        self.app_secret = sys_config.get("feishu_app_secret")
        self.params = {"receive_id_type": "chat_id"}
        self.msg = "text content"
        self.headers = {'Authorization': f'Bearer {self.get_token()}', 'Content-Type': 'application/json'}

    def get_token(self):
        """
        获取token
        """
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {
            'Content-Type': 'application/json; charset=utf-8'
        }
        req = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        response = requests.request(
            "POST",
            url,
            headers=headers,
            data=json.dumps(req)
        )
        return response.json()["tenant_access_token"]

    def get_user_id(self, email):
        url = "https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id?user_id_type=user_id"
        req = {
            "emails": [
                email
            ]
        }
        payload = json.dumps(req)
        response = (
            requests.request(
                "POST",
                url,
                params=self.params,
                headers=self.headers,
                data=payload
            )
        ).json()
        if response["code"] != 0:
            return False
        if not (
                response["data"]["user_list"][0]
        ).__contains__('user_id'):
            return False
        return response["data"]["user_list"][0]['user_id']
