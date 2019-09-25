import os
from time import sleep

import pytest
import redis

from django_q.brokers import get_broker, Broker
from django_q.conf import Conf
from django_q.humanhash import uuid


def test_broker(monkeypatch):
    broker = Broker()
    broker.enqueue('test')
    broker.dequeue()
    broker.queue_size()
    broker.lock_size()
    broker.purge_queue()
    broker.delete('id')
    broker.delete_queue()
    broker.acknowledge('test')
    broker.ping()
    broker.info()
    # stats
    assert broker.get_stat('test_1') is None
    broker.set_stat('test_1', 'test', 3)
    assert broker.get_stat('test_1') == 'test'
    assert broker.get_stats('test:*')[0] == 'test'
    # stats with no cache
    monkeypatch.setattr(Conf, 'CACHE', 'not_configured')
    broker.cache = broker.get_cache()
    assert broker.get_stat('test_1') is None
    broker.set_stat('test_1', 'test', 3)
    assert broker.get_stat('test_1') is None
    assert broker.get_stats('test:*') is None


def test_redis(monkeypatch):
    monkeypatch.setattr(Conf, 'DJANGO_REDIS', None)
    broker = get_broker()
    assert broker.ping() is True
    assert broker.info() is not None
    monkeypatch.setattr(Conf, 'REDIS', {'host': '127.0.0.1', 'port': 7799})
    broker = get_broker()
    with pytest.raises(Exception):
        broker.ping()


def test_custom(monkeypatch):
    monkeypatch.setattr(Conf, 'BROKER_CLASS', 'brokers.redis_broker.Redis')
    broker = get_broker()
    assert broker.ping() is True
    assert broker.info() is not None
    assert broker.__class__.__name__ == 'Redis'


def test_disque(monkeypatch):
    monkeypatch.setattr(Conf, 'DISQUE_NODES', ['127.0.0.1:7711'])
    # check broker
    broker = get_broker(list_key='disque_test')
    assert broker.ping() is True
    assert broker.info() is not None
    # clear before we start
    broker.delete_queue()
    # async_task
    broker.enqueue('test')
    assert broker.queue_size() == 1
    # dequeue
    task = broker.dequeue()[0]
    assert task[1] == 'test'
    broker.acknowledge(task[0])
    assert broker.queue_size() == 0
    # Retry test
    monkeypatch.setattr(Conf, 'RETRY', 1)
    broker.enqueue('test')
    assert broker.queue_size() == 1
    broker.dequeue()
    assert broker.queue_size() == 0
    sleep(1.5)
    assert broker.queue_size() == 1
    task = broker.dequeue()[0]
    assert broker.queue_size() == 0
    broker.acknowledge(task[0])
    sleep(1.5)
    assert broker.queue_size() == 0
    # delete job
    task_id = broker.enqueue('test')
    broker.delete(task_id)
    assert broker.dequeue() is None
    # fail
    task_id = broker.enqueue('test')
    broker.fail(task_id)
    # bulk test
    for i in range(5):
        broker.enqueue('test')
    monkeypatch.setattr(Conf, 'BULK', 5)
    monkeypatch.setattr(Conf, 'DISQUE_FASTACK', True)
    tasks = broker.dequeue()
    for task in tasks:
        assert task is not None
        broker.acknowledge(task[0])
    # test duplicate acknowledge
    broker.acknowledge(task[0])
    # delete queue
    broker.enqueue('test')
    broker.enqueue('test')
    broker.delete_queue()
    assert broker.queue_size() == 0
    # connection test
    monkeypatch.setattr(Conf, 'DISQUE_NODES', ['127.0.0.1:7798', '127.0.0.1:7799'])
    with pytest.raises(redis.exceptions.ConnectionError):
        broker.get_connection()


@pytest.mark.skipif(not os.getenv('IRON_MQ_TOKEN'),
                    reason="requires IronMQ credentials")
def test_ironmq(monkeypatch):
    monkeypatch.setattr(Conf, 'IRON_MQ', {'token': os.getenv('IRON_MQ_TOKEN'),
                                          'project_id': os.getenv('IRON_MQ_PROJECT_ID')})
    # check broker
    broker = get_broker(list_key=uuid()[0])
    assert broker.ping() is True
    assert broker.info() is not None
    # initialize the queue
    broker.enqueue('test')
    # clear before we start
    broker.purge_queue()
    assert broker.queue_size() == 0
    # async_task
    broker.enqueue('test')
    # dequeue
    task = broker.dequeue()[0]
    assert task[1] == 'test'
    broker.acknowledge(task[0])
    assert broker.dequeue() is None
    # Retry test
    # monkeypatch.setattr(Conf, 'RETRY', 1)
    # broker.async_task('test')
    # assert broker.dequeue() is not None
    # sleep(3)
    # assert broker.dequeue() is not None
    # task = broker.dequeue()[0]
    # assert len(task) > 0
    # broker.acknowledge(task[0])
    # sleep(3)
    # delete job
    task_id = broker.enqueue('test')
    broker.delete(task_id)
    assert broker.dequeue() is None
    # fail
    task_id = broker.enqueue('test')
    broker.fail(task_id)
    # bulk test
    for i in range(5):
        broker.enqueue('test')
    monkeypatch.setattr(Conf, 'BULK', 5)
    tasks = broker.dequeue()
    for task in tasks:
        assert task is not None
        broker.acknowledge(task[0])
    # duplicate acknowledge
    broker.acknowledge(task[0])
    # delete queue
    broker.enqueue('test')
    broker.enqueue('test')
    broker.purge_queue()
    assert broker.dequeue() is None
    broker.delete_queue()


@pytest.mark.skipif(not os.getenv('AWS_ACCESS_KEY_ID'),
                    reason="requires AWS credentials")
def canceled_sqs(monkeypatch):
    monkeypatch.setattr(Conf, 'SQS', {'aws_region': os.getenv('AWS_REGION'),
                                      'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
                                      'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY')})
    # check broker
    broker = get_broker(list_key=uuid()[0])
    assert broker.ping() is True
    assert broker.info() is not None
    assert broker.queue_size() == 0
    # async_task
    broker.enqueue('test')
    # dequeue
    task = broker.dequeue()[0]
    assert task[1] == 'test'
    broker.acknowledge(task[0])
    assert broker.dequeue() is None
    # Retry test
    monkeypatch.setattr(Conf, 'RETRY', 1)
    broker.enqueue('test')
    sleep(2)
    # Sometimes SQS is not linear
    task = broker.dequeue()
    if not task:
        pytest.skip('SQS being weird')
    task = task[0]
    assert len(task) > 0
    broker.acknowledge(task[0])
    sleep(2)
    # delete job
    monkeypatch.setattr(Conf, 'RETRY', 60)
    broker.enqueue('test')
    sleep(1)
    task = broker.dequeue()
    if not task:
        pytest.skip('SQS being weird')
    task_id = task[0][0]
    broker.delete(task_id)
    assert broker.dequeue() is None
    # fail
    broker.enqueue('test')
    while task is None:
        task = broker.dequeue()[0]
    broker.fail(task[0])
    # bulk test
    for i in range(10):
        broker.enqueue('test')
    monkeypatch.setattr(Conf, 'BULK', 12)
    tasks = broker.dequeue()
    for task in tasks:
        assert task is not None
        broker.acknowledge(task[0])
    # duplicate acknowledge
    broker.acknowledge(task[0])
    assert broker.lock_size() == 0
    # delete queue
    broker.enqueue('test')
    broker.purge_queue()
    broker.delete_queue()


@pytest.mark.django_db
def test_orm(monkeypatch):
    monkeypatch.setattr(Conf, 'ORM', 'default')
    # check broker
    broker = get_broker(list_key='orm_test')
    assert broker.ping() is True
    assert broker.info() is not None
    # clear before we start
    broker.delete_queue()
    # async_task
    broker.enqueue('test')
    assert broker.queue_size() == 1
    # dequeue
    task = broker.dequeue()[0]
    assert task[1] == 'test'
    broker.acknowledge(task[0])
    assert broker.queue_size() == 0
    # Retry test
    monkeypatch.setattr(Conf, 'RETRY', 1)
    broker.enqueue('test')
    assert broker.queue_size() == 1
    broker.dequeue()
    assert broker.queue_size() == 0
    sleep(1.5)
    assert broker.queue_size() == 1
    task = broker.dequeue()[0]
    assert broker.queue_size() == 0
    broker.acknowledge(task[0])
    sleep(1.5)
    assert broker.queue_size() == 0
    # delete job
    task_id = broker.enqueue('test')
    broker.delete(task_id)
    assert broker.dequeue() is None
    # fail
    task_id = broker.enqueue('test')
    broker.fail(task_id)
    # bulk test
    for i in range(5):
        broker.enqueue('test')
    monkeypatch.setattr(Conf, 'BULK', 5)
    tasks = broker.dequeue()
    assert broker.lock_size() == Conf.BULK
    for task in tasks:
        assert task is not None
        broker.acknowledge(task[0])
    # test lock size
    assert broker.lock_size() == 0
    # test duplicate acknowledge
    broker.acknowledge(task[0])
    # delete queue
    broker.enqueue('test')
    broker.enqueue('test')
    broker.delete_queue()
    assert broker.queue_size() == 0


@pytest.mark.django_db
def test_mongo(monkeypatch):
    monkeypatch.setattr(Conf, 'MONGO', {'host': '127.0.0.1', 'port': 27017})
    # check broker
    broker = get_broker(list_key='mongo_test')
    assert broker.ping() is True
    assert broker.info() is not None
    # clear before we start
    broker.delete_queue()
    # async_task
    broker.enqueue('test')
    assert broker.queue_size() == 1
    # dequeue
    task = broker.dequeue()[0]
    assert task[1] == 'test'
    broker.acknowledge(task[0])
    assert broker.queue_size() == 0
    # Retry test
    monkeypatch.setattr(Conf, 'RETRY', 1)
    broker.enqueue('test')
    assert broker.queue_size() == 1
    broker.dequeue()
    assert broker.queue_size() == 0
    sleep(1.5)
    assert broker.queue_size() == 1
    task = broker.dequeue()[0]
    assert broker.queue_size() == 0
    broker.acknowledge(task[0])
    sleep(1.5)
    assert broker.queue_size() == 0
    # delete job
    task_id = broker.enqueue('test')
    broker.delete(task_id)
    assert broker.dequeue() is None
    # fail
    task_id = broker.enqueue('test')
    broker.fail(task_id)
    # bulk test
    for i in range(5):
        broker.enqueue('test')
    tasks = []
    for i in range(5):
        tasks.append(broker.dequeue()[0])
    assert broker.lock_size() == 5
    for task in tasks:
        assert task is not None
        broker.acknowledge(task[0])
    # test lock size
    assert broker.lock_size() == 0
    # test duplicate acknowledge
    broker.acknowledge(task[0])
    # delete queue
    broker.enqueue('test')
    broker.enqueue('test')
    broker.purge_queue()
    broker.delete_queue()
    assert broker.queue_size() == 0
