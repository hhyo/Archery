# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: instance_database.py
@time: 2019/09/19
"""
import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse, HttpResponse

from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine
from sql.models import Instance, InstanceDatabase, Users

__author__ = 'hhyo'


@permission_required('sql.menu_database', raise_exception=True)
def databases(request):
    """获取实例数据库列表"""
    instance_id = request.POST.get('instance_id')
    saved = True if request.POST.get('saved') == 'true' else False  # 平台是否保存

    if not instance_id:
        return JsonResponse({'status': 0, 'msg': '', 'data': []})

    try:
        instance = Instance.objects.get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '实例不存在', 'data': []})

    # 获取已录入数据库
    cnf_dbs = dict()
    for db in InstanceDatabase.objects.filter(
            instance=instance).values('id', 'db_name', 'owner', 'owner_display', 'remark'):
        db['saved'] = True
        cnf_dbs[f"{db['db_name']}"] = db

    # 获取所有数据库
    sql_get_db = """SELECT SCHEMA_NAME,DEFAULT_CHARACTER_SET_NAME,DEFAULT_COLLATION_NAME 
FROM information_schema.SCHEMATA
WHERE SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'test', 'sys');"""
    query_engine = get_engine(instance=instance)
    query_result = query_engine.query('information_schema', sql_get_db, close_conn=False)
    if not query_result.error:
        dbs = query_result.rows
        # 获取数据库关联用户信息
        rows = []
        for db in dbs:
            db_name = db[0]
            sql_get_bind_users = f"""select group_concat(distinct(GRANTEE)),TABLE_SCHEMA
from information_schema.SCHEMA_PRIVILEGES
where TABLE_SCHEMA='{db_name}'
group by TABLE_SCHEMA;"""
            bind_users = query_engine.query('information_schema', sql_get_bind_users, close_conn=False).rows
            row = {
                'db_name': db_name,
                'charset': db[1],
                'collation': db[2],
                'grantees': bind_users[0][0].split(',') if bind_users else [],
                'saved': False
            }
            # 合并数据
            if db_name in cnf_dbs.keys():
                row = dict(row, **cnf_dbs[db_name])
            rows.append(row)
        # 过滤参数
        if saved:
            rows = [row for row in rows if row['saved']]

        result = {'status': 0, 'msg': 'ok', 'rows': rows}
    else:
        result = {'status': 1, 'msg': query_result.error}

    # 关闭连接
    query_engine.close()
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.db_manage', raise_exception=True)
def create(request):
    """创建数据库"""
    instance_id = request.POST.get('instance_id', 0)
    db_name = request.POST.get('db_name')
    owner = request.POST.get('owner', '')
    remark = request.POST.get('remark', '')

    if not all([db_name]):
        return JsonResponse({'status': 1, 'msg': '参数不完整，请确认后提交', 'data': []})

    try:
        instance = Instance.objects.get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '实例不存在', 'data': []})

    try:
        owner_display = Users.objects.get(username=owner).display
    except Users.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '负责人不存在', 'data': []})

    engine = get_engine(instance=instance)
    exec_result = engine.execute(db_name='information_schema', sql=f"create database {db_name};")
    if exec_result.error:
        return JsonResponse({'status': 1, 'msg': exec_result.error})
    # 保存到数据库
    else:
        InstanceDatabase.objects.create(
            instance=instance, db_name=db_name, owner=owner, owner_display=owner_display, remark=remark)
    return JsonResponse({'status': 0, 'msg': '', 'data': []})


@permission_required('sql.db_manage', raise_exception=True)
def edit(request):
    """编辑/录入数据库"""
    instance_id = request.POST.get('instance_id', 0)
    db_name = request.POST.get('db_name')
    owner = request.POST.get('owner', '')
    remark = request.POST.get('remark', '')

    if not all([db_name]):
        return JsonResponse({'status': 1, 'msg': '参数不完整，请确认后提交', 'data': []})

    try:
        instance = Instance.objects.get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '实例不存在', 'data': []})

    try:
        owner_display = Users.objects.get(username=owner).display
    except Users.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '负责人不存在', 'data': []})

    # 更新或者录入信息
    InstanceDatabase.objects.update_or_create(
        instance=instance,
        db_name=db_name,
        defaults={"owner": owner, "owner_display": owner_display, "remark": remark})
    return JsonResponse({'status': 0, 'msg': '', 'data': []})
