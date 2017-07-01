# -*- coding: UTF-8 -*- 

from django.conf.urls import url,include
from . import views, views_ajax

urlpatterns = [
    url(r'^$', views.allworkflow, name='allworkflow'),
    url(r'^index/$', views.allworkflow, name='allworkflow'),
    url(r'^login/$', views.login, name='login'),
    url(r'^logout/$', views.logout, name='logout'),
    url(r'^submitsql/$', views.submitSql, name='submitSql'),
    url(r'editsql/$', views.submitSql, name='editsql'),
    url(r'^allworkflow/$', views.allworkflow, name='allworkflow'),
    
    url(r'^autoreview/$', views.autoreview, name='autoreview'),
    url(r'^detail/(?P<workflowId>[0-9]+)/$', views.detail, name='detail'),
    url(r'^execute/$', views.execute, name='execute'),
    url(r'^cancel/$', views.cancel, name='cancel'),
    url(r'^rollback/$', views.rollback, name='rollback'),
    url(r'^dbaprinciples/$', views.dbaprinciples, name='dbaprinciples'),
    url(r'^charts/$', views.charts, name='charts'),

    url(r'^authenticate/$', views_ajax.authenticateEntry, name='authenticate'),
    url(r'^simplecheck/$', views_ajax.simplecheck, name='simplecheck'),
    url(r'^getMonthCharts/$', views_ajax.getMonthCharts, name='getMonthCharts'),
    url(r'^getPersonCharts/$', views_ajax.getPersonCharts, name='getPersonCharts'),
    url(r'^getOscPercent/$', views_ajax.getOscPercent, name='getOscPercent'),
    url(r'^getWorkflowStatus/$', views_ajax.getWorkflowStatus, name='getWorkflowStatus'),
    url(r'^stopOscProgress/$', views_ajax.stopOscProgress, name='stopOscProgress'),
]
