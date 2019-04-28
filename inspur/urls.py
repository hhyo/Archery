# -*- coding: UTF-8 -*-
from django.urls import path
from inspur import views

urlpatterns = [
    path('sqlupdate1/', views.sqlupdate1),
    path('update/updatelog/', views.updatelog),
    path('update1/', views.update1),
]