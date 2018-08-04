from django.urls import include, path
from django.contrib import admin

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(('sql.urls', 'sql'), namespace="sql")),
    path('themis/', include(('themis.urls', 'themis'), namespace="themis")),
]
