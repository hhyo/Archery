from django.apps import AppConfig


class SqlApi2Config(AppConfig):
    name = "sql_api"

    def ready(self):
        from sql.utils.tasks import add_query_priv_expire_reminder_schedule
        from django_q.models import Schedule

        # 检查是否已存在
        if not Schedule.objects.filter(name="查询权限到期提醒").exists():
            add_query_priv_expire_reminder_schedule()
