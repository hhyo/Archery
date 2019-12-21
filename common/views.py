# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: views.py
@time: 2019/12/21
"""

__author__ = 'hhyo'

from django.http import (
    HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound,
    HttpResponseServerError,
)
from django.template import loader
from django.views.decorators.csrf import requires_csrf_token


@requires_csrf_token
def bad_request(request, exception, template_name='errors/400.html'):
    template = loader.get_template(template_name)
    return HttpResponseBadRequest(template.render())


@requires_csrf_token
def permission_denied(request, exception, template_name='errors/403.html'):
    template = loader.get_template(template_name)
    return HttpResponseForbidden(template.render())


@requires_csrf_token
def page_not_found(request, exception, template_name='errors/404.html'):
    template = loader.get_template(template_name)
    return HttpResponseNotFound(template.render())


@requires_csrf_token
def server_error(request, template_name='errors/500.html'):
    template = loader.get_template(template_name)
    return HttpResponseServerError(template.render())
