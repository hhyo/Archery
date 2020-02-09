# coding: utf-8

import logging
import requests
from common.config import SysConfig
from django.core.cache import cache

logger = logging.getLogger('default')


def get_feishu_access_token():
    # 优先获取缓存
    try:
        token = cache.get('feishu_access_token')
    except Exception as e:
        logger.error(f"获取飞书token缓存出错:{e}")
        token = None
    if token:
        return token
    # 请求飞书接口获取
    sys_config = SysConfig()
    app_id = sys_config.get('feishu_appid')
    app_secret = sys_config.get('feishu_app_secret')
    # url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corp_id}&corpsecret={corp_secret}"
    url = f"https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal/"
    data = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    proxies = {'http': 'http://192.168.50.186:8888', 'https': 'http://192.168.50.186:8888'}

    resp = requests.post(url, json=data, timeout=5, proxies=proxies, verify=False).json()
    # resp = requests.get(url, timeout=3).json()
    logger.info(f"获取飞书access_token信息成功:{resp}")
    if resp.get('code') == 0:
        access_token = resp.get('app_access_token')
        expires_in = resp.get('expire')
        cache.set('feishu_access_token', access_token, timeout=expires_in - 60)
        return access_token
    else:
        logger.error(f"获取飞书access_token出错:{resp}")
        return None


def get_feishu_open_id(email):
    logger.info(f"获取飞书openid:{email}")
    url = 'https://open.feishu.cn/open-apis/user/v1/batch_get_id?'
    resp = requests.get(url, timeout=3, headers={'Authorization': "Bearer " + get_feishu_access_token()},
                        params={"emails": email}).json()
    result = []
    if resp.get('code') == 0:
        for key in resp.get('data').get('email_users').values():
            result.append(key[0][f"open_id"])
    return result
