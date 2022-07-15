from django.urls import include, path
from django.contrib import admin
from common import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(("sql_api.urls", "sql_api"), namespace="sql_api")),
    path("", include(("sql.urls", "sql"), namespace="sql")),
]

handler400 = views.bad_request
handler403 = views.permission_denied
handler404 = views.page_not_found
handler500 = views.server_error
