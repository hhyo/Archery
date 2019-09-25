# Future
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from time import sleep

# external
import arrow
import ast
# Standard
import importlib
import signal
import socket
import traceback
# Django
from django import db
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from multiprocessing import Event, Process, Value, current_process

# Local
from django_q import tasks
from django_q.brokers import get_broker
from django_q.conf import Conf, logger, psutil, get_ppid, error_reporter
from django_q.models import Task, Success, Schedule
from django_q.queues import Queue
from django_q.signals import pre_execute
from django_q.signing import SignedPackage, BadSignature
from django_q.status import Stat, Status


class Cluster(object):
    def __init__(self, broker=None):
        self.broker = broker or get_broker()
        self.sentinel = None
        self.stop_event = None
        self.start_event = None
        self.pid = current_process().pid
        self.host = socket.gethostname()
        self.timeout = Conf.TIMEOUT
        signal.signal(signal.SIGTERM, self.sig_handler)
        signal.signal(signal.SIGINT, self.sig_handler)

    def start(self):
        # Start Sentinel
        self.stop_event = Event()
        self.start_event = Event()
        self.sentinel = Process(target=Sentinel,
                                args=(self.stop_event, self.start_event, self.broker, self.timeout))
        self.sentinel.start()
        logger.info(_('Q Cluster-{} starting.').format(self.pid))
        while not self.start_event.is_set():
            sleep(0.1)
        return self.pid

    def stop(self):
        if not self.sentinel.is_alive():
            return False
        logger.info(_('Q Cluster-{} stopping.').format(self.pid))
        self.stop_event.set()
        self.sentinel.join()
        logger.info(_('Q Cluster-{} has stopped.').format(self.pid))
        self.start_event = None
        self.stop_event = None
        return True

    def sig_handler(self, signum, frame):
        logger.debug(_('{} got signal {}').format(current_process().name,
                                                  Conf.SIGNAL_NAMES.get(signum, 'UNKNOWN')))
        self.stop()

    @property
    def stat(self):
        if self.sentinel:
            return Stat.get(self.pid)
        return Status(self.pid)

    @property
    def is_starting(self):
        return self.stop_event and self.start_event and not self.start_event.is_set()

    @property
    def is_running(self):
        return self.stop_event and self.start_event and self.start_event.is_set()

    @property
    def is_stopping(self):
        return self.stop_event and self.start_event and self.start_event.is_set() and self.stop_event.is_set()

    @property
    def has_stopped(self):
        return self.start_event is None and self.stop_event is None and self.sentinel


class Sentinel(object):
    def __init__(self, stop_event, start_event, broker=None, timeout=Conf.TIMEOUT, start=True):
        # Make sure we catch signals for the pool
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        self.pid = current_process().pid
        self.parent_pid = get_ppid()
        self.name = current_process().name
        self.broker = broker or get_broker()
        self.reincarnations = 0
        self.tob = timezone.now()
        self.stop_event = stop_event
        self.start_event = start_event
        self.pool_size = Conf.WORKERS
        self.pool = []
        self.timeout = timeout
        self.task_queue = Queue(maxsize=Conf.QUEUE_LIMIT) if Conf.QUEUE_LIMIT else Queue()
        self.result_queue = Queue()
        self.event_out = Event()
        self.monitor = None
        self.pusher = None
        if start:
            self.start()

    def start(self):
        self.broker.ping()
        self.spawn_cluster()
        self.guard()

    def status(self):
        if not self.start_event.is_set() and not self.stop_event.is_set():
            return Conf.STARTING
        elif self.start_event.is_set() and not self.stop_event.is_set():
            if self.result_queue.empty() and self.task_queue.empty():
                return Conf.IDLE
            return Conf.WORKING
        elif self.stop_event.is_set() and self.start_event.is_set():
            if self.monitor.is_alive() or self.pusher.is_alive() or len(self.pool) > 0:
                return Conf.STOPPING
            return Conf.STOPPED

    def spawn_process(self, target, *args):
        """
        :type target: function or class
        """
        p = Process(target=target, args=args)
        p.daemon = True
        if target == worker:
            p.daemon = Conf.DAEMONIZE_WORKERS
            p.timer = args[2]
            self.pool.append(p)
        p.start()
        return p

    def spawn_pusher(self):
        return self.spawn_process(pusher, self.task_queue, self.event_out, self.broker)

    def spawn_worker(self):
        self.spawn_process(worker, self.task_queue, self.result_queue, Value('f', -1), self.timeout)

    def spawn_monitor(self):
        return self.spawn_process(monitor, self.result_queue, self.broker)

    def reincarnate(self, process):
        """
        :param process: the process to reincarnate
        :type process: Process or None
        """
        db.connections.close_all()  # Close any old connections
        if process == self.monitor:
            self.monitor = self.spawn_monitor()
            logger.error(_("reincarnated monitor {} after sudden death").format(process.name))
        elif process == self.pusher:
            self.pusher = self.spawn_pusher()
            logger.error(_("reincarnated pusher {} after sudden death").format(process.name))
        else:
            self.pool.remove(process)
            self.spawn_worker()
            if self.timeout and int(process.timer.value) == 0:
                # only need to terminate on timeout, otherwise we risk destabilizing the queues
                process.terminate()
                logger.warn(_("reincarnated worker {} after timeout").format(process.name))
            elif int(process.timer.value) == -2:
                logger.info(_("recycled worker {}").format(process.name))
            else:
                logger.error(_("reincarnated worker {} after death").format(process.name))

        self.reincarnations += 1

    def spawn_cluster(self):
        self.pool = []
        Stat(self).save()
        db.connection.close()
        # spawn worker pool
        for __ in range(self.pool_size):
            self.spawn_worker()
        # spawn auxiliary
        self.monitor = self.spawn_monitor()
        self.pusher = self.spawn_pusher()
        # set worker cpu affinity if needed
        if psutil and Conf.CPU_AFFINITY:
            set_cpu_affinity(Conf.CPU_AFFINITY, [w.pid for w in self.pool])

    def guard(self):
        logger.info(_('{} guarding cluster at {}').format(current_process().name, self.pid))
        self.start_event.set()
        Stat(self).save()
        logger.info(_('Q Cluster-{} running.').format(self.parent_pid))
        scheduler(broker=self.broker)
        counter = 0
        cycle = Conf.GUARD_CYCLE  # guard loop sleep in seconds
        # Guard loop. Runs at least once
        while not self.stop_event.is_set() or not counter:
            # Check Workers
            for p in self.pool:
                # Are you alive?
                if not p.is_alive() or (self.timeout and p.timer.value == 0):
                    self.reincarnate(p)
                    continue
                # Decrement timer if work is being done
                if self.timeout and p.timer.value > 0:
                    p.timer.value -= cycle
            # Check Monitor
            if not self.monitor.is_alive():
                self.reincarnate(self.monitor)
            # Check Pusher
            if not self.pusher.is_alive():
                self.reincarnate(self.pusher)
            # Call scheduler once a minute (or so)
            counter += cycle
            if counter >= 30 and Conf.SCHEDULER:
                counter = 0
                scheduler(broker=self.broker)
            # Save current status
            Stat(self).save()
            sleep(cycle)
        self.stop()

    def stop(self):
        Stat(self).save()
        name = current_process().name
        logger.info(_('{} stopping cluster processes').format(name))
        # Stopping pusher
        self.event_out.set()
        # Wait for it to stop
        while self.pusher.is_alive():
            sleep(0.1)
            Stat(self).save()
        # Put poison pills in the queue
        for __ in range(len(self.pool)):
            self.task_queue.put('STOP')
        self.task_queue.close()
        # wait for the task queue to empty
        self.task_queue.join_thread()
        # Wait for all the workers to exit
        while len(self.pool):
            for p in self.pool:
                if not p.is_alive():
                    self.pool.remove(p)
            sleep(0.1)
            Stat(self).save()
        # Finally stop the monitor
        self.result_queue.put('STOP')
        self.result_queue.close()
        # Wait for the result queue to empty
        self.result_queue.join_thread()
        logger.info(_('{} waiting for the monitor.').format(name))
        # Wait for everything to close or time out
        count = 0
        if not self.timeout:
            self.timeout = 30
        while self.status() == Conf.STOPPING and count < self.timeout * 10:
            sleep(0.1)
            Stat(self).save()
            count += 1
        # Final status
        Stat(self).save()


def pusher(task_queue, event, broker=None):
    """
    Pulls tasks of the broker and puts them in the task queue
    :type task_queue: multiprocessing.Queue
    :type event: multiprocessing.Event
    """
    if not broker:
        broker = get_broker()
    logger.info(_('{} pushing tasks at {}').format(current_process().name, current_process().pid))
    while True:
        try:
            task_set = broker.dequeue()
        except Exception as e:
            logger.error(e, traceback.format_exc())
            # broker probably crashed. Let the sentinel handle it.
            sleep(10)
            break
        if task_set:
            for task in task_set:
                ack_id = task[0]
                # unpack the task
                try:
                    task = SignedPackage.loads(task[1])
                except (TypeError, BadSignature) as e:
                    logger.error(e, traceback.format_exc())
                    broker.fail(ack_id)
                    continue
                task['ack_id'] = ack_id
                task_queue.put(task)
            logger.debug(_('queueing from {}').format(broker.list_key))
        if event.is_set():
            break
    logger.info(_("{} stopped pushing tasks").format(current_process().name))


def monitor(result_queue, broker=None):
    """
    Gets finished tasks from the result queue and saves them to Django
    :type result_queue: multiprocessing.Queue
    """
    if not broker:
        broker = get_broker()
    name = current_process().name
    logger.info(_("{} monitoring at {}").format(name, current_process().pid))
    for task in iter(result_queue.get, 'STOP'):
        # save the result
        if task.get('cached', False):
            save_cached(task, broker)
        else:
            save_task(task, broker)
        # acknowledge result
        ack_id = task.pop('ack_id', False)
        if ack_id and (task['success'] or task.get('ack_failure', False)):
            broker.acknowledge(ack_id)
        # log the result
        if task['success']:
            # log success
            logger.info(_("Processed [{}]").format(task['name']))
        else:
            # log failure
            logger.error(_("Failed [{}] - {}").format(task['name'], task['result']))
    logger.info(_("{} stopped monitoring results").format(name))


def worker(task_queue, result_queue, timer, timeout=Conf.TIMEOUT):
    """
    Takes a task from the task queue, tries to execute it and puts the result back in the result queue
    :type task_queue: multiprocessing.Queue
    :type result_queue: multiprocessing.Queue
    :type timer: multiprocessing.Value
    """
    name = current_process().name
    logger.info(_('{} ready for work at {}').format(name, current_process().pid))
    task_count = 0
    # Start reading the task queue
    for task in iter(task_queue.get, 'STOP'):
        result = None
        timer.value = -1  # Idle
        task_count += 1
        # Get the function from the task
        logger.info(_('{} processing [{}]').format(name, task['name']))
        f = task['func']
        # if it's not an instance try to get it from the string
        if not callable(task['func']):
            try:
                module, func = f.rsplit('.', 1)
                m = importlib.import_module(module)
                f = getattr(m, func)
            except (ValueError, ImportError, AttributeError) as e:
                result = (e, False)
                if error_reporter:
                    error_reporter.report()
        # We're still going
        if not result:
            db.close_old_connections()
            timer_value = task['kwargs'].pop('timeout', timeout or 0)
            # signal execution
            pre_execute.send(sender="django_q", func=f, task=task)
            # execute the payload
            timer.value = timer_value  # Busy
            try:
                res = f(*task['args'], **task['kwargs'])
                result = (res, True)
            except Exception as e:
                result = ('{} : {}'.format(e, traceback.format_exc()), False)
                if error_reporter:
                    error_reporter.report()
        # Process result
        task['result'] = result[0]
        task['success'] = result[1]
        task['stopped'] = timezone.now()
        result_queue.put(task)
        timer.value = -1  # Idle
        # Recycle
        if task_count == Conf.RECYCLE:
            timer.value = -2  # Recycled
            break
    logger.info(_('{} stopped doing work').format(name))


def save_task(task, broker):
    """
    Saves the task package to Django or the cache
    """
    # SAVE LIMIT < 0 : Don't save success
    if not task.get('save', Conf.SAVE_LIMIT >= 0) and task['success']:
        return
    # enqueues next in a chain
    if task.get('chain', None):
        tasks.async_chain(task['chain'], group=task['group'], cached=task['cached'], sync=task['sync'], broker=broker)
    # SAVE LIMIT > 0: Prune database, SAVE_LIMIT 0: No pruning
    db.close_old_connections()
    try:
        if task['success'] and 0 < Conf.SAVE_LIMIT <= Success.objects.count():
            Success.objects.last().delete()
        # check if this task has previous results
        if Task.objects.filter(id=task['id'], name=task['name']).exists():
            existing_task = Task.objects.get(id=task['id'], name=task['name'])
            # only update the result if it hasn't succeeded yet
            if not existing_task.success:
                existing_task.stopped = task['stopped']
                existing_task.result = task['result']
                existing_task.success = task['success']
                existing_task.save()
        else:
            Task.objects.create(id=task['id'],
                                name=task['name'],
                                func=task['func'],
                                hook=task.get('hook'),
                                args=task['args'],
                                kwargs=task['kwargs'],
                                started=task['started'],
                                stopped=task['stopped'],
                                result=task['result'],
                                group=task.get('group'),
                                success=task['success']
                                )
    except Exception as e:
        logger.error(e)


def save_cached(task, broker):
    task_key = '{}:{}'.format(broker.list_key, task['id'])
    timeout = task['cached']
    if timeout is True:
        timeout = None
    try:
        group = task.get('group', None)
        iter_count = task.get('iter_count', 0)
        # if it's a group append to the group list
        if group:
            group_key = '{}:{}:keys'.format(broker.list_key, group)
            group_list = broker.cache.get(group_key) or []
            # if it's an iter group, check if we are ready
            if iter_count and len(group_list) == iter_count - 1:
                group_args = '{}:{}:args'.format(broker.list_key, group)
                # collate the results into a Task result
                results = [SignedPackage.loads(broker.cache.get(k))['result'] for k in group_list]
                results.append(task['result'])
                task['result'] = results
                task['id'] = group
                task['args'] = SignedPackage.loads(broker.cache.get(group_args))
                task.pop('iter_count', None)
                task.pop('group', None)
                if task.get('iter_cached', None):
                    task['cached'] = task.pop('iter_cached', None)
                    save_cached(task, broker=broker)
                else:
                    save_task(task, broker)
                broker.cache.delete_many(group_list)
                broker.cache.delete_many([group_key, group_args])
                return
            # save the group list
            group_list.append(task_key)
            broker.cache.set(group_key, group_list, timeout)
            # async_task next in a chain
            if task.get('chain', None):
                tasks.async_chain(task['chain'], group=group, cached=task['cached'], sync=task['sync'], broker=broker)
        # save the task
        broker.cache.set(task_key,
                         SignedPackage.dumps(task),
                         timeout)
    except Exception as e:
        logger.error(e)


def scheduler(broker=None):
    """
    Creates a task from a schedule at the scheduled time and schedules next run
    """
    if not broker:
        broker = get_broker()
    db.close_old_connections()
    try:
        for s in Schedule.objects.exclude(repeats=0).filter(next_run__lt=timezone.now()):
            args = ()
            kwargs = {}
            # get args, kwargs and hook
            if s.kwargs:
                try:
                    # eval should be safe here because dict()
                    kwargs = eval('dict({})'.format(s.kwargs))
                except SyntaxError:
                    kwargs = {}
            if s.args:
                args = ast.literal_eval(s.args)
                # single value won't eval to tuple, so:
                if type(args) != tuple:
                    args = (args,)
            q_options = kwargs.get('q_options', {})
            if s.hook:
                q_options['hook'] = s.hook
            # set up the next run time
            if not s.schedule_type == s.ONCE:
                next_run = arrow.get(s.next_run)
                while True:
                    if s.schedule_type == s.MINUTES:
                        next_run = next_run.replace(minutes=+(s.minutes or 1))
                    elif s.schedule_type == s.HOURLY:
                        next_run = next_run.replace(hours=+1)
                    elif s.schedule_type == s.DAILY:
                        next_run = next_run.replace(days=+1)
                    elif s.schedule_type == s.WEEKLY:
                        next_run = next_run.replace(weeks=+1)
                    elif s.schedule_type == s.MONTHLY:
                        next_run = next_run.replace(months=+1)
                    elif s.schedule_type == s.QUARTERLY:
                        next_run = next_run.replace(months=+3)
                    elif s.schedule_type == s.YEARLY:
                        next_run = next_run.replace(years=+1)
                    if Conf.CATCH_UP or next_run > arrow.utcnow():
                        break
                s.next_run = next_run.datetime
                s.repeats += -1
            # send it to the cluster
            q_options['broker'] = broker
            q_options['group'] = q_options.get('group', s.name or s.id)
            kwargs['q_options'] = q_options
            s.task = tasks.async_task(s.func, *args, **kwargs)
            # log it
            if not s.task:
                logger.error(
                    _('{} failed to create a task from schedule [{}]').format(current_process().name,
                                                                              s.name or s.id))
            else:
                logger.info(
                    _('{} created a task from schedule [{}]').format(current_process().name, s.name or s.id))
            # default behavior is to delete a ONCE schedule
            if s.schedule_type == s.ONCE:
                if s.repeats < 0:
                    s.delete()
                    continue
                # but not if it has a positive repeats
                s.repeats = 0
            # save the schedule
            s.save()
    except Exception as e:
        logger.error(e)


def set_cpu_affinity(n, process_ids, actual=not Conf.TESTING):
    """
    Sets the cpu affinity for the supplied processes.
    Requires the optional psutil module.
    :param int n: affinity
    :param list process_ids: a list of pids
    :param bool actual: Test workaround for Travis not supporting cpu affinity
    """
    # check if we have the psutil module
    if not psutil:
        logger.warning('Skipping cpu affinity because psutil was not found.')
        return
    # check if the platform supports cpu_affinity
    if actual and not hasattr(psutil.Process(process_ids[0]), 'cpu_affinity'):
        logger.warning('Faking cpu affinity because it is not supported on this platform')
        actual = False
    # get the available processors
    cpu_list = list(range(psutil.cpu_count()))
    # affinities of 0 or gte cpu_count, equals to no affinity
    if not n or n >= len(cpu_list):
        return
    # spread the workers over the available processors.
    index = 0
    for pid in process_ids:
        affinity = []
        for k in range(n):
            if index == len(cpu_list):
                index = 0
            affinity.append(cpu_list[index])
            index += 1
        if psutil.pid_exists(pid):
            p = psutil.Process(pid)
            if actual:
                p.cpu_affinity(affinity)
            logger.info(_('{} will use cpu {}').format(pid, affinity))
