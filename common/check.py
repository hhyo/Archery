# -*- coding: UTF-8 -*-
import logging
import smtplib
import traceback

import MySQLdb
import simplejson as json
from django.http import HttpResponse

from common.utils.permission import superuser_required
from common.utils.sendmsg import MailSender
from sql.utils.inception import InceptionDao
from sql.utils.dao import Dao
from sql.models import Instance

logger = logging.getLogger('default')


# 检测inception配置
@superuser_required
def inception(request):
    result = {'status': 0, 'msg': 'ok', 'data': []}
    inception = InceptionDao()
    try:
        conn = MySQLdb.connect(host=inception.inception_host, port=inception.inception_port, charset='utf8')
        cur = conn.cursor()
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = '无法连接inception,\n{}'.format(str(e))
    else:
        cur.close()
        conn.close()
    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 检测email配置
@superuser_required
def email(request):
    result = {'status': 0, 'msg': 'ok', 'data': []}
    mail_sender = MailSender()
    try:
        if mail_sender.MAIL_SSL:
            server = smtplib.SMTP_SSL(mail_sender.MAIL_REVIEW_SMTP_SERVER,
                                      mail_sender.MAIL_REVIEW_SMTP_PORT)  # SMTP协议默认SSL端口是465
        else:
            server = smtplib.SMTP(mail_sender.MAIL_REVIEW_SMTP_SERVER,
                                  mail_sender.MAIL_REVIEW_SMTP_PORT)  # SMTP协议默认端口是25
        # 如果提供的密码为空，则不需要登录SMTP server
        if mail_sender.MAIL_REVIEW_FROM_PASSWORD != '':
            server.login(mail_sender.MAIL_REVIEW_FROM_ADDR, mail_sender.MAIL_REVIEW_FROM_PASSWORD)
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = '邮件服务配置不正确,\n{}'.format(str(e))
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
