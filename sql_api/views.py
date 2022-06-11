# -*- coding: UTF-8 -*-
import django_q
import pkg_resources
import platform
import sys
import MySQLdb

from common.config import SysConfig
from django.db import connection
from django_redis import get_redis_connection
from django.http import JsonResponse
from django_q.status import Stat
from django_q.models import Success, Failure
from django_q.brokers import get_broker
from django.utils import timezone

from common.utils.aes_decryptor import Prpcrypt
from common.utils.permission import superuser_required
import archery
from sql.models import Instance
from mirage.tools import Migrator


def info(request):
    # 获取django_q信息
    django_q_version = '.'.join(str(i) for i in django_q.VERSION)

    system_info = {
        'archery': {
            'version': archery.display_version
        },
        'django_q': {
            'version': django_q_version,
        }
    }
    return JsonResponse(system_info)


@superuser_required
def debug(request):
    # 获取完整信息
    full = request.GET.get('full')

    # 系统配置
    sys_config = SysConfig().sys_config
    # 敏感信息处理
    secret_keys = [
        'inception_remote_backup_password',
        'ding_app_secret',
        'feishu_app_secret',
        'mail_smtp_password'
    ]
    sys_config.update({k: "******" for k in secret_keys})

    # MySQL信息
    cursor = connection.cursor()
    mysql_info = {
        'mysql_server_info': cursor.db.mysql_server_info,
        'timezone_name': cursor.db.timezone_name
    }

    # Redis信息
    try:
        redis_conn = get_redis_connection("default")
        full_redis_info = redis_conn.info()
        redis_info = {
            'redis_version': full_redis_info.get('redis_version'),
            'redis_mode': full_redis_info.get('redis_mode'),
            'role': full_redis_info.get('role'),
            'maxmemory_human': full_redis_info.get('maxmemory_human'),
            'used_memory_human': full_redis_info.get('used_memory_human'),
        }
    except Exception as e:
        redis_info = f'获取Redis信息报错:{e}'
        full_redis_info = redis_info

    # django_q
    try:
        django_q_version = '.'.join(str(i) for i in django_q.VERSION)
        broker = get_broker()
        stats = Stat.get_all(broker=broker)
        queue_size = broker.queue_size()
        lock_size = broker.lock_size()
        if lock_size:
            queue_size = '{}({})'.format(queue_size, lock_size)
        q_broker_stats = {
            'info': broker.info(),
            'Queued': queue_size,
            'Success': Success.objects.count(),
            'Failures': Failure.objects.count(),
        }
        q_cluster_stats = []
        for stat in stats:
            # format uptime
            uptime = (timezone.now() - stat.tob).total_seconds()
            hours, remainder = divmod(uptime, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime = '%d:%02d:%02d' % (hours, minutes, seconds)
            q_cluster_stats.append({
                'host': stat.host,
                'cluster_id': stat.cluster_id,
                'state': stat.status,
                'pool': len(stat.workers),
                'tq': stat.task_q_size,
                'rq': stat.done_q_size,
                'rc': stat.reincarnations,
                'up': uptime
            })
        django_q_info = {
            'version': django_q_version,
            'conf': django_q.conf.Conf.conf,
            'q_cluster_stats': q_cluster_stats if q_cluster_stats else '没有正在运行的集群信息，请检查django_q状态',
            'q_broker_stats': q_broker_stats
        }
    except Exception as e:
        django_q_info = f'获取django_q信息报错:{e}'

    # Inception和goInception信息
    go_inception_host = sys_config.get('go_inception_host')
    go_inception_port = sys_config.get('go_inception_port', 0)
    inception_remote_backup_host = sys_config.get('inception_remote_backup_host', '')
    inception_remote_backup_port = sys_config.get('inception_remote_backup_port', '')
    inception_remote_backup_user = sys_config.get('inception_remote_backup_user', '')
    inception_remote_backup_password = sys_config.get('inception_remote_backup_password', '')

    # goInception
    try:
        goinc_conn = MySQLdb.connect(host=go_inception_host, port=int(go_inception_port),
                                     connect_timeout=1, cursorclass=MySQLdb.cursors.DictCursor)
        cursor = goinc_conn.cursor()
        cursor.execute('inception get variables')
        rows = cursor.fetchall()
        full_goinception_info = dict()
        for row in rows:
            full_goinception_info[row.get('Variable_name')] = row.get('Value')
        goinception_info = {
            'version': full_goinception_info.get('version'),
            'max_allowed_packet': full_goinception_info.get('max_allowed_packet'),
            'lang': full_goinception_info.get('lang'),
            'osc_on': full_goinception_info.get('osc_on'),
            'osc_bin_dir': full_goinception_info.get('osc_bin_dir'),
            'ghost_on': full_goinception_info.get('ghost_on'),
        }
    except Exception as e:
        goinception_info = f'获取goInception信息报错:{e}'
        full_goinception_info = goinception_info

    # 备份库
    try:
        bak_conn = MySQLdb.connect(host=inception_remote_backup_host,
                                   port=int(inception_remote_backup_port),
                                   user=inception_remote_backup_user,
                                   password=inception_remote_backup_password,
                                   connect_timeout=1)
        cursor = bak_conn.cursor()
        cursor.execute('select 1;')
        backup_info = 'normal'
    except Exception as e:
        backup_info = f'无法连接goInception备份库\n{e}'

    # PACKAGES
    installed_packages = pkg_resources.working_set
    installed_packages_list = sorted([
        "%s==%s" % (i.key, i.version) for i in installed_packages])

    # 最终集合
    system_info = {
        'archery': {
            'version': archery.display_version
        },
        'django_q': django_q_info,
        'inception': {
            'goinception_info': full_goinception_info if full else goinception_info,
            'backup_info': backup_info
        },
        'runtime_info': {
            'python_version': platform.python_version(),
            'mysql_info': mysql_info,
            'redis_info': full_redis_info if full else redis_info,
            'sys_argv': sys.argv,
            'platform': platform.uname()
        },
        'sys_config': sys_config,
        'packages': installed_packages_list
    }
    return JsonResponse(system_info)


@superuser_required
def mirage(request):
    """迁移加密的Instance数据，保留一定版本后删除"""
    try:
        pc = Prpcrypt()
        mg_user = Migrator(app="sql", model="Instance", field="user")
        mg_password = Migrator(app="sql", model="Instance", field="password")
        # 还原密码
        for ins in Instance.objects.all():
            # 忽略解密错误的数据(本身为异常数据)
            try:
                Instance(pk=ins.pk, password=pc.decrypt(ins.password)).save(update_fields=['password'])
            except:
                pass
        # 使用django-mirage-field重新加密
        mg_user.encrypt()
        mg_password.encrypt()
        return JsonResponse({"msg": "ok"})
    except Exception as msg:
        return JsonResponse({"msg": f"{msg}"})
