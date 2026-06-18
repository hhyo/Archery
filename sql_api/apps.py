from django.apps import AppConfig
from django.db import ProgrammingError


class SqlApi2Config(AppConfig):
    name = "sql_api"

    def ready(self):
        # 延迟导入，避免循环引用
        from sql.utils.tasks import add_query_priv_expire_reminder_schedule
        from django_q.models import Schedule

        try:
            # 检查是否已存在定时任务
            if not Schedule.objects.filter(name="查询权限到期提醒").exists():
                add_query_priv_expire_reminder_schedule()
        except ProgrammingError:
            # 表（django_q_schedule）还不存在，说明正在 makemigrations 或首次 migrate
            # 忽略即可，等表创建后下次启动时会自动创建任务
            pass
