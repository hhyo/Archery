from django import get_version
from django.template.defaultfilters import truncatechars

from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _
from django.db import models
from django.utils import timezone
from picklefield import PickledObjectField
from picklefield.fields import dbsafe_decode

from django_q.signing import SignedPackage


class Task(models.Model):
    id = models.CharField(max_length=32, primary_key=True, editable=False)
    name = models.CharField(max_length=100, editable=False)
    func = models.CharField(max_length=256)
    hook = models.CharField(max_length=256, null=True)
    args = PickledObjectField(null=True, protocol=-1)
    kwargs = PickledObjectField(null=True, protocol=-1)
    result = PickledObjectField(null=True, protocol=-1)
    group = models.CharField(max_length=100, editable=False, null=True)
    started = models.DateTimeField(editable=False)
    stopped = models.DateTimeField(editable=False)
    success = models.BooleanField(default=True, editable=False)

    @staticmethod
    def get_result(task_id):
        if len(task_id) == 32 and Task.objects.filter(id=task_id).exists():
            return Task.objects.get(id=task_id).result
        elif Task.objects.filter(name=task_id).exists():
            return Task.objects.get(name=task_id).result

    @staticmethod
    def get_result_group(group_id, failures=False):
        if failures:
            values = Task.objects.filter(group=group_id).values_list('result', flat=True)
        else:
            values = Task.objects.filter(group=group_id).exclude(success=False).values_list('result', flat=True)
        return decode_results(values)

    def group_result(self, failures=False):
        if self.group:
            return self.get_result_group(self.group, failures)

    @staticmethod
    def get_group_count(group_id, failures=False):
        if failures:
            return Failure.objects.filter(group=group_id).count()
        return Task.objects.filter(group=group_id).count()

    def group_count(self, failures=False):
        if self.group:
            return self.get_group_count(self.group, failures)

    @staticmethod
    def delete_group(group_id, objects=False):
        group = Task.objects.filter(group=group_id)
        if objects:
            return group.delete()
        return group.update(group=None)

    def group_delete(self, tasks=False):
        if self.group:
            return self.delete_group(self.group, tasks)

    @staticmethod
    def get_task(task_id):
        if len(task_id) == 32 and Task.objects.filter(id=task_id).exists():
            return Task.objects.get(id=task_id)
        elif Task.objects.filter(name=task_id).exists():
            return Task.objects.get(name=task_id)

    @staticmethod
    def get_task_group(group_id, failures=True):
        if failures:
            return Task.objects.filter(group=group_id)
        return Task.objects.filter(group=group_id).exclude(success=False)

    def time_taken(self):
        return (self.stopped - self.started).total_seconds()

    @property
    def short_result(self):
        return truncatechars(self.result, 100)

    def __unicode__(self):
        return u'{}'.format(self.name or self.id)

    class Meta:
        app_label = 'django_q'
        ordering = ['-stopped']


class SuccessManager(models.Manager):
    def get_queryset(self):
        return super(SuccessManager, self).get_queryset().filter(
            success=True)


class Success(Task):
    objects = SuccessManager()

    class Meta:
        app_label = 'django_q'
        verbose_name = _('Successful task')
        verbose_name_plural = _('Successful tasks')
        ordering = ['-stopped']
        proxy = True


class FailureManager(models.Manager):
    def get_queryset(self):
        return super(FailureManager, self).get_queryset().filter(
            success=False)


class Failure(Task):
    objects = FailureManager()

    class Meta:
        app_label = 'django_q'
        verbose_name = _('Failed task')
        verbose_name_plural = _('Failed tasks')
        ordering = ['-stopped']
        proxy = True


class Schedule(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    func = models.CharField(max_length=256, help_text='e.g. module.tasks.function')
    hook = models.CharField(max_length=256, null=True, blank=True, help_text='e.g. module.tasks.result_function')
    args = models.TextField(null=True, blank=True, help_text=_("e.g. 1, 2, 'John'"))
    kwargs = models.TextField(null=True, blank=True, help_text=_("e.g. x=1, y=2, name='John'"))
    ONCE = 'O'
    MINUTES = 'I'
    HOURLY = 'H'
    DAILY = 'D'
    WEEKLY = 'W'
    MONTHLY = 'M'
    QUARTERLY = 'Q'
    YEARLY = 'Y'
    TYPE = (
        (ONCE, _('Once')),
        (MINUTES, _('Minutes')),
        (HOURLY, _('Hourly')),
        (DAILY, _('Daily')),
        (WEEKLY, _('Weekly')),
        (MONTHLY, _('Monthly')),
        (QUARTERLY, _('Quarterly')),
        (YEARLY, _('Yearly')),
    )
    schedule_type = models.CharField(max_length=1, choices=TYPE, default=TYPE[0][0], verbose_name=_('Schedule Type'))
    minutes = models.PositiveSmallIntegerField(null=True, blank=True,
                                               help_text=_('Number of minutes for the Minutes type'))
    repeats = models.IntegerField(default=-1, verbose_name=_('Repeats'), help_text=_('n = n times, -1 = forever'))
    next_run = models.DateTimeField(verbose_name=_('Next Run'), default=timezone.now, null=True)
    task = models.CharField(max_length=100, null=True, editable=False)

    def success(self):
        if self.task and Task.objects.filter(id=self.task):
            return Task.objects.get(id=self.task).success

    def last_run(self):
        if self.task and Task.objects.filter(id=self.task):
            task = Task.objects.get(id=self.task)
            if task.success:
                url = reverse('admin:django_q_success_change', args=(task.id,))
            else:
                url = reverse('admin:django_q_failure_change', args=(task.id,))
            return format_html('<a href="{}">[{}]</a>'.format(url, task.name))
        return None

    def __unicode__(self):
        return self.func

    success.boolean = True
    last_run.allow_tags = True

    class Meta:
        app_label = 'django_q'
        verbose_name = _('Scheduled task')
        verbose_name_plural = _('Scheduled tasks')
        ordering = ['next_run']


class OrmQ(models.Model):
    key = models.CharField(max_length=100)
    payload = models.TextField()
    lock = models.DateTimeField(null=True)

    def task(self):
        return SignedPackage.loads(self.payload)

    def func(self):
        return self.task()['func']

    def task_id(self):
        return self.task()['id']

    def name(self):
        return self.task()['name']

    class Meta:
        app_label = 'django_q'
        verbose_name = _('Queued task')
        verbose_name_plural = _('Queued tasks')


# Backwards compatibility for Django 1.7
def decode_results(values):
    if get_version().split('.')[1] == '7':
        # decode values in 1.7
        return [dbsafe_decode(v) for v in values]
    return values
