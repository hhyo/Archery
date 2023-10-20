import django_cas_ng.views
from django.urls import include, path
from django.contrib import admin
from common import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(("sql_api.urls", "sql_api"), namespace="sql_api")),
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("dingding/", include("django_auth_dingding.urls")),
    path(
        "cas/authenticate/", django_cas_ng.views.LoginView.as_view(), name="cas-login"
    ),
    path("", include(("sql.urls", "sql"), namespace="sql")),
]

handler400 = views.bad_request
handler403 = views.permission_denied
handler404 = views.page_not_found
handler500 = views.server_error
