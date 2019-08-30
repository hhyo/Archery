from django.urls import path
from sql_api import views

urlpatterns = [
    path('info', views.info),
    path('debug', views.debug)
]
