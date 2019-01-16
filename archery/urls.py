from django.urls import include, path
from django.contrib import admin

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(('sql_api.urls', 'sql_api'), namespace='sql_api')),
    path('', include(('sql.urls', 'sql'), namespace="sql")),
    path('themis/', include(('themis.urls', 'themis'), namespace="themis")),
]
