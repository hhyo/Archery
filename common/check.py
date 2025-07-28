# -*- coding: UTF-8 -*-
import logging
import traceback

import MySQLdb
import simplejson as json
from django.http import HttpResponse
from paramiko import Transport, SFTPClient
import oss2
import os

from common.utils.permission import superuser_required
from sql.engines import get_engine
from sql.models import Instance
from common.utils.sendmsg import MsgSender

logger = logging.getLogger("default")


# 检测inception配置
@superuser_required
def go_inception(request):
    result = {"status": 0, "msg": "ok", "data": []}
    go_inception_host = request.POST.get("go_inception_host", "")
    go_inception_port = request.POST.get("go_inception_port", "")
    go_inception_user = request.POST.get("go_inception_user", "")
    go_inception_password = request.POST.get("go_inception_password", "")
    inception_remote_backup_host = request.POST.get("inception_remote_backup_host", "")
    inception_remote_backup_port = request.POST.get("inception_remote_backup_port", "")
    inception_remote_backup_user = request.POST.get("inception_remote_backup_user", "")
    inception_remote_backup_password = request.POST.get(
        "inception_remote_backup_password", ""
    )

    try:
        conn = MySQLdb.connect(
            host=go_inception_host,
            port=int(go_inception_port),
            user=go_inception_user,
            password=go_inception_password,
            charset="utf8mb4",
            connect_timeout=5,
        )
        cur = conn.cursor()
    except Exception as e:
        logger.error(traceback.format_exc())
        result["status"] = 1
        result["msg"] = "无法连接goInception\n{}".format(str(e))
        return HttpResponse(json.dumps(result), content_type="application/json")
    else:
        cur.close()
        conn.close()

    try:
        conn = MySQLdb.connect(
            host=inception_remote_backup_host,
            port=int(inception_remote_backup_port),
            user=inception_remote_backup_user,
            password=inception_remote_backup_password,
            charset="utf8mb4",
            connect_timeout=5,
        )
        cur = conn.cursor()
    except Exception as e:
        logger.error(traceback.format_exc())
        result["status"] = 1
        result["msg"] = "无法连接goInception备份库\n{}".format(str(e))
    else:
        cur.close()
        conn.close()

    # 返回结果
    return HttpResponse(json.dumps(result), content_type="application/json")


# 检测email配置
@superuser_required
def email(request):
    result = {"status": 0, "msg": "ok", "data": []}
    mail = True if request.POST.get("mail", "") == "true" else False
    mail_ssl = True if request.POST.get("mail_ssl") == "true" else False
    mail_smtp_server = request.POST.get("mail_smtp_server", "")
    mail_smtp_port = request.POST.get("mail_smtp_port", "")
    mail_smtp_user = request.POST.get("mail_smtp_user", "")
    mail_smtp_password = request.POST.get("mail_smtp_password", "")
    if not mail:
        result["status"] = 1
        result["msg"] = "请先开启邮件通知！"
        # 返回结果
        return HttpResponse(json.dumps(result), content_type="application/json")
    try:
        mail_smtp_port = int(mail_smtp_port)
        if mail_smtp_port < 0:
            raise ValueError
    except ValueError:
        result["status"] = 1
        result["msg"] = "端口号只能为正整数"
        return HttpResponse(json.dumps(result), content_type="application/json")
    if not request.user.email:
        result["status"] = 1
        result["msg"] = "请先完善当前用户邮箱信息！"
        return HttpResponse(json.dumps(result), content_type="application/json")
    bd = "Archery 邮件发送测试..."
    subj = "Archery 邮件发送测试"
    sender = MsgSender(
        server=mail_smtp_server,
        port=mail_smtp_port,
        user=mail_smtp_user,
        password=mail_smtp_password,
        ssl=mail_ssl,
    )
    sender_response = sender.send_email(subj, bd, [request.user.email])
    if sender_response != "success":
        result["status"] = 1
        result["msg"] = sender_response
        return HttpResponse(json.dumps(result), content_type="application/json")
    return HttpResponse(json.dumps(result), content_type="application/json")


# 检测实例配置
@superuser_required
def instance(request):
    result = {"status": 0, "msg": "ok", "data": []}
    instance_id = request.POST.get("instance_id")
    instance = Instance.objects.get(id=instance_id)
    try:
        engine = get_engine(instance=instance)
        test_result = engine.test_connection()
        if test_result.error:
            result["status"] = 1
            result["msg"] = "无法连接实例,\n{}".format(test_result.error)
    except Exception as e:
        result["status"] = 1
        result["msg"] = "无法连接实例,\n{}".format(str(e))
    # 返回结果
    return HttpResponse(json.dumps(result), content_type="application/json")


@superuser_required
def file_storage_connect(request):
    result = {"status": 0, "msg": "ok", "data": []}
    storage_type = request.POST.get("storage_type")
    # 检查是否存在该变量
    max_export_rows = request.POST.get("max_export_rows", "10000")
    max_export_exec_time = request.POST.get("max_export_exec_time", "60")
    # 若变量已经定义，检查是否为空
    max_export_rows = max_export_rows if max_export_rows else "10000"
    max_export_exec_time = max_export_exec_time if max_export_exec_time else "60"
    check_list = {
        "max_export_rows": max_export_rows,
        "max_export_exec_time": max_export_exec_time,
    }
    try:
        # 遍历字典，判断是否只有数字
        for key, value in check_list.items():
            if not value.isdigit():
                raise TypeError(f"Value: {key} \nmust be an integer.")
    except TypeError as e:
        result["status"] = 1
        result["msg"] = "参数类型错误,\n{}".format(str(e))

    if storage_type == "sftp":
        sftp_host = request.POST.get("sftp_host")
        sftp_port = int(request.POST.get("sftp_port"))
        sftp_user = request.POST.get("sftp_user")
        sftp_password = request.POST.get("sftp_password")
        sftp_path = request.POST.get("sftp_path")

        try:
            with Transport((sftp_host, sftp_port)) as transport:
                transport.connect(username=sftp_user, password=sftp_password)
                # 创建 SFTPClient
                sftp = SFTPClient.from_transport(transport)
                remote_path = sftp_path
                try:
                    sftp.listdir(remote_path)
                except FileNotFoundError:
                    raise Exception(f"SFTP 远程路径 '{remote_path}' 不存在")

        except Exception as e:
            result["status"] = 1
            result["msg"] = "无法连接,\n{}".format(str(e))
    elif storage_type == "oss":
        access_key_id = request.POST.get("access_key_id")
        access_key_secret = request.POST.get("access_key_secret")
        endpoint = request.POST.get("endpoint")
        bucket_name = request.POST.get("bucket_name")
        try:
            # 创建 OSS 认证
            auth = oss2.Auth(access_key_id, access_key_secret)
            # 创建 OSS Bucket 对象
            bucket = oss2.Bucket(auth, endpoint, bucket_name)

            # 判断配置的 Bucket 是否存在
            try:
                bucket.get_bucket_info()
            except oss2.exceptions.NoSuchBucket:
                raise Exception(f"OSS 存储桶 '{bucket_name}' 不存在")

        except Exception as e:
            result["status"] = 1
            result["msg"] = "无法连接,\n{}".format(str(e))
    elif storage_type == "local":
        local_path = r"{}".format(request.POST.get("local_path"))
        try:
            if not os.path.exists(local_path):
                raise FileNotFoundError(
                    f"Destination directory '{local_path}' not found."
                )
        except Exception as e:
            result["status"] = 1
            result["msg"] = "本地路径不存在,\n{}".format(str(e))

    return HttpResponse(json.dumps(result), content_type="application/json")

