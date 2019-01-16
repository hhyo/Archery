# -*- coding: UTF-8 -*-
# https://www.programcreek.com/python/example/59413/redis.StrictRedis
import redis
import re
import datetime

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse, QueryDict
from django.db.models import Q
from django.contrib.auth.models import Permission
from sql.utils.ding_api import DingSender
from .models import Instance, RedisApply
from common.utils.extend_json_encoder import ExtendJSONEncoder


safe_cmd = ["exists", "ttl", "pttl", "type", "get", "mget", "strlen",
             "hgetall", "hexists", "hget", "hmget", "keys", "hkeys", "hvals",
             "smembers", "scard", "sdiff", "sunion", "sismember"]


@permission_required('sql.redis_view', raise_exception=True)
def redis_query(request):
    redis_id = request.POST.get('redis_id', '')
    db = request.POST.get('db', 0)
    cmd = request.POST.get('cmd', '').strip()
    comment = request.POST.get('comment', '').strip()
    try:
        if redis_id and cmd:
            ro = Instance.objects.get(id=redis_id)
            if re.match(r'keys\s+\\*$', cmd, re.I):
                result = "这个命令太危险！无法执行！"
            elif cmd.split(" ")[0].lower() in safe_cmd:
                if ro.password:
                    rs = redis.StrictRedis(host=ro.ip, port=ro.port, password=ro.raw_password, db=int(db))
                else:
                    rs = redis.StrictRedis(host=ro.ip, port=ro.port, db=int(db))
                result = rs.execute_command(cmd)
                result = "None" if result is None else str(result)
            elif request.user.has_perm("sql.redis_edit"):
                if ro.password:
                    rs = redis.StrictRedis(host=ro.ip, port=ro.port, password=ro.raw_password, db=int(db))
                else:
                    rs = redis.StrictRedis(host=ro.ip, port=ro.port, db=int(db))
                result = rs.execute_command(cmd)
                result = "None" if result is None else str(result)
                # 管理员执行设置语句，也记录下来
                RedisApply.objects.create(redis=ro, db=db, command=cmd, status=1, applicant=request.user,
                                          auditor=request.user, comment=comment, result=result)
            else:
                RedisApply.objects.create(redis=ro, db=db, command=cmd, status=0, applicant=request.user,
                                          comment=comment)
                msg = """Redis 数据更变审核\n实例：{}\nIP：{}\n端口：{}\n执行命令：{}\n申请人：{}""".format(ro.hostname, ro.ip,
                                                                                    ro.port, cmd, request.user.username)
                for p in Permission.objects.filter(codename='redis_edit'):
                    for g in p.group_set.all():
                        for u in g.user_set.all():
                            DingSender().send_msg(u.ding_user_id, msg)

                result = "非查询命令需管理员审核！"
            res = {"code": 0, "result": result}
        else:
            res = {"code": 1, "errmsg": "非法调用"}
    except Instance.DoesNotExist:
        res = {"code": 1, "errmsg": str('Redis.DoesNotExist')}
    except Exception as e:
        res = {"code": 1, "errmsg": str(e)}
    return HttpResponse(json.dumps(res, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.redis_view', raise_exception=True)
def redis_apply_list(request):
    limit = int(request.POST.get('limit', 0))
    offset = int(request.POST.get('offset', 0))
    redis_id = request.POST.get('redis_id', '')
    search = request.POST.get('search', '')
    if request.user.has_perm("sql.redis_edit"):
        if redis_id:
            obj_list = RedisApply.objects.filter(redis_id=redis_id)
        else:
            obj_list = RedisApply.objects.get_queryset()
    else:
        if redis_id:
            obj_list = RedisApply.objects.filter(redis_id=redis_id).filter(applicant=request.user)
        else:
            obj_list = RedisApply.objects.filter(applicant=request.user)
    if search:
        obj_list = obj_list.filter(Q(redis__hostname__contains=search) | Q(command__contains=search))

    res = list()
    for r in obj_list[offset:(offset + limit)]:
        res.append({"id": r.id, "hostname": r.redis.hostname, "db": r.db, "command": r.command,
                    "applicant": r.applicant.username,
                    "auditor": r.auditor.username if r.auditor else "", "audit_msg": r.audit_msg,
                    "comment": r.comment, "status": r.status,
                    "result": r.result, "create_time": r.create_time})
    result = {'total': len(obj_list), 'rows': res}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.redis_view', raise_exception=True)
def redis_apply_audit(request):
    if request.method == 'GET':
        redis_apply_id = request.GET.get('id', None)
        try:
            if redis_apply_id:
                result = RedisApply.objects.get(id=redis_apply_id).audit_msg
            else:
                result = "未查到该申请！"
        except RedisApply.DoesNotExist:
            result = "未查到该申请！"
    if request.method == 'POST':
        redis_apply_id = request.POST.get('id', None)
        audit_msg = request.POST.get('audit_msg', "")
        is_allow = request.POST.get('is_allow', "")
        is_cancel = request.POST.get('is_cancel', "")
        try:
            ra = RedisApply.objects.get(id=redis_apply_id)
            ro = ra.redis
            if is_cancel == "yes":
                # 主动取消申请
                RedisApply.objects.filter(id=redis_apply_id).update(audit_msg=audit_msg, status=3)
                result = "取消成功"
            elif is_allow == "no":
                # 申请被拒绝
                RedisApply.objects.filter(id=redis_apply_id).update(audit_msg=audit_msg, status=2)
                msg = """Redis 数据更变申请已被拒绝\n实例：{}\nIP：{}\n端口：{}\n执行命令：{}\n审核人：{}\n拒绝原因：{}""".format(
                    ro.hostname, ro.ip, ro.port, ra.command, request.user.username, ra.audit_msg)
                DingSender().send_msg(ra.applicant.ding_user_id, msg)
                result = "申请已拒绝"
            elif is_allow == "yes" and redis_apply_id:
                if not request.user.has_perm("sql.redis_edit"):
                    return HttpResponse("您无权审核！")
                try:
                    if ro.password:
                        rs = redis.StrictRedis(host=ro.ip, port=ro.port, password=ro.raw_password, db=ra.db)
                    else:
                        rs = redis.StrictRedis(host=ro.ip, port=ro.port, db=ra.db)
                    result = rs.execute_command(ra.command)
                    result = "None" if not result else str(result)
                    ra.audit_msg = audit_msg
                    ra.auditor = request.user
                    ra.result = str(result)
                    ra.status = 1
                    ra.save()
                except Exception as e:
                    result = str(e)
                    ra.result = str(e)
                    ra.status = 1
                    ra.save()
                msg = """Redis 数据更变申请已执行完毕\n实例：{}\nIP：{}\n端口：{}\n执行命令：{}\n审核人：{}\n返回：{}""".format(
                    ro.hostname, ro.ip, ro.port, ra.command, request.user.username, ra.result)
                DingSender().send_msg(ra.applicant.ding_user_id, msg)
            else:
                result = "非法调用！"
        except RedisApply.DoesNotExist:
            result = "未查到该申请！"
        except Exception as e:
            result = str(e)
    return HttpResponse(result)
