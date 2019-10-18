# coding: utf-8

import os
import json
import time
import logging
import requests
from common.config import SysConfig
from archery.settings import BASE_DIR

TOKEN_FILE = os.path.join(BASE_DIR, 'downloads', 'access_token.json')
logger = logging.getLogger('default')


def get_wx_headers():
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip,deflate,sdch",
        "Accept-Language": "en-US,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "User-Agent": "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_6; en-US) "
                      "AppleWebKit/533.20.25 (KHTML, like Gecko) Version/5.0.4 Safari/533.20.28"
    }


def re_fetch_wx_token():
    token = ''
    sys_config = SysConfig()
    corp_id = sys_config.get('wx_corpid')
    corp_secret = sys_config.get('wx_app_secret')
    fetch_url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=%s&corpsecret=%s" % (corp_id, corp_secret)
    try:
        res = requests.get(fetch_url, headers=get_wx_headers(), timeout=5, verify=True)
        r_json = res.json()
        if r_json['errcode'] == 0:
            with open(TOKEN_FILE, "w") as f:
                f.write(res.text)
            token = r_json['access_token']
        return token
    except Exception as e:
        logger.error('get weixin token error::%s' % e)


def get_wx_access_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            t_token = json.load(f)
            expire_time = int(t_token['expires_in'])
        if (time.time() - os.stat(TOKEN_FILE).st_mtime) >= expire_time:
            token = re_fetch_wx_token()
            return token
        else:
            token = t_token['access_token']
    else:
        token = re_fetch_wx_token()
    return token
