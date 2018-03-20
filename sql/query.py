import re

import simplejson as json

from django.db.models import Q, Min
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.core import serializers
from django.db import transaction
from datetime import date
import datetime
import time

from .aes_decryptor import Prpcrypt
from .sendmail import MailSender
from .dao import Dao
from .const import WorkflowDict
from .inception import InceptionDao
from .models import users, slave_config, QueryPrivilegesApply, QueryPrivileges, QueryLog
from .data_masking import Masking
from .workflow import Workflow

dao = Dao()
prpCryptor = Prpcrypt()
inceptionDao = InceptionDao()
datamasking = Masking()
workflowOb = Workflow()
mailSenderOb = MailSender()


# 管理员操作权限验证
def superuser_required(func):
    def wrapper(request, *args, **kw):
        # 获取用户信息，权限验证
        loginUser = request.session.get('login_username', False)
        loginUserOb = users.objects.get(username=loginUser)

        if loginUserOb.is_superuser is False:
            if request.is_ajax():
                finalResult = {'status': 1, 'msg': '您无权操作，请联系管理员', 'data': []}
                return HttpResponse(json.dumps(finalResult), content_type='application/json')
            else:
                context = {'errMsg': "您无权操作，请联系管理员"}
                return render(request, "error.html", context)

        return func(request, *args, **kw)

    return wrapper


# 角色操作权限验证
def role_required(roles=()):
    def _deco(func):
        def wrapper(request, *args, **kw):
            # 获取用户信息，权限验证
            loginUser = request.session.get('login_username', False)
            loginUserOb = users.objects.get(username=loginUser)
            loginrole = loginUserOb.role

            if loginrole not in roles and loginUserOb.is_superuser is False:
                if request.is_ajax():
                    finalResult = {'status': 1, 'msg': '您无权操作，请联系管理员', 'data': []}
                    return HttpResponse(json.dumps(finalResult), content_type='application/json')
                else:
                    context = {'errMsg': "您无权操作，请联系管理员"}
                    return render(request, "error.html", context)

            return func(request, *args, **kw)

        return wrapper

    return _deco


# 处理查询结果的时间格式
class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        else:
            return json.JSONEncoder.default(self, obj)


# 查询权限申请用于工作流审核回调
def query_audit_call_back(workflow_id, workflow_status):
    # 更新业务表状态
    apply_info = QueryPrivilegesApply()
    apply_info.apply_id = workflow_id
    apply_info.status = workflow_status
    apply_info.save(update_fields=['status'])
    # 审核通过插入权限信息，批量插入，减少性能消耗
    if workflow_status == WorkflowDict.workflow_status['audit_success']:
        apply_queryset = QueryPrivilegesApply.objects.get(apply_id=workflow_id)
        insertlist = [QueryPrivileges(
            user_name=apply_queryset.user_name, cluster_id=apply_queryset.cluster_id,
            cluster_name=apply_queryset.cluster_name, db_name=apply_queryset.db_name,
            table_name=table_name, valid_date=apply_queryset.valid_date,
            limit_num=apply_queryset.limit_num) for table_name in
            apply_queryset.table_list.split(',')]
        QueryPrivileges.objects.bulk_create(insertlist)


# 获取所有集群名称
@csrf_exempt
def getClusterList(request):
    slaves = slave_config.objects.all().order_by('cluster_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 获取所有集群名称
    listAllClusterName = [slave.cluster_name for slave in slaves]
    result['data'] = listAllClusterName

    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取集群里面的数据库集合
@csrf_exempt
def getdbNameList(request):
    clusterName = request.POST.get('cluster_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    slave_info = slave_config.objects.get(cluster_name=clusterName)
    # 取出该集群的连接方式，为了后面连进去获取所有databases
    listDb = dao.getAlldbByCluster(slave_info.slave_host, slave_info.slave_port, slave_info.slave_user,
                                   prpCryptor.decrypt(slave_info.slave_password))

    # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
    result['data'] = listDb
    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取数据库的表集合
@csrf_exempt
def getTableNameList(request):
    clusterName = request.POST.get('cluster_name')
    db_name = request.POST.get('db_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    slave_info = slave_config.objects.get(cluster_name=clusterName)
    # 取出该集群的连接方式，为了后面连进去获取所有的表
    listTb = dao.getAllTableByDb(slave_info.slave_host, slave_info.slave_port, slave_info.slave_user,
                                 prpCryptor.decrypt(slave_info.slave_password), db_name)
    # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
    result['data'] = listTb
    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取表里面的字段集合
@csrf_exempt
def getColumnNameList(request):
    clusterName = request.POST.get('cluster_name')
    db_name = request.POST.get('db_name')
    tb_name = request.POST.get('tb_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    slave_info = slave_config.objects.get(cluster_name=clusterName)
    # 取出该集群的连接方式，为了后面连进去获取表的所有字段
    listCol = dao.getAllColumnsByTb(slave_info.slave_host, slave_info.slave_port, slave_info.slave_user,
                                    prpCryptor.decrypt(slave_info.slave_password), db_name, tb_name)
    # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
    result['data'] = listCol
    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取查询权限申请列表
@csrf_exempt
def getqueryapplylist(request):
    # 获取用户信息
    loginUser = request.session.get('login_username', False)
    loginUserOb = users.objects.get(username=loginUser)

    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit

    # 获取搜索参数
    search = request.POST.get('search')
    if search is None:
        search = ''

    # 审核列表跳转
    workflow_id = request.POST.get('workflow_id')
    # 获取列表数据,申请人只能查看自己申请的数据,管理员可以看到全部数据
    if workflow_id != '0':
        # 判断权限
        audit_users = workflowOb.auditinfobyworkflow_id(workflow_id, WorkflowDict.workflow_type['query']).audit_users
        if loginUserOb.is_superuser or loginUserOb.username in audit_users.split(','):
            applylist = QueryPrivilegesApply.objects.filter(apply_id=workflow_id)
            applylistCount = QueryPrivilegesApply.objects.filter(apply_id=workflow_id).count()
        else:
            applylist = QueryPrivilegesApply.objects.filter(apply_id=workflow_id, user_name=loginUser)
            applylistCount = QueryPrivilegesApply.objects.filter(apply_id=workflow_id, user_name=loginUser).count()
    elif loginUserOb.is_superuser:
        applylist = QueryPrivilegesApply.objects.all().filter(title__contains=search).order_by('-apply_id')[
                    offset:limit]
        applylistCount = QueryPrivilegesApply.objects.all().filter(title__contains=search).count()
    else:
        applylist = QueryPrivilegesApply.objects.filter(user_name=loginUserOb.username).filter(
            title__contains=search).order_by('-apply_id')[offset:limit]
        applylistCount = QueryPrivilegesApply.objects.filter(user_name=loginUserOb.username).filter(
            title__contains=search).count()

    # QuerySet 序列化
    applylist = serializers.serialize("json", applylist)
    applylist = json.loads(applylist)
    applylist_result = [apply_info['fields'] for apply_info in applylist]

    result = {"total": applylistCount, "rows": applylist_result}
    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 申请查询权限
@csrf_exempt
def applyforprivileges(request):
    title = request.POST['title']
    cluster_name = request.POST['cluster_name']
    db_name = request.POST['db_name']
    table_list = request.POST['table_list']
    valid_date = request.POST['valid_date']
    limit_num = request.POST['limit_num']
    try:
        workflow_remark = request.POST['apply_remark']
    except Exception:
        workflow_remark = ''

    # 获取用户信息
    loginUser = request.session.get('login_username', False)

    # 服务端参数校验
    result = {'status': 0, 'msg': 'ok', 'data': []}
    if title is None or cluster_name is None or db_name is None or valid_date is None or table_list is None:
        result['status'] = 1
        result['msg'] = '请填写完整'
        return HttpResponse(json.dumps(result), content_type='application/json')

    table_list = table_list.split(',')
    # 通过cluster_name获取cluster_id
    cluster_id = slave_config.objects.get(cluster_name=cluster_name).cluster_id

    # 检查申请账号是否已拥有该表的查询权限
    own_tables = QueryPrivileges.objects.filter(cluster_id=cluster_id, user_name=loginUser, db_name=db_name,
                                                table_name__in=table_list, valid_date__gte=datetime.datetime.now(),
                                                is_deleted=0).values('table_name')
    own_table_list = [table_info['table_name'] for table_info in own_tables]
    if own_table_list is None:
        pass
    else:
        for table_name in table_list:
            if table_name in own_table_list:
                result['status'] = 1
                result['msg'] = '你已拥有' + cluster_name + '集群' + db_name + '.' + table_name + '表的查询权限，不能重复申请'
                return HttpResponse(json.dumps(result), content_type='application/json')

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 保存申请信息到数据库
            applyinfo = QueryPrivilegesApply()
            applyinfo.title = title
            applyinfo.user_name = loginUser
            applyinfo.cluster_id = cluster_id
            applyinfo.cluster_name = cluster_name
            applyinfo.db_name = db_name
            applyinfo.table_list = ','.join(table_list)
            applyinfo.valid_date = valid_date
            applyinfo.status = WorkflowDict.workflow_status['audit_wait']  # 待审核
            applyinfo.limit_num = limit_num
            applyinfo.create_user = loginUser
            applyinfo.save()
            apply_id = applyinfo.apply_id

            # 调用工作流插入审核信息,查询权限申请workflow_type=2
            auditresult = workflowOb.addworkflowaudit(request, WorkflowDict.workflow_type['query'], apply_id,
                                                      title, loginUser, workflow_remark)

            if auditresult['status'] == 0:
                # 更新业务表审核状态,判断是否插入权限信息
                query_audit_call_back(apply_id, auditresult['data']['workflow_status'])
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)
    else:
        result = auditresult
    return HttpResponse(json.dumps(result), content_type='application/json')


# 用户的查询权限管理
@csrf_exempt
def getuserprivileges(request):
    user_name = request.POST.get('user_name')
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit

    # 获取搜索参数
    search = request.POST.get('search')
    if search is None:
        search = ''

    # 判断权限，除了管理员外其他人只能查看自己的权限信息
    result = {'status': 0, 'msg': 'ok', 'data': []}
    loginUser = request.session.get('login_username', False)
    loginUserOb = users.objects.get(username=loginUser)

    # 获取用户的权限数据
    if loginUserOb.is_superuser:
        if user_name != 'all':
            privilegeslist = QueryPrivileges.objects.all().filter(user_name=user_name, is_deleted=0,
                                                                  table_name__contains=search).order_by(
                '-privilege_id')[offset:limit]
            privilegeslistCount = QueryPrivileges.objects.all().filter(user_name=user_name, is_deleted=0,
                                                                       table_name__contains=search).count()
        else:
            privilegeslist = QueryPrivileges.objects.all().filter(is_deleted=0, table_name__contains=search).order_by(
                '-privilege_id')[offset:limit]
            privilegeslistCount = QueryPrivileges.objects.all().filter(is_deleted=0,
                                                                       table_name__contains=search).count()
    else:
        privilegeslist = QueryPrivileges.objects.filter(user_name=loginUserOb.username, is_deleted=0).filter(
            table_name__contains=search).order_by('-privilege_id')[offset:limit]
        privilegeslistCount = QueryPrivileges.objects.filter(user_name=loginUserOb.username, is_deleted=0).filter(
            table_name__contains=search).count()

    # QuerySet 序列化
    privilegeslist = serializers.serialize("json", privilegeslist)
    privilegeslist = json.loads(privilegeslist)
    privilegeslist_result = []
    for i in range(len(privilegeslist)):
        privilegeslist[i]['fields']['id'] = privilegeslist[i]['pk']
        privilegeslist_result.append(privilegeslist[i]['fields'])

    result = {"total": privilegeslistCount, "rows": privilegeslist_result}
    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 变更权限信息
@csrf_exempt
@superuser_required
def modifyqueryprivileges(request):
    privilege_id = request.POST.get('privilege_id')
    type = request.POST.get('type')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # type=1删除权限,type=2变更权限
    privileges = QueryPrivileges()
    if int(type) == 1:
        # 删除权限
        privileges.privilege_id = int(privilege_id)
        privileges.is_deleted = 1
        privileges.save(update_fields=['is_deleted'])
        return HttpResponse(json.dumps(result), content_type='application/json')
    elif int(type) == 2:
        # 变更权限
        valid_date = request.POST.get('valid_date')
        limit_num = request.POST.get('limit_num')
        privileges.privilege_id = int(privilege_id)
        privileges.valid_date = valid_date
        privileges.limit_num = limit_num
        privileges.save(update_fields=['valid_date', 'limit_num'])
        return HttpResponse(json.dumps(result), content_type='application/json')


# 获取SQL查询结果
@csrf_exempt
def query(request):
    cluster_name = request.POST.get('cluster_name')
    sqlContent = request.POST.get('sql_content')
    dbName = request.POST.get('db_name')
    tb_name = request.POST.get('tb_name')
    limit_num = request.POST.get('limit_num')

    finalResult = {'status': 0, 'msg': 'ok', 'data': {}}

    # 服务器端参数验证
    if sqlContent is None or dbName is None:
        finalResult['status'] = 1
        finalResult['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')

    sqlContent = sqlContent.strip()
    if sqlContent[-1] != ";":
        finalResult['status'] = 1
        finalResult['msg'] = 'SQL语句结尾没有以;结尾，请重新修改并提交！'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')

    # 获取用户信息
    loginUser = request.session.get('login_username', False)
    loginUserOb = users.objects.get(username=loginUser)

    # 过滤注释语句和非查询的语句
    sql_list = sqlContent.split('\n')
    for sql in sql_list:
        if re.match(r"^(\--|#)", sql):
            pass
        elif re.match(r"^select|^show.*create|^explain", sql.lower()):
            break
        else:
            finalResult['status'] = 1
            finalResult['msg'] = '仅支持^select|^show.*create|^explain语法，请联系管理员！'
            return HttpResponse(json.dumps(finalResult), content_type='application/json')

    # 取出该集群的连接方式,查询只读账号,按照分号截取第一条有效sql执行
    cluster_info = slave_config.objects.get(cluster_name=cluster_name)
    sqlContent = sqlContent.strip().split(';')[0]

    # 检查用户是否有该数据库/表的查询权限
    if loginUserOb.is_superuser:
        user_limit_num = 10000
        if int(limit_num) == 0:
            limit_num = user_limit_num
        else:
            limit_num = min(int(limit_num), user_limit_num)
        pass
    # 查看表结构和执行计划，inception会报错，故单独处理，explain直接跳过
    elif re.match(r"^show.*create", sqlContent.lower()):
        if re.match(r"^show.*create", sqlContent.lower()):
            tb_name = re.sub('^show.*create.*table', '', sqlContent, count=1, flags=0).strip()
        try:
            QueryPrivileges.objects.get(user_name=loginUser, cluster_name=cluster_name, db_name=dbName,
                                        table_name=tb_name, valid_date__gte=datetime.datetime.now(), is_deleted=0)
        except Exception:
            finalResult['status'] = 1
            finalResult['msg'] = '你无' + dbName + '.' + tb_name + '表的查询权限！请先到查询权限管理进行申请'
            return HttpResponse(json.dumps(finalResult), content_type='application/json')
    # sql查询
    else:
        # 先检查是否有该库的权限，防止inception的语法树打印错误时连库权限也未做校验
        privileges = QueryPrivileges.objects.filter(user_name=loginUser, cluster_name=cluster_name, db_name=dbName,
                                                    valid_date__gte=datetime.datetime.now(), is_deleted=0)
        if len(privileges) == 0:
            finalResult['status'] = 1
            finalResult['msg'] = '你无' + dbName + '数据库的查询权限！请先到查询权限管理进行申请'
            return HttpResponse(json.dumps(finalResult), content_type='application/json')

        # 首先使用inception的语法树打印获取查询涉及的的表
        table_ref_result = datamasking.query_table_ref(sqlContent + ';', cluster_name, dbName)

        # 正确拿到表数据
        if table_ref_result['status'] == 0:
            table_ref = table_ref_result['data']
            # 获取表信息,校验是否拥有全部表查询权限
            QueryPrivilegesOb = QueryPrivileges.objects.filter(user_name=loginUser, cluster_name=cluster_name)
            for table in table_ref:
                privileges = QueryPrivilegesOb.filter(db_name=table['db'], table_name=table['table'],
                                                      valid_date__gte=datetime.datetime.now(), is_deleted=0)
                if len(privileges) == 0:
                    finalResult['status'] = 1
                    finalResult['msg'] = '你无' + table['db'] + '.' + table['table'] + '表的查询权限！请先到查询权限管理进行申请'
                    return HttpResponse(json.dumps(finalResult), content_type='application/json')
        # 获取表数据报错，检查配置文件是否允许继续执行
        else:
            table_ref = None
            if hasattr(settings, 'CRITICAL_QUERY_ON_OFF') == True:
                if getattr(settings, 'CRITICAL_QUERY_ON_OFF') == "off":
                    return HttpResponse(json.dumps(table_ref_result), content_type='application/json')
                else:
                    pass

        # 获取查询涉及表的最小limit限制
        if loginUserOb.is_superuser:
            user_limit_num = 10000
        elif table_ref:
            db_list = [table_info['db'] for table_info in table_ref]
            table_list = [table_info['table'] for table_info in table_ref]
            user_limit_num = QueryPrivileges.objects.filter(user_name=loginUser,
                                                            cluster_name=cluster_name,
                                                            db_name__in=db_list,
                                                            table_name__in=table_list,
                                                            valid_date__gte=datetime.datetime.now(),
                                                            is_deleted=0).aggregate(Min('limit_num'))['limit_num__min']
        else:
            # 如果表没获取到则获取涉及库的最小limit限制
            user_limit_num = QueryPrivileges.objects.filter(user_name=loginUser,
                                                            cluster_name=cluster_name,
                                                            db_name=dbName,
                                                            valid_date__gte=datetime.datetime.now(),
                                                            is_deleted=0).aggregate(Min('limit_num'))['limit_num__min']
        if int(limit_num) == 0:
            limit_num = user_limit_num
        else:
            limit_num = min(int(limit_num), user_limit_num)

        # 对查询sql增加limit限制
        if re.search(r"limit[\f\n\r\t\v\s]+(\d+)$", sqlContent.lower()) is None:
            if re.search(r"limit[\f\n\r\t\v\s]+\d+[\f\n\r\t\v\s]*,[\f\n\r\t\v\s]*(\d+)$", sqlContent.lower()) is None:
                sqlContent = sqlContent + ' limit ' + str(limit_num)

    sqlContent = sqlContent + ';'

    # 执行查询语句,统计执行时间
    t_start = time.time()
    sql_result = dao.mysql_query(cluster_info.slave_host, cluster_info.slave_port, cluster_info.slave_user,
                                 prpCryptor.decrypt(cluster_info.slave_password), str(dbName), sqlContent, limit_num)
    t_end = time.time()
    cost_time = "%5s" % "{:.4f}".format(t_end - t_start)

    sql_result['cost_time'] = cost_time

    # 数据脱敏，同样需要检查配置，是否开启脱敏，语法树解析是否允许出错继续执行
    t_start = time.time()
    if getattr(settings, 'CRITICAL_DATA_MASKING_ON_OFF') == "on":
        # 仅对查询语句进行脱敏
        if re.match(r"^select", sqlContent.lower()):
            try:
                masking_result = datamasking.data_masking(cluster_name, dbName, sqlContent, sql_result)
            except Exception:
                if getattr(settings, 'CRITICAL_QUERY_ON_OFF') == "off":
                    finalResult['status'] = 1
                    finalResult['msg'] = '脱敏数据报错,请联系管理员'
                    return HttpResponse(json.dumps(finalResult), content_type='application/json')
            else:
                if masking_result['status'] != 0:
                    if getattr(settings, 'CRITICAL_QUERY_ON_OFF') == "off":
                        return HttpResponse(json.dumps(masking_result), content_type='application/json')

    t_end = time.time()
    masking_cost_time = "%5s" % "{:.4f}".format(t_end - t_start)

    sql_result['masking_cost_time'] = masking_cost_time

    finalResult['data'] = sql_result

    # 成功的查询语句记录存入数据库
    if sql_result.get('Error'):
        pass
    else:
        query_log = QueryLog()
        query_log.username = loginUser
        query_log.db_name = dbName
        query_log.cluster_id = cluster_info.cluster_id
        query_log.cluster_name = cluster_info.cluster_name
        query_log.sqllog = sqlContent
        if int(limit_num) == 0:
            limit_num = int(sql_result['effect_row'])
        else:
            limit_num = min(int(limit_num), int(sql_result['effect_row']))
        query_log.effect_row = limit_num
        query_log.cost_time = cost_time
        query_log.save()

    # 返回查询结果
    return HttpResponse(json.dumps(finalResult, cls=DateEncoder), content_type='application/json')


# 获取sql查询记录
@csrf_exempt
def querylog(request):
    # 获取用户信息
    loginUser = request.session.get('login_username', False)
    loginUserOb = users.objects.get(username=loginUser)

    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit

    # 获取搜索参数
    search = request.POST.get('search')
    if search is None:
        search = ''

    # 查询个人记录，超管查看所有数据
    if loginUserOb.is_superuser:
        sql_log_count = QueryLog.objects.all().filter(Q(sqllog__contains=search) | Q(username__contains=search)).count()
        sql_log_list = QueryLog.objects.all().filter(
            Q(sqllog__contains=search) | Q(username__contains=search)).order_by(
            '-id')[offset:limit]
    else:
        sql_log_count = QueryLog.objects.filter(username=loginUser).filter(
            Q(sqllog__contains=search) | Q(username__contains=search)).count()
        sql_log_list = QueryLog.objects.filter(username=loginUser).filter(
            Q(sqllog__contains=search) | Q(username__contains=search)).order_by('-id')[offset:limit]

    # QuerySet 序列化
    sql_log_list = serializers.serialize("json", sql_log_list)
    sql_log_list = json.loads(sql_log_list)
    sql_log = [log_info['fields'] for log_info in sql_log_list]

    result = {"total": sql_log_count, "rows": sql_log}
    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取审核列表
@csrf_exempt
def workflowlist(request):
    # 获取用户信息
    loginUser = request.session.get('login_username', False)
    loginUserOb = users.objects.get(username=loginUser)

    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    workflow_type = int(request.POST.get('workflow_type'))
    limit = offset + limit

    # 获取搜索参数
    search = request.POST.get('search')
    if search is None:
        search = ''

    # 调用工作流接口获取审核列表
    result = workflowOb.auditlist(loginUserOb, workflow_type, offset, limit, search)
    auditlist = result['data']['auditlist']
    auditlistCount = result['data']['auditlistCount']

    # QuerySet 序列化
    auditlist = serializers.serialize("json", auditlist)
    auditlist = json.loads(auditlist)
    list = []
    for i in range(len(auditlist)):
        auditlist[i]['fields']['id'] = auditlist[i]['pk']
        list.append(auditlist[i]['fields'])
    result = {"total": auditlistCount, "rows": list}

    result = {"total": auditlistCount, "rows": list}
    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 工单审核
@csrf_exempt
def workflowaudit(request):
    # 获取用户信息
    loginUser = request.session.get('login_username', False)
    result = {'status': 0, 'msg': 'ok', 'data': []}

    audit_id = int(request.POST['audit_id'])
    audit_status = int(request.POST['audit_status'])
    audit_remark = request.POST['audit_remark']

    # 获取审核信息
    auditInfo = workflowOb.auditinfo(audit_id)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口审核
            auditresult = workflowOb.auditworkflow(audit_id, audit_status, loginUser, audit_remark)

            # 按照审核结果更新业务表审核状态
            if auditresult['status'] == 0:
                if auditInfo.workflow_type == WorkflowDict.workflow_type['query']:
                    # 更新业务表审核状态,插入权限信息
                    query_audit_call_back(auditInfo.workflow_id, auditresult['data']['workflow_status'])

                    # 给拒绝和审核通过的申请人发送邮件
                    if hasattr(settings, 'MAIL_ON_OFF') is True and getattr(settings, 'MAIL_ON_OFF') == "on":
                        email_reciver = users.objects.get(username=auditInfo.create_user).email

                        email_content = "发起人：" + auditInfo.create_user + "\n审核人：" + auditInfo.audit_users \
                                        + "\n工单地址：" + request.scheme + "://" + request.get_host() + "/workflowdetail/" \
                                        + str(audit_id) + "\n工单名称： " + auditInfo.workflow_title \
                                        + "\n审核备注： " + audit_remark
                        if auditresult['data']['workflow_status'] == WorkflowDict.workflow_status['audit_success']:
                            email_title = "工单审核通过 # " + str(auditInfo.audit_id)
                            mailSenderOb.sendEmail(email_title, email_content, [email_reciver])
                        elif auditresult['data']['workflow_status'] == WorkflowDict.workflow_status['audit_reject']:
                            email_title = "工单被驳回 # " + str(auditInfo.audit_id)
                            mailSenderOb.sendEmail(email_title, email_content, [email_reciver])
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)
    else:
        result = auditresult
    return HttpResponse(json.dumps(result), content_type='application/json')
