# -*- coding: UTF-8 -*-
import logging
import re
import time
import traceback
import simplejson
from django.shortcuts import render
from django.contrib.auth.decorators import permission_required
from django.db import connection
from django.core import serializers
from django.http import HttpResponse
from django.db.models import Q
from sql.engines import get_engine
from sql.utils.resource_group import  user_instances
from inspur.models import UpdateLog
import simplejson as json
from common.utils.extend_json_encoder import ExtendJSONEncoder
from inspur.mysql_exec import mysql_exec

logger = logging.getLogger('default')

@permission_required('inspur.menu_sqlupdate', raise_exception=True)
def sqlupdate1(request):
    
    # 获取用户关联实例列表
    instances = [instance_name for instance_name in user_instances(request.user)]
    if request.POST.get('fiter')=='请输入数据库名称！':
        dbfiter = 'liu'
    elif (request.POST.get('fiter')):
        dbfiter = request.POST.get('fiter')
    else:
        dbfiter='liu'
    context = {'instances': instances}
    database_list = []
    for instance_name in instances:
            query_engine = get_engine(instance=instance_name)
            db_list = query_engine.get_all_databases().rows
            if dbfiter=='liu':
                instance_list = {'instance': instance_name, 'database': db_list}
                database_list.append(instance_list)
            else:

                for db in db_list:
                    if db == dbfiter:
                        newdb=[]
                        newdb.append(db)
                        instance_list = {'instance': instance_name, 'database': newdb}
                        print(instance_list)
                        database_list.append(instance_list)
                        print(database_list)
    return render(request, 'sqlupdate1.html', {'database_list': database_list})

def updatelog_save(username, db_name, instance_name, sql_content, cost_time, sql_result):

    # 成功的查询语句记录存入数据库

    update_log = UpdateLog()
    update_log.username = username
    update_log.db_name = db_name
    update_log.instance_name = instance_name
    update_log.sqllog = sql_content
    update_log.cost_time = cost_time
    update_log.effect_row = sql_result

    # 防止更新超时
    try:
        update_log.save()
    except:
        connection.close()
        update_log.save()


@permission_required('inspur.menu_sqlupdate', raise_exception=True)
def updatelog(request):
    # 获取用户信息
    user = request.user
    search = request.POST.get('search', '')
    # 查询个人记录，超管查看所有数据
    if user.is_superuser:
        sql_log_count = UpdateLog.objects.all().filter(
            Q(sqllog__contains=search) | Q(user_display__contains=search)).count()
        sql_log_list = UpdateLog.objects.all().filter(
            Q(sqllog__contains=search) | Q(user_display__contains=search)).order_by(
            '-id')
    else:
        sql_log_count = UpdateLog.objects.filter(username=user.username).filter(sqllog__contains=search).count()
        sql_log_list = UpdateLog.objects.filter(username=user.username).filter(sqllog__contains=search).order_by('-id')

    # QuerySet 序列化
    sql_log_list = serializers.serialize("json", sql_log_list)
    sql_log_list = json.loads(sql_log_list)
    sql_log = [log_info['fields'] for log_info in sql_log_list]

    result = {"total": sql_log_count, "rows": sql_log}
    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


@permission_required('inspur.menu_sqlupdate', raise_exception=True)
def dbfiter(request):
    dbfiter = json.loads(request.POST.get('fiter'))
    print(dbfiter)
    # 获取用户关联实例列表
    instances = [instance_name for instance_name in user_instances(request.user)]

    context = {'instances': instances}
    database_list = []
    while len(database_list) < len(instances):
        for instance_name in instances:
            query_engine = get_engine(instance=instance_name)
            db_list = query_engine.get_all_databases()
            for db in db_list:
                if db == dbfiter:
                    instance_list = {'instance': instance_name, 'database': db}
                    database_list.append(instance_list)
    return render(request, 'sqlupdate1.html', {'database_list': database_list})

def updatelog_save(username, db_name, instance_name, sql_content, cost_time, sql_result):

    # 成功的查询语句记录存入数据库

    update_log = UpdateLog()
    update_log.username = username
    update_log.db_name = db_name
    update_log.instance_name = instance_name
    update_log.sqllog = sql_content
    update_log.cost_time = cost_time
    update_log.effect_row = sql_result

    # 防止更新超时
    try:
        update_log.save()
    except:
        connection.close()
        update_log.save()


@permission_required('inspur.menu_sqlupdate', raise_exception=True)
def updatelog(request):
    # 获取用户信息
    user = request.user

    search = request.POST.get('search', '')

    # 查询个人记录，超管查看所有数据
    if user.is_superuser:
        sql_log_count = UpdateLog.objects.all().filter(
            Q(sqllog__contains=search) | Q(user_display__contains=search)).count()
        sql_log_list = UpdateLog.objects.all().filter(
            Q(sqllog__contains=search) | Q(user_display__contains=search)).order_by(
            '-id')
    else:
        sql_log_count = UpdateLog.objects.filter(username=user.username).filter(sqllog__contains=search).count()
        sql_log_list = UpdateLog.objects.filter(username=user.username).filter(sqllog__contains=search).order_by('-id')

    # QuerySet 序列化
    sql_log_list = serializers.serialize("json", sql_log_list)
    sql_log_list = json.loads(sql_log_list)
    sql_log = [log_info['fields'] for log_info in sql_log_list]

    result = {"total": sql_log_count, "rows": sql_log}
    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


@permission_required('inspur.menu_sqlupdate', raise_exception=True)
def update1(request):
    db_list = simplejson.loads(request.POST.get('db_list'))
    sql_content = request.POST.get('sql_content')
    result = {'status': 0, 'msg':['ok'] , 'data': {}}
    resulttmp = {'status': 0, 'msg':['ok'] , 'data': {}}

    # 服务器端参数验证
    if sql_content is None or db_list is None:
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')
    sql_content = sql_content.strip()
    # 获取用户信息
    user = request.user

    # 过滤注释语句和非查询的语句
    sql_content = ''.join(
        map(lambda x: re.compile(r'(^--\s+.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
            sql_content.splitlines(1))).strip()
    # 去除空行
    sql_content = re.sub('[\r\n\f]{2,}', '\n', sql_content)
    sql_list = sql_content.strip().split(';')
    for i in range(sql_list.count('')):
        sql_list.remove('')
    sql_list = [sql.replace('\n','').strip() for sql in sql_list]


    for sql in sql_list:
        if re.match(r"^delete|^create|^alter", sql.lower()):
            #pass
            continue
        else:
            result['status'] = 1
            result['msg'] = '仅支持^delete|^create|^alter，请联系管理员！'
            return HttpResponse(json.dumps(result), content_type='application/json')

    # 按照分号截取第一条有效sql执行
    #sql_content = sql_content.strip().split(';')[0]

    sql_log_bin='set sql_log_bin = 0;'
    for sql in sql_list:
         if re.match(r"^delete|^alter", sql.lower()):
             sql_content = sql_log_bin + sql_content
    try:
        # 查询权限校验
        if re.match(r"^explain", sql_content.lower()):
            limit_num = 0
        # 对查询sql增加limit限制
        if re.match(r"^select", sql_content.lower()):
            if re.search(r"limit\s+(\d+)$", sql_content.lower()) is None:
                if re.search(r"limit\s+\d+\s*,\s*(\d+)$", sql_content.lower()) is None:
                    sql_content = sql_content + ' limit ' + str(limit_num)

        # 执行更新语句,统计执行时间

        sql_result={}
        for i in range(len(db_list)):
            t_start = time.time()
            sql_result = mysql_exec(instance_name=db_list[str(i)]["instance"]).execute(db_list[str(i)]["db"], sql_content)
            t_end = time.time()
            cost_time = "%5s" % "{:.4f}".format(t_end - t_start)
            if  sql_result:
                resulttmp['msg']= '实例名'+db_list[str(i)]["instance"]+':数据库名'+db_list[str(i)]["db"]+" 错误信息"+str(sql_result)
                resulttmp['msg']
                if 'ok' in result['msg']:
                    result['msg'][0]=resulttmp['msg']
                else:
                    result['msg'].append(resulttmp['msg'])

            if sql_result:
                sql_result=str(sql_result)
            else:
                sql_result='ok'
            updatelog_save(user,db_list[str(i)]["db"],db_list[str(i)]["instance"],sql_content,cost_time,sql_result)
            result['status'] = 1
        for i in range(result['msg'].count(' ')):
            result['msg'].remove('\'')
        result['data'] = sql_result
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = str(e)

    # 返回查询结果
    try:
        return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),content_type='application/json')
    except Exception:
        return HttpResponse(json.dumps(result, default=str, bigint_as_string=True, encoding='latin1'),content_type='application/json')