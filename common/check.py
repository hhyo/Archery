# -*- coding: UTF-8 -*-
import logging
import smtplib
import traceback

import MySQLdb
import simplejson as json
from django.http import HttpResponse
from email.header import Header
from email.mime.text import MIMEText

from common.utils.permission import superuser_required
from sql.utils.dao import Dao
from sql.models import Instance, Users

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
        conn = MySQLdb.connect(host=inception_host, port=int(inception_port), charset='utf8')
        cur = conn.cursor()
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = '无法连接inception\n{}'.format(str(e))
    else:
        cur.close()
        conn.close()

    try:
        conn = MySQLdb.connect(host=inception_remote_backup_host,
                               port=int(inception_remote_backup_port),
                               user=inception_remote_backup_user,
                               password=inception_remote_backup_password,
                               charset='utf8')
        cur = conn.cursor()
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = '无法连接inception备份库\n{}'.format(str(e))
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

    if mail:
        try:
            if mail_ssl:
                server = smtplib.SMTP_SSL(mail_smtp_server, mail_smtp_port)  # SMTP协议默认SSL端口是465
            else:
                server = smtplib.SMTP(mail_smtp_server, mail_smtp_port)  # SMTP协议默认端口是25
            # 如果提供的密码为空，则不需要登录SMTP server
            if mail_smtp_password:
                server.login(mail_smtp_user, mail_smtp_password)
            # 获取当前用户邮箱，发送测试邮件
            if request.user.email:
                message = MIMEText('Archery 邮件发送测试...', 'plain', 'utf-8')
                message['From'] = Header("Archery", 'utf-8')
                message['To'] = Header("测试", 'utf-8')
                subject = 'Archery 邮件发送测试...'
                message['Subject'] = Header(subject, 'utf-8')
                server.sendmail(mail_smtp_user, request.user.email, message.as_string())
            else:
                result['status'] = 1
                result['msg'] = '请先完善当前用户邮箱信息！'
        except Exception as e:
            logger.error(traceback.format_exc())
            result['status'] = 1
            result['msg'] = '邮件服务配置不正确,\n{}'.format(str(e))
    else:
        result['status'] = 1
        result['msg'] = '请先开启邮件通知！'
    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 检测实例配置
@superuser_required
def instance(request):
    result = {'status': 0, 'msg': 'ok', 'data': []}
    instance_id = request.POST.get('instance_id')
    instance_name = Instance.objects.get(id=instance_id).instance_name
    dao = Dao(instance_name=instance_name)
    try:
        conn = MySQLdb.connect(host=dao.host, port=dao.port, user=dao.user, passwd=dao.password, charset='utf8')
        cursor = conn.cursor()
        sql = "select 1"
        cursor.execute(sql)
    except Exception as e:
        result['status'] = 1
        result['msg'] = '无法连接实例{},\n{}'.format(instance_name, str(e))
    else:
        cursor.close()
        conn.close()
    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')
