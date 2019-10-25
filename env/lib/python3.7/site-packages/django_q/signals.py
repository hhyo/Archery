import importlib

from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.utils.translation import ugettext_lazy as _

from django_q.conf import logger
from django_q.models import Task


@receiver(post_save, sender=Task)
def call_hook(sender, instance, **kwargs):
    if instance.hook:
        f = instance.hook
        if not callable(f):
            try:
                module, func = f.rsplit('.', 1)
                m = importlib.import_module(module)
                f = getattr(m, func)
            except (ValueError, ImportError, AttributeError):
                logger.error(_('malformed return hook \'{}\' for [{}]').format(instance.hook, instance.name))
                return
        try:
            f(instance)
        except Exception as e:
            logger.error(_('return hook {} failed on [{}] because {}').format(instance.hook, instance.name, e))


pre_enqueue = Signal(providing_args=["task"])
pre_execute = Signal(providing_args=["func", "task"])
