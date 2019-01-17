from sql_api import views

from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'workflow', views.SqlWorkflowViewSet, basename='workflow')
router.register(r'instance', views.InstanceViewSet, basename='instance')

urlpatterns = router.urls