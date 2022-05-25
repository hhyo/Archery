# -*- coding: UTF-8 -*-
import re
from django.http import HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin

IGNORE_URL = [
    '/login/',
    '/login/2fa/',
    '/authenticate/',
    '/signup/',
    '/api/info'
]

IGNORE_URL_RE = r'/api/(v1|auth)/\w+'


class CheckLoginMiddleware(MiddlewareMixin):
    @staticmethod
    def process_request(request):
        """
        该函数在每个函数之前检查是否登录，若未登录，则重定向到/login/
        """
        if not request.user.is_authenticated:
            # 以下是不用跳转到login页面的url白名单
            if request.path not in IGNORE_URL and re.match(IGNORE_URL_RE, request.path) is None \
                    and not (re.match(r'/user/qrcode/\w+', request.path) and request.session.get('user')):
                return HttpResponseRedirect('/login/')
