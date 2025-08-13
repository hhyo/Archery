# -*- coding: UTF-8 -*-
import logging
import os
import tempfile
import csv
import hashlib
import shutil
import datetime
import xml.etree.ElementTree as ET
import zipfile
import sqlparse
import time

import simplejson as json
import pandas as pd
from django.http import JsonResponse, FileResponse


from sql.models import SqlWorkflow, AuditEntry
from sql.engines import EngineBase
from sql.engines.models import ReviewSet, ReviewResult
from sql.storage import DynamicStorage
from sql.engines import get_engine
from common.config import SysConfig

logger = logging.getLogger("default")


class OffLineDownLoad(EngineBase):
    """
    离线下载类，用于执行离线下载操作。
    """

    def execute_offline_download(self, workflow):
        """
        执行离线下载操作
        :param workflow: 工单实例
        :return: 下载结果
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # 获取系统配置
            config = SysConfig()
            # 先进行 max_execution_time 变量的判断是否存在以及是否为空,默认值60
            max_execution_time_str = config.get("max_export_rows", "60")
            max_execution_time = (
                int(max_execution_time_str) if max_execution_time_str else 60
            )
            # 获取前端提交的 SQL 和其他工单信息
            full_sql = workflow.sqlworkflowcontent.sql_content
            full_sql = sqlparse.format(full_sql, strip_comments=True)
            full_sql = sqlparse.split(full_sql)[0]
            sql = full_sql.strip()
            instance = workflow.instance
            execute_result = ReviewSet(full_sql=sql)
            check_engine = get_engine(instance=instance)

            start_time = time.time()

            try:
                # 执行 SQL 查询
                storage = DynamicStorage()
                results = check_engine.query(
                    db_name=workflow.db_name,
                    sql=sql,
                    max_execution_time=max_execution_time * 1000,
                )
                if results.error:
                    raise Exception(results.error)
                if results:
                    columns = results.column_list
                    result = results.rows
                    actual_rows = results.affected_rows

                # 保存查询结果为 CSV or JSON or XML or XLSX or SQL 文件
                get_format_type = workflow.export_format
                file_name = save_to_format_file(
                    get_format_type, result, workflow, columns, temp_dir
                )

                # 将导出的文件保存到存储
                tmp_file = os.path.join(temp_dir, file_name)
                with open(tmp_file, "rb") as f:
                    storage.save(file_name, f)

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
                        affected_rows=actual_rows,
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
                # 关闭存储连接（主要是sftp情况save后需要关闭连接）
                storage.close()
                # 清理本地文件和临时目录
                shutil.rmtree(temp_dir)

    def pre_count_check(self, workflow):
        """
        提交工单时进行后端检查，检查行数是否符合阈值 以及 是否允许的查询语句
        :param workflow: 工单实例
        :return: 检查结果字典
        """
        # 获取系统配置
        config = SysConfig()
        # 获取前端提交的 SQL 和其他工单信息
        full_sql = workflow.sql_content
        full_sql = sqlparse.format(full_sql, strip_comments=True)
        full_sql = sqlparse.split(full_sql)[0]
        sql = full_sql.strip()
        count_sql = f"SELECT COUNT(*) FROM ({sql.rstrip(';')}) t"
        clean_sql = sql.strip().lower()
        instance = workflow
        check_result = ReviewSet(full_sql=sql)
        check_result.syntax_type = 3
        check_engine = get_engine(instance=instance)
        result_set = check_engine.query(db_name=workflow.db_name, sql=count_sql)
        actual_rows_check = result_set.rows[0][0]
        max_export_rows_str = config.get("max_export_rows", "10000")
        max_export_rows = int(max_export_rows_str) if max_export_rows_str else 10000

        allowed_prefixes = ("select", "with")  # 允许 SELECT 和 WITH 开头
        if not clean_sql.startswith(allowed_prefixes):
            result = ReviewResult(
                stage="自动审核失败",
                errlevel=2,
                stagestatus="检查未通过！",
                errormessage=f"违规语句！",
                affected_rows=actual_rows_check,
                sql=full_sql,
            )
        elif result_set.error:
            result = ReviewResult(
                stage="自动审核失败",
                errlevel=2,
                stagestatus="检查未通过！",
                errormessage=result_set.error,
                affected_rows=actual_rows_check,
                sql=full_sql,
            )
        elif actual_rows_check > max_export_rows:
            result = ReviewResult(
                errlevel=2,
                stagestatus="检查未通过！",
                errormessage=f"导出数据行数({actual_rows_check})超过阈值({max_export_rows})。",
                affected_rows=actual_rows_check,
                sql=full_sql,
            )
        else:
            result = ReviewResult(
                errlevel=0,
                stagestatus="行数统计完成",
                errormessage="None",
                sql=full_sql,
                affected_rows=actual_rows_check,
                execute_time=0,
            )
        check_result.rows = [result]
        # 统计警告和错误数量
        for r in check_result.rows:
            if r.errlevel == 1:
                check_result.warning_count += 1
            if r.errlevel == 2:
                check_result.error_count += 1
        return check_result


def save_to_format_file(
    format_type=None, result=None, workflow=None, columns=None, temp_dir=None
):
    """
    保存查询结果为指定格式的文件。
    :param format_type: 文件格式类型（csv、json、xml、xlsx、sql）
    :param result: 查询结果
    :param workflow: 工单实例
    :param columns: 列名
    :param temp_dir: 临时目录路径
    :return: 压缩后的文件名
    """
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


def save_csv(file_path, result, columns):
    """
    保存CSV文件，将查询结果写入CSV文件。
    :param file_path: CSV文件路径
    :param result: 查询结果
    :param columns: 列名
    """
    with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
        csv_writer = csv.writer(csv_file, quoting=csv.QUOTE_ALL)

        if columns:
            csv_writer.writerow(columns)

        for row in result:
            csv_row = ["null" if value is None else value for value in row]
            csv_writer.writerow(csv_row)


def save_json(file_path, result, columns):
    """
    保存JSON文件，将查询结果写入JSON文件。
    :param file_path: JSON文件路径
    :param result: 查询结果
    :param columns: 列名
    """
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(
            [dict(zip(columns, row)) for row in result],
            json_file,
            indent=2,
            ensure_ascii=False,
        )


def save_xml(file_path, result, columns):
    """
    保存XML文件，将查询结果写入XML文件。
    :param file_path: XML文件路径
    :param result: 查询结果
    :param columns: 列名
    """
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
    """
    保存Excel文件，将查询结果写入Excel文件。
    :param file_path: Excel文件路径
    :param result: 查询结果
    :param columns: 列名
    """
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
    """
    保存SQL文件，将查询结果写入SQL文件。
    :param file_path: SQL文件路径
    :param result: 查询结果
    :param columns: 列名
    """
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


class StorageFileResponse(FileResponse):
    """
    自定义文件响应类，用于处理文件下载，主要用于处理storages.backends.sftpstorage下载后无法关闭后台连接的问题。
    """

    def __init__(self, *args, storage=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage = storage

    def close(self):
        super().close()
        if hasattr(self, "storage") and self.storage:
            self.storage.close()


def offline_file_download(request):
    """
    下载文件，本地文件和sftp文件使用文件流，云对象存储服务的文件重定向到url。
    :param request:
    :return:
    """
    file_name = request.GET.get("file_name", " ")
    workflow_id = request.GET.get("workflow_id", " ")
    action = "离线下载"
    extra_info = f"工单id：{workflow_id}，文件：{file_name}"
    config = SysConfig()
    storage_type = config.get("storage_type")
    storage = DynamicStorage()

    try:
        if not storage.exists(file_name):
            extra_info = extra_info + f"，error:文件不存在。"
            return JsonResponse({"error": "文件不存在"}, status=404)
        elif storage.exists(file_name):
            if storage_type in ["sftp", "local"]:
                # SFTP/LOCAL处理 - 直接提供文件流
                try:
                    file = storage.open(file_name, "rb")
                    file_size = storage.size(file_name)
                    response = StorageFileResponse(file, storage=storage)
                    response["Content-Disposition"] = (
                        f'attachment; filename="{file_name}"'
                    )
                    response["Content-Length"] = str(file_size)
                    response["Content-Encoding"] = "identity"
                    return response
                except Exception as e:
                    extra_info = extra_info + f"，error:{str(e)}"
                    logger.error(extra_info)
                    return JsonResponse(
                        {"error": f"文件下载失败：请联系管理员。"}, status=500
                    )

            elif storage_type in ["s3c", "azure"]:
                try:
                    # 云对象存储生成带有效期的临时下载URL
                    presigned_url = storage.url(file_name)
                    return JsonResponse({"type": "redirect", "url": presigned_url})
                except Exception as e:
                    extra_info = extra_info + f"，error:{str(e)}"
                    logger.error(extra_info)
                    return JsonResponse(
                        {"error": f"文件下载失败：请联系管理员。"}, status=500
                    )

    except Exception as e:
        extra_info = extra_info + f"，error:{str(e)}"
        logger.error(extra_info)
        return JsonResponse({"error": "内部错误，请联系管理员。"}, status=500)

    finally:
        if request.method != "HEAD":
            AuditEntry.objects.create(
                user_id=request.user.id,
                user_name=request.user.username,
                user_display=request.user.display,
                action=action,
                extra_info=extra_info,
            )
