# -*- coding: UTF-8 -*- 

from django.conf.urls import url,include
from . import views

urlpatterns = [
    url(r'^$', views.allworkflow, name='allworkflow'),
    url(r'^index/$', views.allworkflow, name='allworkflow'),
    url(r'^login/$', views.login, name='login'),
    url(r'^logout/$', views.logout, name='logout'),
    url(r'^authenticate/$', views.authenticate, name='authenticate'),
    url(r'^submitsql/$', views.submitSql, name='submitSql'),
    url(r'^allworkflow/$', views.allworkflow, name='allworkflow'),
    
    url(r'^autoreview/$', views.autoreview, name='autoreview'),
    url(r'^detail/(?P<workflowId>[0-9]+)/$', views.detail, name='detail'),
    url(r'^execute/$', views.execute, name='execute'),
    url(r'^cancel/$', views.cancel, name='cancel'),
    url(r'^rollback/$', views.rollback, name='rollback'),
    url(r'^dbaprinciples/$', views.dbaprinciples, name='dbaprinciples'),
]
