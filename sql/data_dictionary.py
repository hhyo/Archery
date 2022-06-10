# -*- coding: UTF-8 -*-
import datetime
import os
from urllib.parse import quote

import MySQLdb
import simplejson as json
from django.template import loader
from archery import settings
from sql.engines import get_engine
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse, JsonResponse, FileResponse

from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.utils.resource_group import user_instances
from .models import Instance


@permission_required('sql.menu_data_dictionary', raise_exception=True)
def table_list(request):
    """数据字典获取表列表"""
    instance_name = request.GET.get('instance_name', '')
    db_name = request.GET.get('db_name', '')
    db_type = request.GET.get('db_type', '')

    if instance_name and db_name:
        try:
            instance = Instance.objects.get(instance_name=instance_name, db_type=db_type)
            query_engine = get_engine(instance=instance)
            data = query_engine.get_group_tables_by_db(db_name=db_name)
            res = {'status': 0, 'data': data}
        except Instance.DoesNotExist:
            res = {'status': 1, 'msg': 'Instance.DoesNotExist'}
        except Exception as e:
            res = {'status': 1, 'msg': str(e)}
    else:
        res = {'status': 1, 'msg': '非法调用！'}
    return HttpResponse(json.dumps(res, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.menu_data_dictionary', raise_exception=True)
def table_info(request):
    """数据字典获取表信息"""
    instance_name = request.GET.get('instance_name', '')
    db_name = request.GET.get('db_name', '')
    tb_name = request.GET.get('tb_name', '')
    db_type = request.GET.get('db_type', '')
    if instance_name and db_name and tb_name:
        data = {}
        try:
            instance = Instance.objects.get(instance_name=instance_name, db_type=db_type)
            query_engine = get_engine(instance=instance)
            data['meta_data'] = query_engine.get_table_meta_data(db_name=db_name, tb_name=tb_name)
            data['desc'] = query_engine.get_table_desc_data(db_name=db_name, tb_name=tb_name)
            data['index'] = query_engine.get_table_index_data(db_name=db_name, tb_name=tb_name)

            # mysql数据库可以获取创建表格的SQL语句，mssql暂无找到生成创建表格的SQL语句
            if instance.db_type == 'mysql':
                _create_sql = query_engine.query(db_name, "show create table `%s`;" % tb_name)
                data['create_sql'] = _create_sql.rows
            res = {'status': 0, 'data': data}
        except Instance.DoesNotExist:
            res = {'status': 1, 'msg': 'Instance.DoesNotExist'}
        except Exception as e:
            res = {'status': 1, 'msg': str(e)}
    else:
        res = {'status': 1, 'msg': '非法调用！'}
    return HttpResponse(json.dumps(res, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.data_dictionary_export', raise_exception=True)
def export(request):
    """导出数据字典"""
    instance_name = request.GET.get('instance_name', '')
    db_name = request.GET.get('db_name', '')
    # escape
    db_name = MySQLdb.escape_string(db_name).decode('utf-8')

    try:
        instance = user_instances(request.user, db_type=['mysql', 'mssql', 'oracle']).get(instance_name=instance_name)
        query_engine = get_engine(instance=instance)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '你所在组未关联该实例！', 'data': []})

    # 普通用户仅可以获取指定数据库的字典信息
    if db_name:
        dbs = [db_name]
    # 管理员可以导出整个实例的字典信息
    elif request.user.is_superuser:
        dbs = query_engine.get_all_databases().rows
    else:
        return JsonResponse({'status': 1, 'msg': f'仅管理员可以导出整个实例的字典信息！', 'data': []})

    # 获取数据，存入目录
    path = os.path.join(settings.BASE_DIR, 'downloads/dictionary')
    os.makedirs(path, exist_ok=True)
    for db in dbs:
        table_metas = query_engine.get_tables_metas_data(db_name=db)
        context = {"db_name": db_name, "tables": table_metas, "export_time": datetime.datetime.now()}
        data = loader.render_to_string(template_name="dictionaryexport.html", context=context, request=request)
        with open(f'{path}/{instance_name}_{db}.html', 'w') as f:
            f.write(data)
    # 关闭连接
    query_engine.close()
    if db_name:
        response = FileResponse(open(f'{path}/{instance_name}_{db_name}.html', 'rb'))
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = f'attachment;filename="{quote(instance_name)}_{quote(db_name)}.html"'
        return response

    else:
        return JsonResponse({'status': 0, 'msg': f'实例{instance_name}数据字典导出成功，请到downloads目录下载！', 'data': []})
