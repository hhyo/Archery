# -*- coding: UTF-8 -*-
import MySQLdb
import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from django.http import HttpResponse, JsonResponse

from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine
from sql.utils.resource_group import user_instances
from .models import Instance, InstanceAccount


@permission_required('sql.menu_instance_account', raise_exception=True)
def users(request):
    """获取实例用户列表"""
    instance_id = request.POST.get('instance_id')
    saved = True if request.POST.get('saved') == 'true' else False  # 平台是否保存

    if not instance_id:
        return JsonResponse({'status': 0, 'msg': '', 'data': []})
    try:
        instance = user_instances(request.user, db_type=['mysql']).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '你所在组未关联该实例', 'data': []})

    # 获取已录入用户
    cnf_users = dict()
    for user in InstanceAccount.objects.filter(instance=instance).values('id', 'user', 'host', 'remark'):
        user['saved'] = True
        cnf_users[f"`{user['user']}`@`{user['host']}`"] = user
    # 获取所有用户
    query_engine = get_engine(instance=instance)
    server_version = query_engine.server_version
    # MySQL 5.7.6版本起支持ACCOUNT LOCK
    if server_version >= (5, 7, 6):
        sql_get_user = "select concat('`', user, '`', '@', '`', host,'`') as query,user,host,account_locked from mysql.user;"
    else:
        sql_get_user = "select concat('`', user, '`', '@', '`', host,'`') as query,user,host from mysql.user;"
    query_result = query_engine.query('mysql', sql_get_user)
    if not query_result.error:
        db_users = query_result.rows
        # 获取用户权限信息
        rows = []
        for db_user in db_users:
            user_host = db_user[0]
            user_priv = query_engine.query('mysql', 'show grants for {};'.format(user_host), close_conn=False).rows
            row = {
                'user_host': user_host,
                'user': db_user[1],
                'host': db_user[2],
                'privileges': user_priv,
                'saved': False,
                'is_locked': db_user[3] if server_version >= (5, 7, 6) else None
            }
            # 合并数据
            if user_host in cnf_users.keys():
                row = dict(row, **cnf_users[user_host])
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


@permission_required('sql.instance_account_manage', raise_exception=True)
def create(request):
    """创建数据库账号"""
    instance_id = request.POST.get('instance_id', 0)
    user = request.POST.get('user')
    host = request.POST.get('host')
    password1 = request.POST.get('password1')
    password2 = request.POST.get('password2')
    remark = request.POST.get('remark', '')

    try:
        instance = user_instances(request.user, db_type=['mysql']).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '你所在组未关联该实例', 'data': []})

    if not all([user, host, password1, password2]):
        return JsonResponse({'status': 1, 'msg': '参数不完整，请确认后提交', 'data': []})

    if password1 != password2:
        return JsonResponse({'status': 1, 'msg': '两次输入密码不一致', 'data': []})

    # TODO 目前使用系统自带验证，后续实现验证器校验
    try:
        validate_password(password1, user=None, password_validators=None)
    except ValidationError as msg:
        return JsonResponse({'status': 1, 'msg': f'{msg}', 'data': []})

    # escape
    user = MySQLdb.escape_string(user).decode('utf-8')
    host = MySQLdb.escape_string(host).decode('utf-8')
    password1 = MySQLdb.escape_string(password1).decode('utf-8')

    engine = get_engine(instance=instance)
    # 在一个事务内执行
    hosts = host.split("|")
    create_user_cmd = ''
    accounts = []
    for host in hosts:
        create_user_cmd += f"create user '{user}'@'{host}' identified by '{password1}';"
        accounts.append(InstanceAccount(instance=instance, user=user, host=host, password=password1, remark=remark))
    exec_result = engine.execute(db_name='mysql', sql=create_user_cmd)
    if exec_result.error:
        return JsonResponse({'status': 1, 'msg': exec_result.error})

    # 保存到数据库
    else:
        InstanceAccount.objects.bulk_create(accounts)
    return JsonResponse({'status': 0, 'msg': '', 'data': []})


@permission_required('sql.instance_account_manage', raise_exception=True)
def edit(request):
    """修改、录入数据库账号"""
    instance_id = request.POST.get('instance_id', 0)
    user = request.POST.get('user')
    host = request.POST.get('host')
    password = request.POST.get('password')
    remark = request.POST.get('remark', '')

    try:
        instance = user_instances(request.user, db_type=['mysql']).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '你所在组未关联该实例', 'data': []})

    if not all([user, host]):
        return JsonResponse({'status': 1, 'msg': '参数不完整，请确认后提交', 'data': []})

    # 保存到数据库
    if password:
        InstanceAccount.objects.update_or_create(
            instance=instance, user=user, host=host,
            defaults={
                "password": password,
                "remark": remark
            }
        )
    else:
        InstanceAccount.objects.update_or_create(
            instance=instance, user=user, host=host,
            defaults={
                "remark": remark
            }
        )
    return JsonResponse({'status': 0, 'msg': '', 'data': []})


@permission_required('sql.instance_account_manage', raise_exception=True)
def grant(request):
    """获取用户权限变更语句，并执行权限变更"""
    instance_id = request.POST.get('instance_id', 0)
    user_host = request.POST.get('user_host')
    op_type = int(request.POST.get('op_type'))
    priv_type = int(request.POST.get('priv_type'))
    privs = json.loads(request.POST.get('privs'))
    grant_sql = ''

    # escape
    user_host = MySQLdb.escape_string(user_host).decode('utf-8')

    # 全局权限
    if priv_type == 0:
        global_privs = privs['global_privs']
        if not all([global_privs]):
            return JsonResponse({'status': 1, 'msg': '信息不完整，请确认后提交', 'data': []})
        global_privs = ['GRANT OPTION' if g == 'GRANT' else g for g in global_privs]
        if op_type == 0:
            grant_sql = f"GRANT {','.join(global_privs)} ON *.* TO {user_host};"
        elif op_type == 1:
            grant_sql = f"REVOKE {','.join(global_privs)} ON *.* FROM {user_host};"

    # 库权限
    elif priv_type == 1:
        db_privs = privs['db_privs']
        db_name = request.POST.getlist('db_name[]')
        if not all([db_privs, db_name]):
            return JsonResponse({'status': 1, 'msg': '信息不完整，请确认后提交', 'data': []})
        for db in db_name:
            db_privs = ['GRANT OPTION' if d == 'GRANT' else d for d in db_privs]
            if op_type == 0:
                grant_sql += f"GRANT {','.join(db_privs)} ON `{db}`.* TO {user_host};"
            elif op_type == 1:
                grant_sql += f"REVOKE {','.join(db_privs)} ON `{db}`.* FROM {user_host};"
    # 表权限
    elif priv_type == 2:
        tb_privs = privs['tb_privs']
        db_name = request.POST.get('db_name')
        tb_name = request.POST.getlist('tb_name[]')
        if not all([tb_privs, db_name, tb_name]):
            return JsonResponse({'status': 1, 'msg': '信息不完整，请确认后提交', 'data': []})
        for tb in tb_name:
            tb_privs = ['GRANT OPTION' if t == 'GRANT' else t for t in tb_privs]
            if op_type == 0:
                grant_sql += f"GRANT {','.join(tb_privs)} ON `{db_name}`.`{tb}` TO {user_host};"
            elif op_type == 1:
                grant_sql += f"REVOKE {','.join(tb_privs)} ON `{db_name}`.`{tb}` FROM {user_host};"
    # 列权限
    elif priv_type == 3:
        col_privs = privs['col_privs']
        db_name = request.POST.get('db_name')
        tb_name = request.POST.get('tb_name')
        col_name = request.POST.getlist('col_name[]')
        if not all([col_privs, db_name, tb_name, col_name]):
            return JsonResponse({'status': 1, 'msg': '信息不完整，请确认后提交', 'data': []})
        for priv in col_privs:
            if op_type == 0:
                grant_sql += f"GRANT {priv}(`{'`,`'.join(col_name)}`) ON `{db_name}`.`{tb_name}` TO {user_host};"
            elif op_type == 1:
                grant_sql += f"REVOKE {priv}(`{'`,`'.join(col_name)}`) ON `{db_name}`.`{tb_name}` FROM {user_host};"

    # 执行变更语句
    try:
        instance = user_instances(request.user, db_type=['mysql']).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '你所在组未关联该实例', 'data': []})

    engine = get_engine(instance=instance)
    exec_result = engine.execute(db_name='mysql', sql=grant_sql)
    if exec_result.error:
        return JsonResponse({'status': 1, 'msg': exec_result.error})
    return JsonResponse({'status': 0, 'msg': '', 'data': grant_sql})


@permission_required('sql.instance_account_manage', raise_exception=True)
def reset_pwd(request):
    """创建数据库账号"""
    instance_id = request.POST.get('instance_id', 0)
    user_host = request.POST.get('user_host')
    user = request.POST.get('user')
    host = request.POST.get('host')
    reset_pwd1 = request.POST.get('reset_pwd1')
    reset_pwd2 = request.POST.get('reset_pwd2')

    if not all([user, host, reset_pwd1, reset_pwd2]):
        return JsonResponse({'status': 1, 'msg': '参数不完整，请确认后提交', 'data': []})

    if reset_pwd1 != reset_pwd2:
        return JsonResponse({'status': 1, 'msg': '两次输入密码不一致', 'data': []})

    try:
        instance = user_instances(request.user, db_type=['mysql']).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '你所在组未关联该实例', 'data': []})

    # escape
    user_host = MySQLdb.escape_string(user_host).decode('utf-8')
    reset_pwd1 = MySQLdb.escape_string(reset_pwd1).decode('utf-8')

    # TODO 目前使用系统自带验证，后续实现验证器校验
    try:
        validate_password(reset_pwd1, user=None, password_validators=None)
    except ValidationError as msg:
        return JsonResponse({'status': 1, 'msg': f'{msg}', 'data': []})

    engine = get_engine(instance=instance)
    exec_result = engine.execute(db_name='mysql',
                                 sql=f"ALTER USER {user_host} IDENTIFIED BY '{reset_pwd1}';")
    if exec_result.error:
        result = {'status': 1, 'msg': exec_result.error}
        return HttpResponse(json.dumps(result), content_type='application/json')
    # 保存到数据库
    else:
        InstanceAccount.objects.update_or_create(instance=instance, user=user, host=host,
                                                 defaults={'password': reset_pwd1})
    return JsonResponse({'status': 0, 'msg': '', 'data': []})


@permission_required('sql.instance_account_manage', raise_exception=True)
def lock(request):
    """锁定/解锁账号"""
    instance_id = request.POST.get('instance_id', 0)
    user_host = request.POST.get('user_host')
    is_locked = request.POST.get('is_locked')
    lock_sql = ''

    if not all([user_host]):
        return JsonResponse({'status': 1, 'msg': '参数不完整，请确认后提交', 'data': []})

    try:
        instance = user_instances(request.user, db_type=['mysql']).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '你所在组未关联该实例', 'data': []})

    # escape
    user_host = MySQLdb.escape_string(user_host).decode('utf-8')

    if is_locked == 'N':
        lock_sql = f"ALTER USER {user_host} ACCOUNT LOCK;"
    elif is_locked == 'Y':
        lock_sql = f"ALTER USER {user_host} ACCOUNT UNLOCK;"

    engine = get_engine(instance=instance)
    exec_result = engine.execute(db_name='mysql', sql=lock_sql)
    if exec_result.error:
        return JsonResponse({'status': 1, 'msg': exec_result.error})
    return JsonResponse({'status': 0, 'msg': '', 'data': []})


@permission_required('sql.instance_account_manage', raise_exception=True)
def delete(request):
    """删除账号"""
    instance_id = request.POST.get('instance_id', 0)
    user_host = request.POST.get('user_host')
    user = request.POST.get('user')
    host = request.POST.get('host')

    if not all([user_host]):
        return JsonResponse({'status': 1, 'msg': '参数不完整，请确认后提交', 'data': []})

    try:
        instance = user_instances(request.user, db_type=['mysql']).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '你所在组未关联该实例', 'data': []})

    # escape
    user_host = MySQLdb.escape_string(user_host).decode('utf-8')

    engine = get_engine(instance=instance)
    exec_result = engine.execute(db_name='mysql', sql=f"DROP USER {user_host};")
    if exec_result.error:
        return JsonResponse({'status': 1, 'msg': exec_result.error})
    # 删除数据库对应记录
    else:
        InstanceAccount.objects.filter(instance=instance, user=user, host=host).delete()
    return JsonResponse({'status': 0, 'msg': '', 'data': []})
