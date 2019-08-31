from django.urls import include, path
from django.contrib import admin

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(('sql_api.urls', 'sql_api'), namespace="sql_api")),
    path('', include(('sql.urls', 'sql'), namespace="sql")),
]
