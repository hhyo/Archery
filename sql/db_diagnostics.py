import simplejson as json

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

from sql.utils.aes_decryptor import Prpcrypt
from sql.utils.dao import Dao
from sql.utils.permission import role_required
from sql.utils.config import SysConfig
from .models import master_config

if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
    from .aliyun_rds import process_status as aliyun_process_status, \
        create_kill_session as aliyun_create_kill_session, kill_session as aliyun_kill_session, \
        sapce_status as aliyun_sapce_status

dao = Dao()
prpCryptor = Prpcrypt()


# 问题诊断--进程列表
@csrf_exempt
@role_required(('DBA',))
def process_status(request):
    cluster_name = request.POST.get('cluster_name')
    command_type = request.POST.get('command_type')

    base_sql = "select id, user, host, db, command, time, state, ifnull(info,'') as info from information_schema.processlist"
    # 判断是RDS还是其他实例
    if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
        result = aliyun_process_status(request)
    else:
        master_info = master_config.objects.get(cluster_name=cluster_name)
        if command_type == 'All':
            sql = base_sql + ";"
        elif command_type == 'Not Sleep':
            sql = "{} where command<>'Sleep';".format(base_sql)
        else:
            sql = "{} where command= '{}';".format(base_sql, command_type)
        processlist = dao.mysql_query(master_info.master_host, master_info.master_port, master_info.master_user,
                                      prpCryptor.decrypt(master_info.master_password), 'information_schema', sql)
        column_list = processlist['column_list']
        rows = []
        for row in processlist['rows']:
            row_info = {}
            for row_index, row_item in enumerate(row):
                row_info[column_list[row_index]] = row_item
            rows.append(row_info)
        result = {'status': 0, 'msg': 'ok', 'data': rows}

    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 问题诊断--通过进程id构建请求
@csrf_exempt
@role_required(('DBA',))
def create_kill_session(request):
    cluster_name = request.POST.get('cluster_name')
    ThreadIDs = request.POST.get('ThreadIDs')

    result = {'status': 0, 'msg': 'ok', 'data': []}
    # 判断是RDS还是其他实例
    if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
        result = aliyun_create_kill_session(request)
    else:
        master_info = master_config.objects.get(cluster_name=cluster_name)
        ThreadIDs = ThreadIDs.replace('[', '').replace(']', '')
        sql = "select concat('kill ', id, ';') from information_schema.processlist where id in ({});".format(ThreadIDs)
        all_kill_sql = dao.mysql_query(master_info.master_host, master_info.master_port, master_info.master_user,
                                       prpCryptor.decrypt(master_info.master_password), 'information_schema', sql)
        kill_sql = ''
        for row in all_kill_sql['rows']:
            kill_sql = kill_sql + row[0]
        result['data'] = kill_sql
    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 问题诊断--终止会话
@csrf_exempt
@role_required(('DBA',))
def kill_session(request):
    cluster_name = request.POST.get('cluster_name')
    request_params = request.POST.get('request_params')

    result = {'status': 0, 'msg': 'ok', 'data': []}
    # 判断是RDS还是其他实例
    if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
        result = aliyun_kill_session(request)
    else:
        master_info = master_config.objects.get(cluster_name=cluster_name)
        kill_sql = request_params
        dao.mysql_execute(master_info.master_host, master_info.master_port, master_info.master_user,
                          prpCryptor.decrypt(master_info.master_password), 'information_schema', kill_sql)

    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 问题诊断--Top表空间
@csrf_exempt
@role_required(('DBA',))
def sapce_status(request):
    cluster_name = request.POST.get('cluster_name')

    # 判断是RDS还是其他实例
    if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
        result = aliyun_sapce_status(request)
    else:
        master_info = master_config.objects.get(cluster_name=cluster_name)
        sql = '''
        SELECT
          table_schema,
          table_name,
          engine,
          TRUNCATE((data_length+index_length+data_free)/1024/1024,2) AS total_size,
          table_rows,
          TRUNCATE(data_length/1024/1024,2) AS data_size,
          TRUNCATE(index_length/1024/1024,2) AS index_size,
          TRUNCATE(data_free/1024/1024,2) AS data_free,
          TRUNCATE(data_free/(data_length+index_length+data_free)*100,2) AS pct_free
        FROM information_schema.tables WHERE TABLE_SCHEMA='{}'
          ORDER BY total_size DESC 
        LIMIT 14;'''.format(cluster_name)
        table_space = dao.mysql_query(master_info.master_host, master_info.master_port, master_info.master_user,
                                      prpCryptor.decrypt(master_info.master_password), 'information_schema', sql)
        column_list = table_space['column_list']
        rows = []
        for row in table_space['rows']:
            row_info = {}
            for row_index, row_item in enumerate(row):
                row_info[column_list[row_index]] = row_item
            rows.append(row_info)

        result = {'status': 0, 'msg': 'ok', 'data': rows}

    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')
