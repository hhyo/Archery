# -*- coding: UTF-8 -*-
import MySQLdb
import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from django.http import HttpResponse, JsonResponse
from sql.utils.instance_management import (
    SUPPORTED_MANAGEMENT_DB_TYPE,
    get_instanceaccount_unique_value,
    get_instanceaccount_unique_key,
)
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine, ResultSet
from sql.utils.resource_group import user_instances
from .models import Instance, InstanceAccount


@permission_required("sql.menu_instance_account", raise_exception=True)
def users(request):
    """获取实例用户列表"""
    instance_id = request.POST.get("instance_id")
    saved = True if request.POST.get("saved") == "true" else False  # 平台是否保存

    if not instance_id:
        return JsonResponse({"status": 0, "msg": "", "data": []})
    try:
        instance = user_instances(
            request.user, db_type=SUPPORTED_MANAGEMENT_DB_TYPE
        ).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({"status": 1, "msg": "你所在组未关联该实例", "data": []})

    # 获取已录入用户
    cnf_users = dict()
    for user in InstanceAccount.objects.filter(instance=instance).values(
        "id", "user", "host", "db_name", "remark"
    ):
        user["saved"] = True
        cnf_users[get_instanceaccount_unique_value(instance.db_type, user)] = user
    # 获取所有用户
    query_engine = get_engine(instance=instance)
    query_result = query_engine.get_instance_users_summary()
    if not query_result.error:
        rows = []
        key = get_instanceaccount_unique_key(db_type=instance.db_type)
        for row in query_result.rows:
            # 合并数据
            if row[key] in cnf_users.keys():
                row = dict(row, **cnf_users[row[key]])
            rows.append(row)
        # 过滤参数
        if saved:
            rows = [row for row in rows if row["saved"]]

        result = {"status": 0, "msg": "ok", "rows": rows}
    else:
        result = {"status": 1, "msg": query_result.error}

    # 关闭连接
    query_engine.close()
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@permission_required("sql.instance_account_manage", raise_exception=True)
def create(request):
    """创建数据库账号"""
    instance_id = request.POST.get("instance_id", 0)
    db_name = request.POST.get("db_name")
    user = request.POST.get("user")
    host = request.POST.get("host")
    password1 = request.POST.get("password1")
    password2 = request.POST.get("password2")
    remark = request.POST.get("remark", "")

    try:
        instance = user_instances(
            request.user, db_type=SUPPORTED_MANAGEMENT_DB_TYPE
        ).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({"status": 1, "msg": "你所在组未关联该实例", "data": []})

    if (
        instance.db_type == "mysql" and not all([user, host, password1, password2])
    ) or (
        instance.db_type == "mongo" and not all([db_name, user, password1, password2])
    ):
        return JsonResponse(
            {"status": 1, "msg": "参数不完整，请确认后提交", "data": []}
        )

    if password1 != password2:
        return JsonResponse({"status": 1, "msg": "两次输入密码不一致", "data": []})

    # TODO 目前使用系统自带验证，后续实现验证器校验
    try:
        validate_password(password1, user=None, password_validators=None)
    except ValidationError as msg:
        return JsonResponse({"status": 1, "msg": f"{msg}", "data": []})

    engine = get_engine(instance=instance)
    exec_result = engine.create_instance_user(
        db_name=db_name, user=user, host=host, password1=password1, remark=remark
    )
    # 关闭连接
    engine.close()
    if exec_result.error:
        return JsonResponse({"status": 1, "msg": exec_result.error})

    # 保存到数据库
    else:
        accounts = [InstanceAccount(**row) for row in exec_result.rows]
        InstanceAccount.objects.bulk_create(accounts)

    return JsonResponse({"status": 0, "msg": "", "data": []})


@permission_required("sql.instance_account_manage", raise_exception=True)
def edit(request):
    """修改、录入数据库账号"""
    instance_id = request.POST.get("instance_id", 0)
    db_name = request.POST.get("db_name", "")
    user = request.POST.get("user")
    host = request.POST.get("host", "")
    password = request.POST.get("password")
    remark = request.POST.get("remark", "")

    try:
        instance = user_instances(
            request.user, db_type=SUPPORTED_MANAGEMENT_DB_TYPE
        ).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({"status": 1, "msg": "你所在组未关联该实例", "data": []})

    if (instance.db_type == "mysql" and not all([user, host])) or (
        instance.db_type == "mongo" and not all([db_name, user])
    ):
        return JsonResponse(
            {"status": 1, "msg": "参数不完整，请确认后提交", "data": []}
        )

    # 保存到数据库
    if password:
        InstanceAccount.objects.update_or_create(
            instance=instance,
            user=user,
            host=host,
            db_name=db_name,
            defaults={"password": password, "remark": remark},
        )
    else:
        InstanceAccount.objects.update_or_create(
            instance=instance,
            user=user,
            host=host,
            db_name=db_name,
            defaults={"remark": remark},
        )
    return JsonResponse({"status": 0, "msg": "", "data": []})


@permission_required("sql.instance_account_manage", raise_exception=True)
def grant(request):
    """获取用户权限变更语句，并执行权限变更"""
    instance_id = request.POST.get("instance_id", 0)
    grant_sql = ""

    try:
        instance = user_instances(
            request.user, db_type=SUPPORTED_MANAGEMENT_DB_TYPE
        ).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({"status": 1, "msg": "你所在组未关联该实例", "data": []})

    engine = get_engine(instance=instance)
    if instance.db_type == "mysql":
        user_host = request.POST.get("user_host")
        op_type = request.POST.get("op_type")
        priv_type = request.POST.get("priv_type")
        try:
            privs = json.loads(request.POST.get("privs"))
        except Exception:
            return JsonResponse({"status": 1, "msg": "权限参数不合法", "data": []})
        db_name = request.POST.getlist("db_name[]") or request.POST.get("db_name")
        tb_name = request.POST.getlist("tb_name[]") or request.POST.get("tb_name")
        col_name = request.POST.getlist("col_name[]")
        exec_result = engine.grant_instance_user(
            user_host=user_host,
            op_type=op_type,
            priv_type=priv_type,
            privs=privs,
            db_names=db_name,
            tb_names=tb_name,
            col_names=col_name,
        )
    elif instance.db_type == "mongo":
        db_name_user = request.POST.get("db_name_user")
        roles = request.POST.getlist("roles[]")
        arr = db_name_user.split(".")
        db_name = arr[0]
        user = arr[1]
        exec_result = ResultSet()
        try:
            conn = engine.get_connection()
            conn[db_name].command("updateUser", user, roles=roles)
        except Exception as e:
            exec_result.error = str(e)

    # 关闭连接
    engine.close()
    if exec_result.error:
        return JsonResponse({"status": 1, "msg": exec_result.error})
    grant_sql = exec_result.full_sql
    return JsonResponse({"status": 0, "msg": "", "data": grant_sql})


@permission_required("sql.instance_account_manage", raise_exception=True)
def reset_pwd(request):
    """创建数据库账号"""
    instance_id = request.POST.get("instance_id", 0)
    db_name_user = request.POST.get("db_name_user")
    db_name = request.POST.get("db_name", "")
    user_host = request.POST.get("user_host")
    user = request.POST.get("user")
    host = request.POST.get("host", "")
    reset_pwd1 = request.POST.get("reset_pwd1")
    reset_pwd2 = request.POST.get("reset_pwd2")

    try:
        instance = user_instances(
            request.user, db_type=SUPPORTED_MANAGEMENT_DB_TYPE
        ).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({"status": 1, "msg": "你所在组未关联该实例", "data": []})

    if (
        instance.db_type == "mysql" and not all([user, host, reset_pwd1, reset_pwd2])
    ) or (
        instance.db_type == "mongo" and not all([db_name, user, reset_pwd1, reset_pwd2])
    ):
        return JsonResponse(
            {"status": 1, "msg": "参数不完整，请确认后提交", "data": []}
        )

    if reset_pwd1 != reset_pwd2:
        return JsonResponse({"status": 1, "msg": "两次输入密码不一致", "data": []})

    # TODO 目前使用系统自带验证，后续实现验证器校验
    try:
        validate_password(reset_pwd1, user=None, password_validators=None)
    except ValidationError as msg:
        return JsonResponse({"status": 1, "msg": f"{msg}", "data": []})

    engine = get_engine(instance=instance)
    exec_result = engine.reset_instance_user_pwd(
        user_host=user_host, db_name_user=db_name_user, reset_pwd=reset_pwd1
    )
    # 关闭连接
    engine.close()
    if exec_result.error:
        result = {"status": 1, "msg": exec_result.error}
        return HttpResponse(json.dumps(result), content_type="application/json")
    # 保存到数据库
    else:
        InstanceAccount.objects.update_or_create(
            instance=instance,
            user=user,
            host=host,
            db_name=db_name,
            defaults={"password": reset_pwd1},
        )

    return JsonResponse({"status": 0, "msg": "", "data": []})


@permission_required("sql.instance_account_manage", raise_exception=True)
def lock(request):
    """锁定/解锁账号"""
    instance_id = request.POST.get("instance_id", 0)
    user_host = request.POST.get("user_host")
    is_locked = request.POST.get("is_locked")
    lock_sql = ""

    if not all([user_host]):
        return JsonResponse(
            {"status": 1, "msg": "参数不完整，请确认后提交", "data": []}
        )

    try:
        instance = user_instances(request.user, db_type=["mysql"]).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({"status": 1, "msg": "你所在组未关联该实例", "data": []})

    engine = get_engine(instance=instance)
    exec_result = engine.set_instance_user_lock(
        user_host=user_host, is_locked=is_locked
    )
    if exec_result.error:
        return JsonResponse({"status": 1, "msg": exec_result.error})
    return JsonResponse({"status": 0, "msg": "", "data": []})


@permission_required("sql.instance_account_manage", raise_exception=True)
def delete(request):
    """删除账号"""
    instance_id = request.POST.get("instance_id", 0)
    db_name_user = request.POST.get("db_name_user")
    db_name = request.POST.get("db_name")
    user_host = request.POST.get("user_host")
    user = request.POST.get("user")
    host = request.POST.get("host")

    try:
        instance = user_instances(
            request.user, db_type=SUPPORTED_MANAGEMENT_DB_TYPE
        ).get(id=instance_id)
    except Instance.DoesNotExist:
        return JsonResponse({"status": 1, "msg": "你所在组未关联该实例", "data": []})

    if (instance.db_type == "mysql" and not all([user_host])) or (
        instance.db_type == "mongo" and not all([db_name_user])
    ):
        return JsonResponse(
            {"status": 1, "msg": "参数不完整，请确认后提交", "data": []}
        )

    engine = get_engine(instance=instance)
    exec_result = engine.drop_instance_user(
        user_host=user_host, db_name_user=db_name_user
    )
    # 关闭连接
    engine.close()
    if exec_result.error:
        return JsonResponse({"status": 1, "msg": exec_result.error})
    # 删除数据库对应记录
    else:
        InstanceAccount.objects.filter(
            instance=instance, user=user, host=host, db_name=db_name
        ).delete()

    return JsonResponse({"status": 0, "msg": "", "data": []})
