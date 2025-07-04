# -*- coding: UTF-8 -*-
import logging
import re
import traceback
import os
import tempfile
import csv
from io import BytesIO
import hashlib
import shutil
import datetime
import xml.etree.ElementTree as ET
import zipfile
import sqlparse
from threading import Thread
import queue
import time

import MySQLdb
import cx_Oracle
import simplejson as json
from paramiko import Transport, SFTPClient
import oss2
import pandas as pd
from django.http import HttpResponse
from urllib.parse import quote

from sql.models import SqlWorkflow, AuditEntry, Config
from . import EngineBase
from .models import ReviewSet, ReviewResult


logger = logging.getLogger("default")


class TimeoutException(Exception):
    pass


class OffLineDownLoad(EngineBase):
    def execute_offline_download(self, workflow):
        if workflow.is_offline_export == "yes":
            # 创建一个临时目录用于存放文件
            temp_dir = tempfile.mkdtemp()
            # 获取系统配置
            config = get_sys_config()
            # 先进行 max_export_exec_time 变量的判断是否存在以及是否为空,默认值60
            timeout_str = config.get("max_export_exec_time", "60")
            timeout = int(timeout_str) if timeout_str else 60
            storage_type = config["sqlfile_storage"]
            # 获取前端提交的 SQL 和其他工单信息
            full_sql = workflow.sqlworkflowcontent.sql_content
            full_sql = sqlparse.format(full_sql, strip_comments=True)
            full_sql = sqlparse.split(full_sql)[0]
            sql = full_sql.strip()
            instance = workflow.instance
            if instance.db_type == 'mysql':
                host, port, user, password = self.remote_instance_conn(instance)
            elif instance.db_type == 'oracle':
                host, port, user, password = instance.host, instance.port, instance.user, instance.password
                service_name = instance.service_name
            execute_result = ReviewSet(full_sql=sql)
            # 定义数据库连接
            if instance.db_type == 'mysql':
                conn = MySQLdb.connect(
                    host=host,
                    port=port,
                    user=user,
                    passwd=password,
                    db=workflow.db_name,
                    charset='utf8mb4'
                )
            elif instance.db_type == 'oracle':
                dsn = cx_Oracle.makedsn(host, port, service_name=service_name)
                conn = cx_Oracle.connect(
                    user=user,
                    password=password,
                    dsn=dsn,
                    encoding="UTF-8",
                    nencoding="UTF-8"
                )

            start_time = time.time()
            try:
                check_result = execute_check_sql(conn, sql, config, workflow)
                if isinstance(check_result, Exception):
                    raise check_result
            except Exception as e:
                execute_result.rows = [
                    ReviewResult(
                        stage="Execute failed",
                        error=1,
                        errlevel=2,
                        stagestatus="异常终止",
                        errormessage=f"{e}",
                        sql=full_sql,
                    )
                ]
                execute_result.error = e
                return execute_result

            try:
                # 执行 SQL 查询
                results = self.execute_with_timeout(
                    conn, workflow.sqlworkflowcontent.sql_content, timeout
                )
                if results:
                    columns = results["columns"]
                    result = results["data"]

                # 保存查询结果为 CSV or JSON or XML or XLSX or SQL 文件
                get_format_type = workflow.export_format
                file_name = save_to_format_file(
                    get_format_type, result, workflow, columns, temp_dir
                )

                # 将导出的文件上传至 OSS 或 FTP 或 本地保存
                upload_file_to_storage(file_name, storage_type, temp_dir)

                end_time = time.time()  # 记录结束时间
                elapsed_time = round(end_time - start_time, 3)
                execute_result.rows = [
                    ReviewResult(
                        stage="Executed",
                        errlevel=0,
                        stagestatus="执行正常",
                        errormessage=f"保存文件: {file_name}",
                        sql=full_sql,
                        execute_time=elapsed_time,
                        affected_rows=check_result,
                    )
                ]

                change_workflow = SqlWorkflow.objects.get(id=workflow.id)
                change_workflow.file_name = file_name
                change_workflow.save()

                return execute_result
            except Exception as e:
                # 返回工单执行失败的状态和错误信息
                execute_result.rows = [
                    ReviewResult(
                        stage="Execute failed",
                        error=1,
                        errlevel=2,
                        stagestatus="异常终止",
                        errormessage=f"{e}",
                        sql=full_sql,
                    )
                ]
                execute_result.error = e
                return execute_result
            finally:
                # 清理本地文件和临时目录
                clean_local_files(temp_dir)
                # 关闭游标和数据库连接
                conn.close()

    @staticmethod
    def execute_query(conn, sql):
        try:
            cursor = conn.cursor()
            cursor.execute(sql.rstrip(';'))
            columns = [column[0] for column in cursor.description]
            result = {"columns": columns, "data": cursor.fetchall()}
            cursor.close()
            return result
        except Exception as e:
            raise Exception(f"Query execution failed: {e}")

    def worker(self, conn, sql, result_queue):
        try:
            result = self.execute_query(conn, sql)
            result_queue.put(result)
        except Exception as e:
            result_queue.put(e)

    def execute_with_timeout(self, conn, sql, timeout):
        result_queue = queue.Queue()
        thread = Thread(target=self.worker, args=(conn, sql, result_queue))
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            thread.join()
            raise TimeoutException(
                f"Query execution timed out after {timeout} seconds."
            )
        else:
            result = result_queue.get()
            if isinstance(result, Exception):
                raise result
            else:
                return result


def get_sys_config():
    all_config = Config.objects.all().values("item", "value")
    sys_config = {}
    for items in all_config:
        sys_config[items["item"]] = items["value"]
    return sys_config


def save_to_format_file(
    format_type=None, result=None, workflow=None, columns=None, temp_dir=None
):
    # 生成唯一的文件名（包含工单ID、日期和随机哈希值）
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    hash_value = hashlib.sha256(os.urandom(32)).hexdigest()[:8]  # 使用前8位作为哈希值
    base_name = f"{workflow.db_name}_{timestamp}_{hash_value}"
    file_name = f"{base_name}.{format_type}"
    file_path = os.path.join(temp_dir, file_name)
    # 将查询结果写入 CSV 文件
    if format_type == "csv":
        save_csv(file_path, result, columns)
    elif format_type == "json":
        save_json(file_path, result, columns)
    elif format_type == "xml":
        save_xml(file_path, result, columns)
    elif format_type == "xlsx":
        save_xlsx(file_path, result, columns)
    elif format_type == "sql":
        save_sql(file_path, result, columns)
    else:
        raise ValueError(f"Unsupported format type: {format_type}")

    zip_file_name = f"{base_name}.zip"
    zip_file_path = os.path.join(temp_dir, zip_file_name)
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file_path, os.path.basename(file_path))
    return zip_file_name


def upload_file_to_storage(file_name=None, storage_type=None, temp_dir=None):
    action_exec = StorageControl(
        file_name=file_name, storage_type=storage_type, temp_dir=temp_dir
    )
    try:
        if storage_type == "oss":
            # 使用阿里云 OSS 进行上传
            action_exec.upload_to_oss()
        elif storage_type == "sftp":
            # 使用 SFTP 进行上传
            action_exec.upload_to_sftp()
        elif storage_type == "local":
            # 本地存储
            action_exec.upload_to_local()
        else:
            # 未知存储类型，可以抛出异常或处理其他逻辑
            raise ValueError(f"Unknown storage type: {storage_type}")
    except Exception as e:
        raise e


def clean_local_files(temp_dir):
    # 删除临时目录及其内容
    shutil.rmtree(temp_dir)


def datetime_serializer(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def save_csv(file_path, result, columns):
    with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
        csv_writer = csv.writer(csv_file, quoting=csv.QUOTE_ALL)

        if columns:
            csv_writer.writerow(columns)

        for row in result:
            csv_row = ["null" if value is None else value for value in row]
            csv_writer.writerow(csv_row)


def save_json(file_path, result, columns):
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(
            [dict(zip(columns, row)) for row in result],
            json_file,
            indent=2,
            default=datetime_serializer,
            ensure_ascii=False,
        )


def save_xml(file_path, result, columns):
    root = ET.Element("tabledata")

    # Create fields element
    fields_elem = ET.SubElement(root, "fields")
    for column in columns:
        field_elem = ET.SubElement(fields_elem, "field")
        field_elem.text = column

    # Create data element
    data_elem = ET.SubElement(root, "data")
    for row_id, row in enumerate(result, start=1):
        row_elem = ET.SubElement(data_elem, "row", id=str(row_id))
        for col_idx, value in enumerate(row, start=1):
            col_elem = ET.SubElement(row_elem, f"column-{col_idx}")
            if value is None:
                col_elem.text = "(null)"
            elif isinstance(value, (datetime.date, datetime.datetime)):
                col_elem.text = value.isoformat()
            else:
                col_elem.text = str(value)

    tree = ET.ElementTree(root)
    tree.write(file_path, encoding="utf-8", xml_declaration=True)


def save_xlsx(file_path, result, columns):
    try:
        df = pd.DataFrame(
            [
                [
                    str(value) if value is not None and value != "NULL" else ""
                    for value in row
                ]
                for row in result
            ],
            columns=columns,
        )
        df.to_excel(file_path, index=False, header=True)
    except ValueError as e:
        raise ValueError(f"Excel最大支持行数为1048576,已超出!")


def save_sql(file_path, result, columns):
    with open(file_path, "w") as sql_file:
        for row in result:
            table_name = "your_table_name"
            if columns:
                sql_file.write(
                    f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES "
                )

            values = ", ".join(
                [
                    (
                        "'{}'".format(str(value).replace("'", "''"))
                        if isinstance(value, str)
                        or isinstance(value, datetime.date)
                        or isinstance(value, datetime.datetime)
                        else "NULL" if value is None or value == "" else str(value)
                    )
                    for value in row
                ]
            )
            sql_file.write(f"({values});\n")


def offline_file_download(request):
    file_name = request.GET.get("file_name", " ")
    workflow_id = request.GET.get("workflow_id", " ")
    action = "离线下载"
    extra_info = f"工单id：{workflow_id},文件：{file_name}"
    config = get_sys_config()
    storage_type = config["sqlfile_storage"]

    try:
        action_exec = StorageControl(storage_type=storage_type, file_name=file_name)
        if storage_type == "sftp":
            response = action_exec.download_from_sftp()
            return response
        elif storage_type == "oss":
            response = action_exec.download_from_oss()
            return response
        elif storage_type == "local":
            response = action_exec.download_from_local()
            return response

    except Exception as e:
        action = "离线下载失败"
        return HttpResponse(f"下载失败：{e}", status=500)
    finally:
        AuditEntry.objects.create(
            user_id=request.user.id,
            user_name=request.user.username,
            user_display=request.user.display,
            action=action,
            extra_info=extra_info,
        )


class StorageControl:
    def __init__(
        self, storage_type=None, do_action=None, file_name=None, temp_dir=None
    ):
        """根据存储服务进行文件的上传下载"""
        # 存储类型
        self.storage_type = storage_type
        # 暂时无用，可考虑删除
        self.do_action = do_action
        # 导出文件的压缩包名称
        self.file_name = file_name
        # 导出文件的本地临时目录，上传完成后会自动清理
        self.temp_dir = temp_dir

        # 获取系统配置
        self.config = get_sys_config()
        # 先进行系统管理内配置的 files_expire_with_days 参数的判断是否存在以及是否为空,默认值 0-不过期
        self.expire_time_str = self.config.get("files_expire_with_days", "0")
        self.expire_time_with_days = (
            int(self.expire_time_str) if self.expire_time_str else 0
        )
        # 获取当前时间
        self.current_time = datetime.datetime.now()
        # 获取过期的时间
        self.expire_time = self.current_time - datetime.timedelta(
            days=self.expire_time_with_days
        )

        # SFTP 存储相关配置信息
        self.sftp_host = self.config["sftp_host"]
        self.sftp_user = self.config["sftp_user"]
        self.sftp_password = self.config["sftp_password"]
        self.sftp_port_str = self.config.get("sftp_port", "22")
        self.sftp_port = int(self.sftp_port_str) if self.sftp_port_str else 22
        self.sftp_path = self.config["sftp_path"]

        # OSS 存储相关配置信息
        self.access_key_id = self.config["oss_access_key_id"]
        self.access_key_secret = self.config["oss_access_key_secret"]
        self.endpoint = self.config["oss_endpoint"]
        self.bucket_name = self.config["oss_bucket_name"]
        self.oss_path = self.config["oss_path"]

        # 本地存储相关配置信息
        # self.local_path = r'{}'.format(self.config['local_path'])
        self.local_path = r"{}".format(self.config.get("local_path", "/tmp"))

    def upload_to_sftp(self):
        # SFTP 配置
        try:
            with Transport((self.sftp_host, self.sftp_port)) as transport:
                transport.connect(username=self.sftp_user, password=self.sftp_password)
                with SFTPClient.from_transport(transport) as sftp:
                    remote_file = os.path.join(
                        self.sftp_path, os.path.basename(self.file_name)
                    )
                    # 判断时间是否配置，为 0 则默认不删除，大于 0 则调用删除方法进行删除过期文件
                    if self.expire_time_with_days > 0:
                        self.del_file_before_upload_to_sftp(sftp)
                    # 上传离线导出的文件压缩包到SFTP
                    sftp.put(os.path.join(self.temp_dir, self.file_name), remote_file)

        except Exception as e:
            upload_to_sftp_exception = Exception(f"上传失败: {e}")
            raise upload_to_sftp_exception

    def download_from_sftp(self):
        file_path = os.path.join(self.sftp_path, self.file_name)

        with Transport((self.sftp_host, self.sftp_port)) as transport:
            transport.connect(username=self.sftp_user, password=self.sftp_password)
            with SFTPClient.from_transport(transport) as sftp:
                # 获取压缩包内容
                file_content = BytesIO()
                sftp.getfo(file_path, file_content)

        # 构造 HttpResponse 返回 ZIP 文件内容
        response = HttpResponse(file_content.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = (
            f"attachment; filename={quote(self.file_name)}"
        )
        return response

    def del_file_before_upload_to_sftp(self, sftp):
        for file_info in sftp.listdir_attr(self.sftp_path):
            file_path = os.path.join(self.sftp_path, file_info.filename)

            # 获取文件的修改时间
            modified_time = datetime.datetime.fromtimestamp(file_info.st_mtime)

            # 如果文件过期，则删除
            if modified_time < self.expire_time:
                sftp.remove(file_path)

    def upload_to_oss(self):
        # 创建 OSS 认证
        auth = oss2.Auth(self.access_key_id, self.access_key_secret)

        # 创建 OSS Bucket 对象
        bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)

        # 上传文件到 OSS
        remote_key = os.path.join(self.oss_path, os.path.basename(self.file_name))
        # 判断时间是否配置，为 0 则默认不删除，大于 0 则调用删除方法进行删除过期文件
        if self.expire_time_with_days > 0:
            self.del_file_before_upload_to_oss(bucket)
        # 读取并上传离线导出的文件压缩包到OSS
        with open(os.path.join(self.temp_dir, self.file_name), "rb") as file:
            bucket.put_object(remote_key, file)

    def download_from_oss(self):
        # 创建 OSS 认证
        auth = oss2.Auth(self.access_key_id, self.access_key_secret)

        # 创建 OSS Bucket 对象
        bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)

        # 从OSS下载文件
        remote_path = self.oss_path
        remote_key = os.path.join(remote_path, self.file_name)
        object_stream = bucket.get_object(remote_key)
        response = HttpResponse(object_stream.read(), content_type="application/zip")
        response["Content-Disposition"] = (
            f"attachment; filename={quote(self.file_name)}"
        )
        return response

    def del_file_before_upload_to_oss(self, bucket):
        for object_info in oss2.ObjectIterator(bucket, prefix=self.oss_path):
            # 获取 bucket 存储路径下的文件名
            file_path = object_info.key

            # 获取文件的修改时间
            modified_time = datetime.datetime.fromtimestamp(object_info.last_modified)

            # 如果文件过期，则删除
            if modified_time < self.expire_time:
                bucket.delete_object(file_path)

    def upload_to_local(self):
        try:
            source_path = os.path.join(self.temp_dir, self.file_name)
            # 判断配置内的本地存储路径是否存在，若不存在则抛出报错
            if not os.path.exists(self.local_path):
                raise FileNotFoundError(
                    f"Destination directory '{self.local_path}' not found."
                )
            # 判断时间是否配置，为 0 则默认不删除，大于 0 则调用删除方法进行删除过期文件
            if self.expire_time_with_days > 0:
                self.del_file_before_upload_to_local()
            # 拷贝离线导出的文件压缩包到指定路径
            shutil.copy(source_path, self.local_path)
        except Exception as e:
            raise e

    def download_from_local(self):
        file_path = os.path.join(self.local_path, self.file_name)

        with open(file_path, "rb") as file:
            response = HttpResponse(file.read(), content_type="application/zip")
            response["Content-Disposition"] = (
                f"attachment; filename={quote(self.file_name)}"
            )
            return response

    def del_file_before_upload_to_local(self):
        for local_file_info in os.listdir(self.local_path):
            file_path = os.path.join(self.local_path, local_file_info)
            if (
                os.path.isfile(file_path)
                and os.path.splitext(file_path)[1] == '.zip'
                and os.path.getmtime(file_path) < self.expire_time.timestamp()
            ):
                os.remove(file_path)

def execute_check_sql(conn, sql, config, workflow):
    # 先进行 max_export_rows 变量的判断是否存在以及是否为空,默认值10000
    max_export_rows_str = config.get("max_export_rows", "10000")
    max_export_rows = int(max_export_rows_str) if max_export_rows_str else 10000
    instance = workflow.instance
    schema_name = workflow.db_name
    # 判断sql是否以 select 开头
    if not sql.strip().lower().startswith("select"):
        return Exception(f"违规语句：{sql}")
    # 最终执行导出的时候判断行数是否超过阈值，若超过则抛出异常
    with conn.cursor() as cursor:
        try:
            count_sql = f"SELECT COUNT(*) FROM ({sql.rstrip(';')}) t"
            if instance.db_type == "oracle":
                cursor.execute(f"alter session set current_schema={schema_name}")
            cursor.execute(count_sql)
            actual_rows = cursor.fetchone()[0]
            if actual_rows > max_export_rows:
                return Exception(f"实际行数{actual_rows}超出阈值: {max_export_rows}")
            return actual_rows
        except Exception as e:
            return e
