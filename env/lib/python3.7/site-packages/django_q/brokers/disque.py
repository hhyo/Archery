import random
import redis
from django_q.brokers import Broker
from django_q.conf import Conf


class Disque(Broker):
    def enqueue(self, task):
        retry = Conf.RETRY if Conf.RETRY > 0 else '{} REPLICATE 1'.format(Conf.RETRY)
        return self.connection.execute_command(
            'ADDJOB {} {} 500 RETRY {}'.format(self.list_key, task, retry)).decode()

    def dequeue(self):
            tasks = self.connection.execute_command(
                'GETJOB COUNT {} TIMEOUT 1000 FROM {}'.format(Conf.BULK, self.list_key))
            if tasks:
                return [(t[1].decode(), t[2].decode()) for t in tasks]

    def queue_size(self):
        return self.connection.execute_command('QLEN {}'.format(self.list_key))

    def acknowledge(self, task_id):
        command = 'FASTACK' if Conf.DISQUE_FASTACK else 'ACKJOB'
        return self.connection.execute_command('{} {}'.format(command,task_id))

    def ping(self):
        return self.connection.execute_command('HELLO')[0] > 0

    def delete(self, task_id):
        return self.connection.execute_command('DELJOB {}'.format(task_id))

    def fail(self, task_id):
        return self.delete(task_id)

    def delete_queue(self):
        jobs = self.connection.execute_command('JSCAN QUEUE {}'.format(self.list_key))[1]
        if jobs:
            job_ids = ' '.join(jid.decode() for jid in jobs)
            self.connection.execute_command('DELJOB {}'.format(job_ids))
        return len(jobs)

    def info(self):
        if not self._info:
            info = self.connection.info('server')
            self._info= 'Disque {}'.format(info['disque_version'])
        return self._info

    @staticmethod
    def get_connection(list_key=Conf.PREFIX):
        # randomize nodes
        random.shuffle(Conf.DISQUE_NODES)
        # find one that works
        for node in Conf.DISQUE_NODES:
            host, port = node.split(':')
            kwargs = {'host': host, 'port': port}
            if Conf.DISQUE_AUTH:
                kwargs['password'] = Conf.DISQUE_AUTH
            redis_client = redis.Redis(**kwargs)
            redis_client.decode_responses = True
            try:
                redis_client.execute_command('HELLO')
                return redis_client
            except redis.exceptions.ConnectionError:
                continue
        raise redis.exceptions.ConnectionError('Could not connect to any Disque nodes')
