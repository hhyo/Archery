# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: views.py
@time: 2019/12/21
"""
from django.shortcuts import render

__author__ = "hhyo"

from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseServerError,
)
from django.views.decorators.csrf import requires_csrf_token


@requires_csrf_token
def bad_request(request, exception, template_name="errors/400.html"):
    return HttpResponseBadRequest(render(request, template_name))


@requires_csrf_token
def permission_denied(request, exception, template_name="errors/403.html"):
    return HttpResponseForbidden(render(request, template_name))


@requires_csrf_token
def page_not_found(request, exception, template_name="errors/404.html"):
    return HttpResponseNotFound(render(request, template_name))


@requires_csrf_token
def server_error(request, template_name="errors/500.html"):
    return HttpResponseServerError(render(request, template_name))
