from datetime import timedelta
from multiprocessing import Event, Value

import arrow
import pytest
from django.db import IntegrityError
from django.utils import timezone

from django_q.brokers import get_broker
from django_q.cluster import pusher, worker, monitor, scheduler
from django_q.conf import Conf
from django_q.tasks import Schedule, fetch, schedule as create_schedule
from django_q.queues import Queue


@pytest.fixture
def broker(monkeypatch):
    monkeypatch.setattr(Conf, 'DJANGO_REDIS', 'default')
    return get_broker()


@pytest.mark.django_db
def test_scheduler(broker, monkeypatch):
    broker.list_key = 'scheduler_test:q'
    broker.delete_queue()
    schedule = create_schedule('math.copysign',
                               1, -1,
                               name='test math',
                               hook='django_q.tests.tasks.result',
                               schedule_type=Schedule.HOURLY,
                               repeats=1)
    assert schedule.last_run() is None
    # check duplicate constraint
    with pytest.raises(IntegrityError):
        schedule = create_schedule('math.copysign',
                                   1, -1,
                                   name='test math',
                                   hook='django_q.tests.tasks.result',
                                   schedule_type=Schedule.HOURLY,
                                   repeats=1)
    # run scheduler
    scheduler(broker=broker)
    # set up the workflow
    task_queue = Queue()
    stop_event = Event()
    stop_event.set()
    # push it
    pusher(task_queue, stop_event, broker=broker)
    assert task_queue.qsize() == 1
    assert broker.queue_size() == 0
    task_queue.put('STOP')
    # let a worker handle them
    result_queue = Queue()
    worker(task_queue, result_queue, Value('b', -1))
    assert result_queue.qsize() == 1
    result_queue.put('STOP')
    # store the results
    monitor(result_queue)
    assert result_queue.qsize() == 0
    schedule = Schedule.objects.get(pk=schedule.pk)
    assert schedule.repeats == 0
    assert schedule.last_run() is not None
    assert schedule.success() is True
    assert schedule.next_run < arrow.get(timezone.now()).replace(hours=+1)
    task = fetch(schedule.task)
    assert task is not None
    assert task.success is True
    assert task.result < 0
    # Once schedule with delete
    once_schedule = create_schedule('django_q.tests.tasks.word_multiply',
                                    2,
                                    word='django',
                                    schedule_type=Schedule.ONCE,
                                    repeats=-1,
                                    hook='django_q.tests.tasks.result'
                                    )
    assert hasattr(once_schedule, 'pk') is True
    # negative repeats
    always_schedule = create_schedule('django_q.tests.tasks.word_multiply',
                                      2,
                                      word='django',
                                      schedule_type=Schedule.DAILY,
                                      repeats=-1,
                                      hook='django_q.tests.tasks.result'
                                      )
    assert hasattr(always_schedule, 'pk') is True
    # Minute schedule
    minute_schedule = create_schedule('django_q.tests.tasks.word_multiply',
                                      2,
                                      word='django',
                                      schedule_type=Schedule.MINUTES,
                                      minutes=10)
    assert hasattr(minute_schedule, 'pk') is True
    # All other types
    for t in Schedule.TYPE:
        schedule = create_schedule('django_q.tests.tasks.word_multiply',
                                   2,
                                   word='django',
                                   schedule_type=t[0],
                                   repeats=1,
                                   hook='django_q.tests.tasks.result'
                                   )
        assert schedule is not None
        assert schedule.last_run() is None
        scheduler(broker=broker)
    # via model
    Schedule.objects.create(func='django_q.tests.tasks.word_multiply',
                            args='2',
                            kwargs='word="django"',
                            schedule_type=Schedule.DAILY
                            )
    # scheduler
    scheduler(broker=broker)
    # ONCE schedule should be deleted
    assert Schedule.objects.filter(pk=once_schedule.pk).exists() is False
    # Catch up On
    monkeypatch.setattr(Conf, 'CATCH_UP', True)
    now = timezone.now()
    schedule = create_schedule('django_q.tests.tasks.word_multiply',
                               2,
                               word='catch_up',
                               schedule_type=Schedule.HOURLY,
                               next_run=timezone.now() - timedelta(hours=12),
                               repeats=-1
                               )
    scheduler(broker=broker)
    schedule = Schedule.objects.get(pk=schedule.pk)
    assert schedule.next_run < now
    # Catch up off
    monkeypatch.setattr(Conf, 'CATCH_UP', False)
    scheduler(broker=broker)
    schedule = Schedule.objects.get(pk=schedule.pk)
    assert schedule.next_run > now
    # Done
    broker.delete_queue()
