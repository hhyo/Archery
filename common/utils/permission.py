# -*- coding: UTF-8 -*-
import simplejson as json
from django.shortcuts import render
from django.http import HttpResponse


# 管理员操作权限验证
def superuser_required(func):
    def wrapper(request, *args, **kw):
        # 获取用户信息，权限验证
        user = request.user

        if user.is_superuser is False:
            if request.is_ajax():
                result = {'status': 1, 'msg': '您无权操作，请联系管理员', 'data': []}
                return HttpResponse(json.dumps(result), content_type='application/json')
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
            user = request.user
            if user.role not in roles and user.is_superuser is False:
                if request.is_ajax():
                    result = {'status': 1, 'msg': '您无权操作，请联系管理员', 'data': []}
                    return HttpResponse(json.dumps(result), content_type='application/json')
                else:
                    context = {'errMsg': "您无权操作，请联系管理员"}
                    return render(request, "error.html", context)

            return func(request, *args, **kw)

        return wrapper

    return _deco
