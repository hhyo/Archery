from django.urls import path, include
from rest_framework import routers
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
import sql_api.api_views.system as api_system
import sql_api.api_views.user as api_user
import sql_api.api_views.instance as api_instance
import sql_api.api_views.workflow as api_workflow
import sql_api.api_views.sql_workflow as api_sql_workflow


router = routers.DefaultRouter()
router.register(
    r"v2/workflow/sql", api_sql_workflow.SqlWorkflowView, basename="sql_workflow"
)

urlpatterns = [
    path("", include(router.urls)),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "swagger/",
        SpectacularSwaggerView.as_view(url_name="sql_api:schema"),
        name="swagger",
    ),
    path(
        "redoc/", SpectacularRedocView.as_view(url_name="sql_api:schema"), name="redoc"
    ),
    path("v1/user/", api_user.UserList.as_view()),
    path("v1/user/<int:pk>/", api_user.UserDetail.as_view()),
    path("v1/user/group/", api_user.GroupList.as_view()),
    path("v1/user/group/<int:pk>/", api_user.GroupDetail.as_view()),
    path("v1/user/resourcegroup/", api_user.ResourceGroupList.as_view()),
    path("v1/user/resourcegroup/<int:pk>/", api_user.ResourceGroupDetail.as_view()),
    path("v1/user/auth/", api_user.UserAuth.as_view()),
    path("v1/user/2fa/", api_user.TwoFA.as_view()),
    path("v1/user/2fa/state/", api_user.TwoFAState.as_view()),
    path("v1/user/2fa/save/", api_user.TwoFASave.as_view()),
    path("v1/user/2fa/verify/", api_user.TwoFAVerify.as_view()),
    path("v1/instance/", api_instance.InstanceList.as_view()),
    path("v1/instance/<int:pk>/", api_instance.InstanceDetail.as_view()),
    path("v1/instance/resource/", api_instance.InstanceResource.as_view()),
    path("v1/instance/tunnel/", api_instance.TunnelList.as_view()),
    path("v1/instance/rds/", api_instance.AliyunRdsList.as_view()),
    path("v1/workflow/", api_workflow.WorkflowList.as_view()),
    path(
        "v1/workflow/sqlcheck/",
        api_sql_workflow.SqlWorkflowView.as_view({"post": "check"}),
    ),
    path("v1/workflow/audit/", api_workflow.AuditWorkflow.as_view()),
    path("v1/workflow/auditlist/", api_workflow.WorkflowAuditList.as_view()),
    path("v1/workflow/execute/", api_workflow.ExecuteWorkflow.as_view()),
    path("v1/workflow/log/", api_workflow.WorkflowLogList.as_view()),
    path("info", api_system.info),
    path("debug", api_system.debug),
    path("do_once/mirage", api_system.mirage),
]
