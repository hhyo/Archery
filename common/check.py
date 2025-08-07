# -*- coding: UTF-8 -*-
import logging
import traceback

import MySQLdb
import simplejson as json
from django.http import HttpResponse

from common.utils.permission import superuser_required
from sql.engines import get_engine
from sql.models import Instance
from common.utils.sendmsg import MsgSender
from sql.storage import DynamicStorage

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

    # 检查 max_export_rows 参数
    max_export_rows = request.POST.get("max_export_rows", "10000")
    max_export_rows = max_export_rows if max_export_rows else "10000"
    try:
        if not max_export_rows.isdigit():
            raise TypeError("max_export_rows 必须是整数")
    except TypeError as e:
        result["status"] = 1
        result["msg"] = f"参数类型错误: {str(e)}"
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 根据存储类型获取对应的自定义参数
    custom_param_key = f"{storage_type}_custom_params"
    custom_params_str = request.POST.get(f"{custom_param_key}", "").strip()
    custom_params = {}
    if custom_params_str:
        try:
            custom_params = json.loads(custom_params_str)
        except json.JSONDecodeError:
            result["status"] = 1
            result["msg"] = "自定义参数格式错误，请输入有效的JSON格式"
            return HttpResponse(json.dumps(result), content_type="application/json")

    # 构建配置字典
    config_dict = {
        "storage_type": storage_type,
        "sftp_host": request.POST.get("sftp_host", ""),
        "sftp_port": request.POST.get("sftp_port", 22),
        "sftp_user": request.POST.get("sftp_user", ""),
        "sftp_password": request.POST.get("sftp_password", ""),
        "sftp_path": request.POST.get("sftp_path", ""),
        "sftp_custom_params": request.POST.get("sftp_custom_params", ""),
        "s3c_access_key_id": request.POST.get("s3c_access_key_id", ""),
        "s3c_access_key_secret": request.POST.get("s3c_access_key_secret", ""),
        "s3c_endpoint": request.POST.get("s3c_endpoint", ""),
        "s3c_bucket_name": request.POST.get("s3c_bucket_name", ""),
        "s3c_region": request.POST.get("s3c_region", ""),
        "s3c_path": request.POST.get("s3c_path", ""),
        "s3c_custom_params": request.POST.get("s3c_custom_params", ""),
        "azure_account_name": request.POST.get("azure_account_name", ""),
        "azure_account_key": request.POST.get("azure_account_key", ""),
        "azure_container": request.POST.get("azure_container", ""),
        "azure_path": request.POST.get("azure_path", ""),
        "azure_custom_params": request.POST.get("azure_custom_params", ""),
    }

    try:
        # 使用统一接口测试连接
        storage = DynamicStorage(config_dict=config_dict)
        success, message = storage.check_connection()

        if not success:
            result["status"] = 1
            result["msg"] = "存储连接测试失败"
            # 记录详细错误信息到日志
            logging.error(f"存储连接测试失败")
            # logging.error(f"存储连接测试失败: {message}")
        else:
            # 记录成功信息到日志
            logging.info(f"存储连接测试成功")
            # logging.info(f"存储连接测试成功: {message}")

    except Exception as e:
        result["status"] = 1
        result["msg"] = "存储连接测试异常"
        error_msg = f"连接测试异常: {str(e)}"
        logging.error(error_msg, exc_info=True)

    return HttpResponse(json.dumps(result), content_type="application/json")
