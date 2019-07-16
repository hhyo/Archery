# -*- coding: UTF-8 -*-
import logging
import traceback

import pymysql
import simplejson as json
from django.http import HttpResponse

from common.utils.permission import superuser_required
from sql.engines import get_engine
from sql.models import Instance
from common.utils.sendmsg import MsgSender

logger = logging.getLogger('default')


# 检测inception配置
@superuser_required
def inception(request):
    result = {'status': 0, 'msg': 'ok', 'data': []}
    inception_host = request.POST.get('inception_host', '')
    inception_port = request.POST.get('inception_port', '')
    inception_remote_backup_host = request.POST.get('inception_remote_backup_host', '')
    inception_remote_backup_port = request.POST.get('inception_remote_backup_port', '')
    inception_remote_backup_user = request.POST.get('inception_remote_backup_user', '')
    inception_remote_backup_password = request.POST.get('inception_remote_backup_password', '')

    try:
        conn = pymysql.connect(host=inception_host, port=int(inception_port), charset='utf8mb4')
        cur = conn.cursor()
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = '无法连接Inception\n{}'.format(str(e))
        return HttpResponse(json.dumps(result), content_type='application/json')
    else:
        cur.close()
        conn.close()

    try:
        conn = pymysql.connect(host=inception_remote_backup_host,
                               port=int(inception_remote_backup_port),
                               user=inception_remote_backup_user,
                               password=inception_remote_backup_password,
                               charset='utf8mb4')
        cur = conn.cursor()
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = '无法连接Inception备份库\n{}'.format(str(e))
    else:
        cur.close()
        conn.close()

    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 检测inception配置
@superuser_required
def go_inception(request):
    result = {'status': 0, 'msg': 'ok', 'data': []}
    go_inception_host = request.POST.get('go_inception_host', '')
    go_inception_port = request.POST.get('go_inception_port', '')
    inception_remote_backup_host = request.POST.get('inception_remote_backup_host', '')
    inception_remote_backup_port = request.POST.get('inception_remote_backup_port', '')
    inception_remote_backup_user = request.POST.get('inception_remote_backup_user', '')
    inception_remote_backup_password = request.POST.get('inception_remote_backup_password', '')

    try:
        conn = pymysql.connect(host=go_inception_host, port=int(go_inception_port), charset='utf8mb4')
        cur = conn.cursor()
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = '无法连接Inception\n{}'.format(str(e))
        return HttpResponse(json.dumps(result), content_type='application/json')
    else:
        cur.close()
        conn.close()

    try:
        conn = pymysql.connect(host=inception_remote_backup_host,
                               port=int(inception_remote_backup_port),
                               user=inception_remote_backup_user,
                               password=inception_remote_backup_password,
                               charset='utf8mb4')
        cur = conn.cursor()
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = '无法连接Inception备份库\n{}'.format(str(e))
    else:
        cur.close()
        conn.close()

    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 检测email配置
@superuser_required
def email(request):
    result = {'status': 0, 'msg': 'ok', 'data': []}
    mail = True if request.POST.get('mail', '') == 'true' else False
    mail_ssl = True if request.POST.get('mail_ssl') == 'true' else False
    mail_smtp_server = request.POST.get('mail_smtp_server', '')
    mail_smtp_port = request.POST.get('mail_smtp_port', '')
    mail_smtp_user = request.POST.get('mail_smtp_user', '')
    mail_smtp_password = request.POST.get('mail_smtp_password', '')
    if not mail:
        result['status'] = 1
        result['msg'] = '请先开启邮件通知！'
        # 返回结果
        return HttpResponse(json.dumps(result), content_type='application/json')
    try:
        mail_smtp_port = int(mail_smtp_port)
        if mail_smtp_port < 0:
            raise ValueError
    except ValueError:
        result['status'] = 1
        result['msg'] = '端口号只能为正整数'
        return HttpResponse(json.dumps(result), content_type='application/json')
    if not request.user.email:
        result['status'] = 1
        result['msg'] = '请先完善当前用户邮箱信息！'
        return HttpResponse(json.dumps(result), content_type='application/json')
    bd = 'Archery 邮件发送测试...'
    subj = 'Archery 邮件发送测试'
    sender = MsgSender(server=mail_smtp_server, port=mail_smtp_port, user=mail_smtp_user,
                       password=mail_smtp_password, ssl=mail_ssl)
    sender_response = sender.send_email(subj, bd, [request.user.email])
    if sender_response != 'success':
        result['status'] = 1
        result['msg'] = sender_response
        return HttpResponse(json.dumps(result), content_type='application/json')
    return HttpResponse(json.dumps(result), content_type='application/json')


# 检测实例配置
@superuser_required
def instance(request):
    result = {'status': 0, 'msg': 'ok', 'data': []}
    instance_id = request.POST.get('instance_id')
    instance = Instance.objects.get(id=instance_id)
    try:
        engine = get_engine(instance=instance)
        engine.get_connection()
    except Exception as e:
        result['status'] = 1
        result['msg'] = '无法连接实例,\n{}'.format(str(e))
    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')
