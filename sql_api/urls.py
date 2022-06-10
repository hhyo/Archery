from django.urls import path, include
from sql_api import views
from rest_framework import routers
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from . import api_user, api_instance, api_workflow

router = routers.DefaultRouter()

urlpatterns = [
    path('v1/', include(router.urls)),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('swagger/', SpectacularSwaggerView.as_view(url_name='sql_api:schema'), name='swagger'),
    path('redoc/', SpectacularRedocView.as_view(url_name='sql_api:schema'), name='redoc'),
    path('v1/user/', api_user.UserList.as_view()),
    path('v1/user/<int:pk>/', api_user.UserDetail.as_view()),
    path('v1/user/group/', api_user.GroupList.as_view()),
    path('v1/user/group/<int:pk>/', api_user.GroupDetail.as_view()),
    path('v1/user/resourcegroup/', api_user.ResourceGroupList.as_view()),
    path('v1/user/resourcegroup/<int:pk>/', api_user.ResourceGroupDetail.as_view()),
    path('v1/user/auth/', api_user.UserAuth.as_view()),
    path('v1/user/2fa/', api_user.TwoFA.as_view()),
    path('v1/user/2fa/save/', api_user.TwoFASave.as_view()),
    path('v1/user/2fa/verify/', api_user.TwoFAVerify.as_view()),
    path('v1/instance/', api_instance.InstanceList.as_view()),
    path('v1/instance/<int:pk>/', api_instance.InstanceDetail.as_view()),
    path('v1/instance/resource/', api_instance.InstanceResource.as_view()),
    path('v1/instance/tunnel/', api_instance.TunnelList.as_view()),
    path('v1/instance/rds/', api_instance.AliyunRdsList.as_view()),
    path('v1/workflow/', api_workflow.WorkflowList.as_view()),
    path('v1/workflow/sqlcheck/', api_workflow.ExecuteCheck.as_view()),
    path('v1/workflow/audit/', api_workflow.AuditWorkflow.as_view()),
    path('v1/workflow/auditlist/', api_workflow.WorkflowAuditList.as_view()),
    path('v1/workflow/execute/', api_workflow.ExecuteWorkflow.as_view()),
    path('v1/workflow/log/', api_workflow.WorkflowLogList.as_view()),
    path('info', views.info),
    path('debug', views.debug),
    path('do_once/mirage', views.mirage)
]
