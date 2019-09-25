import socket
from django.utils import timezone
from django_q.brokers import get_broker
from django_q.conf import Conf, logger
from django_q.signing import SignedPackage, BadSignature


class Status(object):
    """Cluster status base class."""

    def __init__(self, pid):
        self.workers = []
        self.tob = None
        self.reincarnations = 0
        self.cluster_id = pid
        self.sentinel = 0
        self.status = Conf.STOPPED
        self.done_q_size = 0
        self.host = socket.gethostname()
        self.monitor = 0
        self.task_q_size = 0
        self.pusher = 0
        self.timestamp = timezone.now()


class Stat(Status):
    """Status object for Cluster monitoring."""

    def __init__(self, sentinel):
        super(Stat, self).__init__(sentinel.parent_pid or sentinel.pid)
        self.broker = sentinel.broker or get_broker()
        self.tob = sentinel.tob
        self.reincarnations = sentinel.reincarnations
        self.sentinel = sentinel.pid
        self.status = sentinel.status()
        self.done_q_size = 0
        self.task_q_size = 0
        if Conf.QSIZE:
            self.done_q_size = sentinel.result_queue.qsize()
            self.task_q_size = sentinel.task_queue.qsize()
        if sentinel.monitor:
            self.monitor = sentinel.monitor.pid
        if sentinel.pusher:
            self.pusher = sentinel.pusher.pid
        self.workers = [w.pid for w in sentinel.pool]

    def uptime(self):
        return (timezone.now() - self.tob).total_seconds()

    @property
    def key(self):
        """
        :return: redis key for this cluster statistic
        """
        return self.get_key(self.cluster_id)

    @staticmethod
    def get_key(cluster_id):
        """
        :param cluster_id: cluster ID
        :return: redis key for the cluster statistic
        """
        return '{}:{}'.format(Conf.Q_STAT, cluster_id)

    def save(self):
        try:
            self.broker.set_stat(self.key, SignedPackage.dumps(self, True), 3)
        except Exception as e:
            logger.error(e)

    def empty_queues(self):
        return self.done_q_size + self.task_q_size == 0

    @staticmethod
    def get(cluster_id, broker=None):
        """
        gets the current status for the cluster
        :param cluster_id: id of the cluster
        :return: Stat or Status
        """
        if not broker:
            broker = get_broker()
        pack = broker.get_stat(Stat.get_key(cluster_id))
        if pack:
            try:
                return SignedPackage.loads(pack)
            except BadSignature:
                return None
        return Status(cluster_id)

    @staticmethod
    def get_all(broker=None):
        """
        Get the status for all currently running clusters with the same prefix
        and secret key.
        :return: list of type Stat
        """
        if not broker:
            broker = get_broker()
        stats = []
        packs = broker.get_stats('{}:*'.format(Conf.Q_STAT)) or []
        for pack in packs:
            try:
                stats.append(SignedPackage.loads(pack))
            except BadSignature:
                continue
        return stats

    def __getstate__(self):
        # Don't pickle the redis connection
        state = dict(self.__dict__)
        del state['broker']
        return state
