#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import requests
import json
import threading
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class HttpRequests(object):
    def __init__(self, timeout=None):
        self.timeout = 3 if timeout is None else timeout

    def post(self, url, params):
        try:
            headers = {"Content-Type": "application/json"}
            resp = requests.post(url, headers=headers, json=params, timeout=self.timeout)
            status = True if resp.status_code == 200 else False

            return status, str(resp.content, encoding="utf8")
        except Exception as e:
            return False, str(e)

    def get(self, url):
        try:
            resp = requests.get(url, timeout=self.timeout)
            status = True if resp.status_code == 200 else False

            return status, str(resp.content, encoding="utf8")
        except Exception as e:
            return False, str(e)


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, datetime.date):
            return obj.strftime("%Y-%m-%d")
        else:
            return json.JSONEncoder.default(self, obj)


def async(func):
    def wrapper(*args, **kwargs):
        thr = threading.Thread(target=func, args=args, kwargs=kwargs)
        thr.start()
    return wrapper
