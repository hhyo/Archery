version = (1, 11, 3)
display_version = ".".join(str(i) for i in version)

from .celery import app as celery_app
__all__ = ['celery_app']