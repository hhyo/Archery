from datetime import timedelta

# external
from blessed import Terminal

# django
from django.db import connection
from django.db.models import Sum, F
from django.utils import timezone
from django.utils.translation import ugettext as _

# local
from django_q.conf import Conf
from django_q.status import Stat
from django_q.brokers import get_broker
from django_q import models, VERSION


def monitor(run_once=False, broker=None):
    if not broker:
        broker = get_broker()
    term = Terminal()
    broker.ping()
    with term.fullscreen(), term.hidden_cursor(), term.cbreak():
        val = None
        start_width = int(term.width / 8)
        while val not in (u'q', u'Q',):
            col_width = int(term.width / 8)
            # In case of resize
            if col_width != start_width:
                print(term.clear())
                start_width = col_width
            print(term.move(0, 0) + term.black_on_green(term.center(_('Host'), width=col_width - 1)))
            print(term.move(0, 1 * col_width) + term.black_on_green(term.center(_('Id'), width=col_width - 1)))
            print(term.move(0, 2 * col_width) + term.black_on_green(term.center(_('State'), width=col_width - 1)))
            print(term.move(0, 3 * col_width) + term.black_on_green(term.center(_('Pool'), width=col_width - 1)))
            print(term.move(0, 4 * col_width) + term.black_on_green(term.center(_('TQ'), width=col_width - 1)))
            print(term.move(0, 5 * col_width) + term.black_on_green(term.center(_('RQ'), width=col_width - 1)))
            print(term.move(0, 6 * col_width) + term.black_on_green(term.center(_('RC'), width=col_width - 1)))
            print(term.move(0, 7 * col_width) + term.black_on_green(term.center(_('Up'), width=col_width - 1)))
            i = 2
            stats = Stat.get_all(broker=broker)
            print(term.clear_eos())
            for stat in stats:
                status = stat.status
                # color status
                if stat.status == Conf.WORKING:
                    status = term.green(str(Conf.WORKING))
                elif stat.status == Conf.STOPPING:
                    status = term.yellow(str(Conf.STOPPING))
                elif stat.status == Conf.STOPPED:
                    status = term.red(str(Conf.STOPPED))
                elif stat.status == Conf.IDLE:
                    status = str(Conf.IDLE)
                # color q's
                tasks = str(stat.task_q_size)
                if stat.task_q_size > 0:
                    tasks = term.cyan(str(stat.task_q_size))
                    if Conf.QUEUE_LIMIT and stat.task_q_size == Conf.QUEUE_LIMIT:
                        tasks = term.green(str(stat.task_q_size))
                results = stat.done_q_size
                if results > 0:
                    results = term.cyan(str(results))
                # color workers
                workers = len(stat.workers)
                if workers < Conf.WORKERS:
                    workers = term.yellow(str(workers))
                # format uptime
                uptime = (timezone.now() - stat.tob).total_seconds()
                hours, remainder = divmod(uptime, 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime = '%d:%02d:%02d' % (hours, minutes, seconds)
                # print to the terminal
                print(term.move(i, 0) + term.center(stat.host[:col_width - 1], width=col_width - 1))
                print(term.move(i, 1 * col_width) + term.center(stat.cluster_id, width=col_width - 1))
                print(term.move(i, 2 * col_width) + term.center(status, width=col_width - 1))
                print(term.move(i, 3 * col_width) + term.center(workers, width=col_width - 1))
                print(term.move(i, 4 * col_width) + term.center(tasks, width=col_width - 1))
                print(term.move(i, 5 * col_width) + term.center(results, width=col_width - 1))
                print(term.move(i, 6 * col_width) + term.center(stat.reincarnations, width=col_width - 1))
                print(term.move(i, 7 * col_width) + term.center(uptime, width=col_width - 1))
                i += 1
            # bottom bar
            i += 1
            queue_size = broker.queue_size()
            lock_size = broker.lock_size()
            if lock_size:
                queue_size = '{}({})'.format(queue_size, lock_size)
            print(term.move(i, 0) + term.white_on_cyan(term.center(broker.info(), width=col_width * 2)))
            print(term.move(i, 2 * col_width) + term.black_on_cyan(term.center(_('Queued'), width=col_width)))
            print(term.move(i, 3 * col_width) + term.white_on_cyan(term.center(queue_size, width=col_width)))
            print(term.move(i, 4 * col_width) + term.black_on_cyan(term.center(_('Success'), width=col_width)))
            print(term.move(i, 5 * col_width) + term.white_on_cyan(
                term.center(models.Success.objects.count(), width=col_width)))
            print(term.move(i, 6 * col_width) + term.black_on_cyan(term.center(_('Failures'), width=col_width)))
            print(term.move(i, 7 * col_width) + term.white_on_cyan(
                term.center(models.Failure.objects.count(), width=col_width)))
            # for testing
            if run_once:
                return Stat.get_all(broker=broker)
            print(term.move(i + 2, 0) + term.center(_('[Press q to quit]')))
            val = term.inkey(timeout=1)


def info(broker=None):
    if not broker:
        broker = get_broker()
    term = Terminal()
    broker.ping()
    stat = Stat.get_all(broker=broker)
    # general stats
    clusters = len(stat)
    workers = 0
    reincarnations = 0
    for cluster in stat:
        workers += len(cluster.workers)
        reincarnations += cluster.reincarnations
    # calculate tasks pm and avg exec time
    tasks_per = 0
    per = _('day')
    exec_time = 0
    last_tasks = models.Success.objects.filter(stopped__gte=timezone.now() - timedelta(hours=24))
    tasks_per_day = last_tasks.count()
    if tasks_per_day > 0:
        # average execution time over the last 24 hours
        if not connection.vendor == 'sqlite':
            exec_time = last_tasks.aggregate(time_taken=Sum(F('stopped') - F('started')))
            exec_time = exec_time['time_taken'].total_seconds() / tasks_per_day
        else:
            # can't sum timedeltas on sqlite
            for t in last_tasks:
                exec_time += t.time_taken()
            exec_time = exec_time / tasks_per_day
        # tasks per second/minute/hour/day in the last 24 hours
        if tasks_per_day > 24 * 60 * 60:
            tasks_per = tasks_per_day / (24 * 60 * 60)
            per = _('second')
        elif tasks_per_day > 24 * 60:
            tasks_per = tasks_per_day / (24 * 60)
            per = _('minute')
        elif tasks_per_day > 24:
            tasks_per = tasks_per_day / 24
            per = _('hour')
        else:
            tasks_per = tasks_per_day
    # print to terminal
    print(term.clear_eos())
    col_width = int(term.width / 6)
    print(term.black_on_green(
        term.center(
            _('-- {} {} on {}  --').format(Conf.PREFIX.capitalize(), '.'.join(str(v) for v in VERSION),
                                           broker.info()))))
    print(term.cyan(_('Clusters')) +
          term.move_x(1 * col_width) +
          term.white(str(clusters)) +
          term.move_x(2 * col_width) +
          term.cyan(_('Workers')) +
          term.move_x(3 * col_width) +
          term.white(str(workers)) +
          term.move_x(4 * col_width) +
          term.cyan(_('Restarts')) +
          term.move_x(5 * col_width) +
          term.white(str(reincarnations))
          )
    print(term.cyan(_('Queued')) +
          term.move_x(1 * col_width) +
          term.white(str(broker.queue_size())) +
          term.move_x(2 * col_width) +
          term.cyan(_('Successes')) +
          term.move_x(3 * col_width) +
          term.white(str(models.Success.objects.count())) +
          term.move_x(4 * col_width) +
          term.cyan(_('Failures')) +
          term.move_x(5 * col_width) +
          term.white(str(models.Failure.objects.count()))
          )
    print(term.cyan(_('Schedules')) +
          term.move_x(1 * col_width) +
          term.white(str(models.Schedule.objects.count())) +
          term.move_x(2 * col_width) +
          term.cyan(_('Tasks/{}'.format(per))) +
          term.move_x(3 * col_width) +
          term.white('{0:.2f}'.format(tasks_per)) +
          term.move_x(4 * col_width) +
          term.cyan(_('Avg time')) +
          term.move_x(5 * col_width) +
          term.white('{0:.4f}'.format(exec_time))
          )
    return True


def get_ids():
    # prints id (PID) of running clusters
    stat = Stat.get_all()
    if stat:
        for s in stat:
            print(s.cluster_id)
    else:
        print('No clusters appear to be running.')
    return True
