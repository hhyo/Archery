# -*- coding: UTF-8 -*-
import datetime
import os
from urllib.parse import quote

import simplejson as json
from django.template import loader
from django.utils.translation import gettext as _
from django.conf import settings
from sql.engines import get_engine
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse, JsonResponse, FileResponse

from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.utils.resource_group import user_instances
from .models import Instance

DICTIONARY_COLUMN_LABELS = {
    "索引列",
    "是否为空",
    "字段名",
    "列类型",
    "列序列",
    "列名",
    "约束类型",
    "数据类型",
    "自动递增",
    "默认值",
    "拓展信息",
    "允许非空",
    "索引类型",
    "字段默认值",
    "表空间",
    "分区",
    "是否为LOCAL索引",
    "所属索引",
    "索引列名",
    "状态",
    "压缩属性",
    "列说明",
    "唯一性",
    "前导列索引",
    "是否主键",
    "备注",
    "索引名称",
    "索引名",
    "分区状态",
    "基数",
    "列注释",
    "字段类型",
    "列字符集",
}


def dictionary_column_title(label):
    return _(label) if label in DICTIONARY_COLUMN_LABELS else label


def localize_dictionary_columns(data):
    for section in ("desc", "index"):
        if isinstance(data.get(section), dict):
            data[section]["column_list"] = [
                dictionary_column_title(label)
                for label in data[section].get("column_list", [])
            ]
    return data


@permission_required("sql.menu_data_dictionary", raise_exception=True)
def table_list(request):
    """数据字典获取表列表"""
    instance_name = request.GET.get("instance_name", "")
    db_name = request.GET.get("db_name", "")
    db_type = request.GET.get("db_type", "")

    if instance_name and db_name:
        try:
            instance = Instance.objects.get(
                instance_name=instance_name, db_type=db_type
            )
            query_engine = get_engine(instance=instance)
            db_name = query_engine.escape_string(db_name)
            data = query_engine.get_group_tables_by_db(db_name=db_name)
            res = {
                "status": 0,
                "data": data,
            }
        except Instance.DoesNotExist:
            res = {"status": 1, "msg": "Instance.DoesNotExist"}
        except Exception as e:
            res = {"status": 1, "msg": str(e)}
    else:
        res = {"status": 1, "msg": _("非法调用！")}
    return HttpResponse(
        json.dumps(res, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@permission_required("sql.menu_data_dictionary", raise_exception=True)
def table_info(request):
    """数据字典获取表信息"""
    instance_name = request.GET.get("instance_name", "")
    db_name = request.GET.get("db_name", "")
    tb_name = request.GET.get("tb_name", "")
    db_type = request.GET.get("db_type", "")

    if instance_name and db_name and tb_name:
        data = {}
        try:
            instance = Instance.objects.get(
                instance_name=instance_name, db_type=db_type
            )
            query_engine = get_engine(instance=instance)
            db_name = query_engine.escape_string(db_name)
            tb_name = query_engine.escape_string(tb_name)
            data["meta_data"] = query_engine.get_table_meta_data(
                db_name=db_name, tb_name=tb_name
            )
            data["desc"] = query_engine.get_table_desc_data(
                db_name=db_name, tb_name=tb_name
            )
            data["index"] = query_engine.get_table_index_data(
                db_name=db_name, tb_name=tb_name
            )

            # mysql、clickhouse 和 gaussdb 数据库可以获取创建表格的SQL语句
            if instance.db_type in ("mysql", "clickhouse", "gaussdb"):
                quote = "`" if instance.db_type in ("mysql", "clickhouse") else ""
                _create_sql = query_engine.query(
                    db_name, f"show create table {quote}{tb_name}{quote};"
                )
                data["create_sql"] = _create_sql.rows
            res = {
                "status": 0,
                "data": localize_dictionary_columns(data),
            }
        except Instance.DoesNotExist:
            res = {"status": 1, "msg": "Instance.DoesNotExist"}
        except Exception as e:
            res = {"status": 1, "msg": str(e)}
    else:
        res = {"status": 1, "msg": _("非法调用！")}
    return HttpResponse(
        json.dumps(res, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@permission_required("sql.menu_data_dictionary", raise_exception=True)
def view_list(request):
    """数据字典获取视图列表"""
    return _dict_list(
        request, db_type_required=("mysql", "gaussdb"), engine_method="get_views_list"
    )


@permission_required("sql.menu_data_dictionary", raise_exception=True)
def view_info(request):
    """数据字典获取视图详情"""
    return _dict_detail(
        request,
        db_type_required=("mysql", "gaussdb"),
        engine_method="get_view_detail",
        name_param="view_name",
        engine_kwarg="view_name",
    )


@permission_required("sql.menu_data_dictionary", raise_exception=True)
def trigger_list(request):
    """数据字典获取触发器列表"""
    return _dict_list(
        request,
        db_type_required=("mysql", "gaussdb"),
        engine_method="get_triggers_list",
    )


@permission_required("sql.menu_data_dictionary", raise_exception=True)
def trigger_info(request):
    """数据字典获取触发器详情"""
    return _dict_detail(
        request,
        db_type_required=("mysql", "gaussdb"),
        engine_method="get_trigger_detail",
        name_param="trigger_name",
        engine_kwarg="trigger_name",
    )


@permission_required("sql.menu_data_dictionary", raise_exception=True)
def procedure_list(request):
    """数据字典获取存储过程列表"""
    return _dict_list(
        request,
        db_type_required=("mysql", "gaussdb"),
        engine_method="get_procedures_list",
    )


@permission_required("sql.menu_data_dictionary", raise_exception=True)
def procedure_info(request):
    """数据字典获取存储过程详情"""
    return _dict_detail(
        request,
        db_type_required=("mysql", "gaussdb"),
        engine_method="get_procedure_detail",
        name_param="proc_name",
        engine_kwarg="proc_name",
    )


@permission_required("sql.menu_data_dictionary", raise_exception=True)
def function_list(request):
    """数据字典获取函数列表"""
    return _dict_list(
        request,
        db_type_required=("mysql", "gaussdb"),
        engine_method="get_functions_list",
    )


@permission_required("sql.menu_data_dictionary", raise_exception=True)
def function_info(request):
    """数据字典获取函数详情"""
    return _dict_detail(
        request,
        db_type_required=("mysql", "gaussdb"),
        engine_method="get_function_detail",
        name_param="func_name",
        engine_kwarg="func_name",
    )


@permission_required("sql.menu_data_dictionary", raise_exception=True)
def event_list(request):
    """数据字典获取定时任务列表（仅MySQL）"""
    return _dict_list(
        request, db_type_required="mysql", engine_method="get_events_list"
    )


@permission_required("sql.menu_data_dictionary", raise_exception=True)
def event_info(request):
    """数据字典获取定时任务详情（仅MySQL）"""
    return _dict_detail(
        request,
        db_type_required="mysql",
        engine_method="get_event_detail",
        name_param="event_name",
        engine_kwarg="event_name",
    )


def _dict_list(request, db_type_required, engine_method):
    """通用数据字典对象列表接口"""
    instance_name = request.GET.get("instance_name", "")
    db_name = request.GET.get("db_name", "")
    db_type = request.GET.get("db_type", "")

    if db_type_required and db_type not in (
        db_type_required
        if isinstance(db_type_required, (tuple, list))
        else (db_type_required,)
    ):
        res = {"status": 1, "msg": _("该数据库类型不支持此功能")}
        return HttpResponse(
            json.dumps(res, cls=ExtendJSONEncoder, bigint_as_string=True),
            content_type="application/json",
        )

    if instance_name and db_name:
        try:
            instance = Instance.objects.get(
                instance_name=instance_name, db_type=db_type
            )
            query_engine = get_engine(instance=instance)
            db_name = query_engine.escape_string(db_name)
            data = getattr(query_engine, engine_method)(db_name=db_name)
            res = {
                "status": 0,
                "data": data,
            }
        except Instance.DoesNotExist:
            res = {"status": 1, "msg": "Instance.DoesNotExist"}
        except Exception as e:
            res = {"status": 1, "msg": str(e)}
    else:
        res = {"status": 1, "msg": _("非法调用！")}
    return HttpResponse(
        json.dumps(res, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


def _dict_detail(request, db_type_required, engine_method, name_param, engine_kwarg):
    """通用数据字典对象详情接口"""
    instance_name = request.GET.get("instance_name", "")
    db_name = request.GET.get("db_name", "")
    obj_name = request.GET.get(name_param, "")
    db_type = request.GET.get("db_type", "")

    if db_type_required and db_type not in (
        db_type_required
        if isinstance(db_type_required, (tuple, list))
        else (db_type_required,)
    ):
        res = {"status": 1, "msg": _("该数据库类型不支持此功能")}
        return HttpResponse(
            json.dumps(res, cls=ExtendJSONEncoder, bigint_as_string=True),
            content_type="application/json",
        )

    if instance_name and db_name and obj_name:
        try:
            instance = Instance.objects.get(
                instance_name=instance_name, db_type=db_type
            )
            query_engine = get_engine(instance=instance)
            db_name = query_engine.escape_string(db_name)
            obj_name = query_engine.escape_string(obj_name)
            data = getattr(query_engine, engine_method)(
                **{"db_name": db_name, engine_kwarg: obj_name}
            )
            res = {
                "status": 0,
                "data": localize_dictionary_columns(data),
            }
        except Instance.DoesNotExist:
            res = {"status": 1, "msg": "Instance.DoesNotExist"}
        except Exception as e:
            res = {"status": 1, "msg": str(e)}
    else:
        res = {"status": 1, "msg": _("非法调用！")}
    return HttpResponse(
        json.dumps(res, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


def get_export_full_path(base_dir: str, instance_name: str, db_name: str) -> str:
    """validate if the instance_name and db_name provided is secure"""
    fullpath = os.path.normpath(
        os.path.join(base_dir, f"{instance_name}_{db_name}.html")
    )
    if not fullpath.startswith(base_dir):
        return ""
    return fullpath


@permission_required("sql.data_dictionary_export", raise_exception=True)
def export(request):
    """导出数据字典"""
    instance_name = request.GET.get("instance_name", "")
    db_name = request.GET.get("db_name", "")

    try:
        instance = user_instances(
            request.user, db_type=["mysql", "mssql", "oracle", "clickhouse", "gaussdb"]
        ).get(instance_name=instance_name)
        query_engine = get_engine(instance=instance)
    except Instance.DoesNotExist:
        return JsonResponse(
            {"status": 1, "msg": _("你所在组未关联该实例！"), "data": []}
        )

    # 普通用户仅可以获取指定数据库的字典信息
    if db_name:
        dbs = [query_engine.escape_string(db_name)]
    # 管理员可以导出整个实例的字典信息
    elif request.user.is_superuser:
        query_engine.is_superuser = True
        dbs = query_engine.get_all_databases().rows
    else:
        return JsonResponse(
            {"status": 1, "msg": _("仅管理员可以导出整个实例的字典信息！"), "data": []}
        )

    # 获取数据，存入目录
    path = os.path.join(settings.BASE_DIR, "downloads", "dictionary")
    os.makedirs(path, exist_ok=True)
    for db in dbs:
        table_metas = query_engine.get_tables_metas_data(db_name=db)
        for table in table_metas:
            for header in table.get("ENGINE_KEYS", []):
                header["value"] = dictionary_column_title(header["value"])
        context = {
            "db_name": db_name,
            "tables": table_metas,
            "export_time": datetime.datetime.now(),
        }
        data = loader.render_to_string(
            template_name="dictionaryexport.html", context=context, request=request
        )
        fullpath = get_export_full_path(path, instance_name, db)
        if not fullpath:
            return JsonResponse(
                {"status": 1, "msg": _("实例名或db名不合法"), "data": []}
            )
        with open(fullpath, "w", encoding="utf-8") as fp:
            fp.write(data)
    # 关闭连接
    query_engine.close()
    if db_name:
        fullpath = get_export_full_path(path, instance_name, db)
        if not fullpath:
            return JsonResponse(
                {"status": 1, "msg": _("实例名或db名不合法"), "data": []}
            )
        response = FileResponse(open(fullpath, "rb"))
        response["Content-Type"] = "application/octet-stream"
        response["Content-Disposition"] = (
            f'attachment;filename="{quote(instance_name)}_{quote(db_name)}.html"'
        )
        return response

    else:
        return JsonResponse(
            {
                "status": 0,
                "msg": _(
                    "实例%(instance_name)s数据字典导出成功，请到downloads目录下载！"
                )
                % {"instance_name": instance_name},
                "data": [],
            }
        )
