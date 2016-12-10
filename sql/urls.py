#coding=utf-8
from django.conf.urls import url,include
from . import views

urlpatterns = [
    url(r'^login/$', views.login, name='login'),
    url(r'^authenticate/$', views.authenticate, name='authenticate'),
    url(r'^submitsql/$', views.submitSql, name='submitSql'),
    url(r'^allworkflow/$', views.allworkflow, name='allworkflow'),
]
