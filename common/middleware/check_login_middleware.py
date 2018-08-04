# -*- coding: UTF-8 -*- 
import re
from django.http import HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin


class CheckLoginMiddleware(MiddlewareMixin):
    def process_request(self, request):
        """
        该函数在每个函数之前检查是否登录，若未登录，则重定向到/login/
        """
        if not request.user.is_authenticated:
            # 以下是不用跳转到login页面的url白名单
            if request.path not in ('/login/', '/authenticate/', '/signup/') and re.match(r"/admin/\w*",
                                                                                          request.path) is None:
                return HttpResponseRedirect('/login/')
