# -*- coding: UTF-8 -*- 
import re
from django.http import HttpResponseRedirect

class CheckLoginMiddleware(object):
    def process_request(self, request):
        """
        该函数在每个函数之前检查是否登录，若未登录，则重定向到/login/
        """
        if request.user.id is None:
            #以下是不用跳转到login页面的url白名单
            if request.path not in ('/login/', '/authenticate/', '/sign_up/') and re.match(r"/admin/\w*", request.path) is None:
                return HttpResponseRedirect('/login/')
