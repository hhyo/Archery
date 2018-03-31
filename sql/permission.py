# -*- coding: UTF-8 -*-
import json
from django.shortcuts import render
from django.http import HttpResponse
from .models import users


# 管理员操作权限验证
def superuser_required(func):
    def wrapper(request, *args, **kw):
        # 获取用户信息，权限验证
        loginUser = request.session.get('login_username', False)
        loginUserOb = users.objects.get(username=loginUser)

        if loginUserOb.is_superuser is False:
            if request.is_ajax():
                finalResult = {'status': 1, 'msg': '您无权操作，请联系管理员', 'data': []}
                return HttpResponse(json.dumps(finalResult), content_type='application/json')
            else:
                context = {'errMsg': "您无权操作，请联系管理员"}
                return render(request, "error.html", context)

        return func(request, *args, **kw)

    return wrapper


# 角色操作权限验证
def role_required(roles=()):
    def _deco(func):
        def wrapper(request, *args, **kw):
            # 获取用户信息，权限验证
            loginUser = request.session.get('login_username', False)
            loginUserOb = users.objects.get(username=loginUser)
            loginrole = loginUserOb.role

            if loginrole not in roles and loginUserOb.is_superuser is False:
                if request.is_ajax():
                    finalResult = {'status': 1, 'msg': '您无权操作，请联系管理员', 'data': []}
                    return HttpResponse(json.dumps(finalResult), content_type='application/json')
                else:
                    context = {'errMsg': "您无权操作，请联系管理员"}
                    return render(request, "error.html", context)

            return func(request, *args, **kw)

        return wrapper

    return _deco
