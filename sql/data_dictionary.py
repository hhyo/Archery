# -*- coding: UTF-8 -*-
import datetime
import os

import MySQLdb
import simplejson as json
from django.utils.http import urlquote
from jinja2 import Template

from archery import settings
from sql.engines import get_engine
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse, JsonResponse, FileResponse

from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.utils.resource_group import user_instances
from .models import Instance
import time
import pandas as pd

@permission_required('sql.menu_data_dictionary', raise_exception=True)
def table_list(request):
    """数据字典获取表列表"""
    instance_name = request.GET.get('instance_name', '')
    db_name = request.GET.get('db_name', '')
    db_type = request.GET.get('db_type', '')

    if instance_name and db_name:
        if db_type == 'mysql':
            try:
                data = {}
                instance = Instance.objects.get(instance_name=instance_name, db_type='mysql')
                query_engine = get_engine(instance=instance)
                # escape
                db_name = MySQLdb.escape_string(db_name).decode('utf-8')

                sql = f"""SELECT
                    TABLE_NAME,
                    TABLE_COMMENT
                FROM
                    information_schema.TABLES
                WHERE
                    TABLE_SCHEMA='{db_name}';"""
                result = query_engine.query(db_name=db_name, sql=sql)
                for row in result.rows:
                    table_name, table_cmt = row[0], row[1]
                    if table_name[0] not in data:
                        data[table_name[0]] = list()
                    data[table_name[0]].append([table_name, table_cmt])
                res = {'status': 0, 'data': data}
            except Instance.DoesNotExist:
                res = {'status': 1, 'msg': 'Instance.DoesNotExist'}
            except Exception as e:
                res = {'status': 1, 'msg': str(e)}
        elif db_type == 'oracle':
            try:
                data = {}
                instance = Instance.objects.get(instance_name=instance_name, db_type='oracle')
                query_engine = get_engine(instance=instance)
                table_list_sql = f"""SELECT     table_name,   comments     FROM    dba_tab_comments        WHERE     owner = '{db_name}'"""
                result = query_engine.query(db_name=db_name, sql=table_list_sql)
                for row in result.rows:
                    table_name, table_cmt = row[0], row[1]
                    if table_name[0] not in data:
                        data[table_name[0]] = list()
                    data[table_name[0]].append([table_name, table_cmt])
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
            if db_type == 'mysql':
                instance = Instance.objects.get(instance_name=instance_name, db_type='mysql')
                query_engine = get_engine(instance=instance)
                # escape
                db_name = MySQLdb.escape_string(db_name).decode('utf-8')
                tb_name = MySQLdb.escape_string(tb_name).decode('utf-8')

                sql = f"""SELECT
                    TABLE_NAME as table_name,
                ENGINE as engine,
                ROW_FORMAT as row_format,
                TABLE_ROWS as table_rows,
                AVG_ROW_LENGTH as avg_row_length,
                round(DATA_LENGTH/1024, 2) as data_length,
                MAX_DATA_LENGTH as max_data_length,
                round(INDEX_LENGTH/1024, 2) as index_length,
                round((DATA_LENGTH + INDEX_LENGTH)/1024, 2) as data_total,
                DATA_FREE as data_free,
                AUTO_INCREMENT as auto_increment,
                TABLE_COLLATION as table_collation,
                CREATE_TIME as create_time,
                CHECK_TIME as check_time,
                UPDATE_TIME as update_time,
                TABLE_COMMENT as table_comment
                FROM
                    information_schema.TABLES
                WHERE
                    TABLE_SCHEMA='{db_name}'
                        AND TABLE_NAME='{tb_name}'"""
                _meta_data = query_engine.query(db_name, sql)
                data['meta_data'] = {'column_list': _meta_data.column_list, 'rows': _meta_data.rows[0]}
                #data['meta_data'] = {'column_list': _meta_data.column_list, 'rows': _meta_data.rows}

                sql = f"""SELECT
                    COLUMN_NAME as '列名',
                    COLUMN_TYPE as '列类型',
                    CHARACTER_SET_NAME as '列字符集',
                    IS_NULLABLE as '是否为空',
                    COLUMN_KEY as '索引列',
                    COLUMN_DEFAULT as '默认值',
                    EXTRA as '拓展信息',
                    COLUMN_COMMENT as '列说明'
                FROM
                    information_schema.COLUMNS
                WHERE
                    TABLE_SCHEMA = '{db_name}'
                        AND TABLE_NAME = '{tb_name}'
                ORDER BY ORDINAL_POSITION;"""
                _desc_data = query_engine.query(db_name, sql)
                data['desc'] = {'column_list': _desc_data.column_list, 'rows': _desc_data.rows}

                sql = f"""SELECT
                    COLUMN_NAME as '列名',
                    INDEX_NAME as '索引名',
                    NON_UNIQUE as '唯一性',
                    SEQ_IN_INDEX as '列序列',
                    CARDINALITY as '基数',
                    NULLABLE as '是否为空',
                    INDEX_TYPE as '索引类型',
                    COMMENT as '备注'
                FROM
                    information_schema.STATISTICS
                WHERE
                    TABLE_SCHEMA = '{db_name}'
                AND TABLE_NAME = '{tb_name}';"""
                _index_data = query_engine.query(db_name, sql)
                data['index'] = {'column_list': _index_data.column_list, 'rows': _index_data.rows}

                _create_sql = query_engine.query(db_name, "show create table `%s`;" % tb_name)
                data['create_sql'] = _create_sql.rows
            elif db_type == 'oracle':

                instance = Instance.objects.get(instance_name=instance_name, db_type='oracle')
                query_engine = get_engine(instance=instance)
                meta_data_sql = f"""select      tcs.TABLE_NAME, --表名
                                                tcs.COMMENTS, --表注释
                                                tcs.TABLE_TYPE,  --表/试图 table/view
                                                ss.SEGMENT_TYPE,  --段类型 堆表/分区表/IOT表
                                                ts.TABLESPACE_NAME, --表空间
                                                ts.COMPRESSION, --压缩属性
                                                bss.NUM_ROWS, --表中的记录数
                                                bss.BLOCKS, --表中数据所占的数据块数
                                                bss.EMPTY_BLOCKS, --表中的空块数
                                                bss.AVG_SPACE, --数据块中平均的使用空间
                                                bss.CHAIN_CNT, --表中行连接和行迁移的数量
                                                bss.AVG_ROW_LEN, --每条记录的平均长度
                                                bss.LAST_ANALYZED  --上次统计信息搜集的时间
                                            from dba_tab_comments tcs
                                            left join dba_segments ss
                                                on ss.owner = tcs.OWNER
                                                and ss.segment_name = tcs.TABLE_NAME
                                            left join dba_tables ts
                                                on ts.OWNER = tcs.OWNER
                                                and ts.TABLE_NAME = tcs.TABLE_NAME
                                            left join DBA_TAB_STATISTICS bss
                                                on bss.OWNER = tcs.owner
                                                and bss.TABLE_NAME = tcs.table_name

                                            WHERE
                                                tcs.OWNER='{db_name}'
                                                AND tcs.TABLE_NAME='{tb_name}'"""
                _meta_data = query_engine.query(db_name=db_name, sql=meta_data_sql)
                data['meta_data'] = {'column_list': _meta_data.column_list, 'rows': _meta_data.rows[0]}

                desc_sql = f"""SELECT bcs.COLUMN_NAME "列名",
                                ccs.comments "列注释" ,
                                bcs.data_type || case
                                 when bcs.data_precision is not null and nvl(data_scale, 0) > 0 then
                                  '(' || bcs.data_precision || ',' || data_scale || ')'
                                 when bcs.data_precision is not null and nvl(data_scale, 0) = 0 then
                                  '(' || bcs.data_precision || ')'
                                 when bcs.data_precision is null and data_scale is not null then
                                  '(*,' || data_scale || ')'
                                 when bcs.char_length > 0 then
                                  '(' || bcs.char_length || case char_used
                                    when 'B' then
                                     ' Byte'
                                    when 'C' then
                                     ' Char'
                                    else
                                     null
                                  end || ')'
                                end "字段类型",
                                bcs.DATA_DEFAULT "字段默认值",
                                decode(nullable, 'N', ' NOT NULL') "是否为空",
                                ics.INDEX_NAME "所属索引",
                                acs.constraint_type "约束类型"
                            FROM  dba_tab_columns bcs
                            left  join dba_col_comments ccs
                                on  bcs.OWNER = ccs.owner
                                and  bcs.TABLE_NAME = ccs.table_name
                                and  bcs.COLUMN_NAME = ccs.column_name
                            left  join dba_ind_columns ics
                                on  bcs.OWNER = ics.TABLE_OWNER
                                and  bcs.TABLE_NAME = ics.table_name
                                and  bcs.COLUMN_NAME = ics.column_name
                            left join dba_constraints acs
                                on acs.owner = ics.TABLE_OWNER
                                and acs.table_name = ics.TABLE_NAME
                                and acs.index_name = ics.INDEX_NAME
                            WHERE
                                bcs.OWNER='{db_name}'
                                AND bcs.TABLE_NAME='{tb_name}'
                            ORDER BY bcs.COLUMN_NAME"""
                _desc_data = query_engine.query(db_name=db_name, sql=desc_sql)
                data['desc'] = {'column_list': _desc_data.column_list, 'rows': _desc_data.rows}

                index_sql = f""" SELECT
                                    ais.INDEX_NAME "索引名称",
                                    ais.uniqueness "唯一性",
                                    ais.index_type "索引类型",
                                    ais.compression "压缩属性",
                                    ais.tablespace_name "表空间",
                                    ais.status "状态",
                                    ais.partitioned "分区",
                                    pis.partitioning_type "分区状态",
                                    pis.locality "是否为LOCAL索引",
                                    pis.alignment "前导列索引"
                                FROM dba_indexes ais
                                left join DBA_PART_INDEXES pis
                                    on ais.owner = pis.owner
                                    and ais.index_name = pis.index_name
                                WHERE
                                    ais.owner = '{db_name}'
                                    AND ais.table_name = '{tb_name}'"""
                _index_data = query_engine.query(db_name, index_sql)
                data['index'] = {'column_list': _index_data.column_list, 'rows': _index_data.rows}

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
        instance = user_instances(request.user, db_type=['mysql','oracle']).get(instance_name=instance_name)
        inst_type = instance.db_type
        query_engine = get_engine(instance=instance)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '你所在组未关联该实例！', 'data': []})
    html = """<html>
    <meta charset="utf-8">
    <title>数据库表结构说明文档</title>
    <style>
        body,td,th {font-family:"宋体"; font-size:12px;}
        table,h1,p{width:960px;margin:0px auto;}
        table{border-collapse:collapse;border:1px solid #CCC;background:#efefef;}
        table caption{text-align:left; background-color:#fff; line-height:2em; font-size:14px; font-weight:bold; }
        table th{text-align:left; font-weight:bold;height:26px; line-height:26px; font-size:12px; border:1px solid #CCC;padding-left:5px;}
        table td{height:20px; font-size:12px; border:1px solid #CCC;background-color:#fff;padding-left:5px;}
        .c1{ width: 150px;}
        .c2{ width: 150px;}
        .c3{ width: 80px;}
        .c4{ width: 100px;}
        .c5{ width: 100px;}
        .c6{ width: 300px;}
    </style>
    <body>
    <h1 style="text-align:center;">{{ db_name }} 数据字典 (共 {{ tables|length }} 个表)</h1>
    <p style="text-align:center;margin:20px auto;">生成时间：{{ export_time }}</p>
    {% for tb in tables %}
    <table border="1" cellspacing="0" cellpadding="0" align="center">
    <caption>表名：{{ tb['TABLE_INFO']['TABLE_NAME'] }}</caption>
    <caption>注释：{{ tb['TABLE_INFO']['TABLE_COMMENTS'] }}</caption>
    <tbody><tr><th>字段名</th><th>数据类型</th><th>默认值</th><th>允许非空</th><th>自动递增</th><th>是否主键</th><th>备注</th>
    {% for col in tb['COLUMNS'] %}
    </tr>
    <td class="c1">{{ col['COLUMN_NAME'] }}</td>
    <td class="c2">{{ col['COLUMN_TYPE'] }}</td>
    <td class="c3">{{ col['COLUMN_DEFAULT'] or '' }}</td>
    <td class="c4">{{ col['IS_NULLABLE'] }}</td>
    <td class="c5">{% if col['EXTRA']=='auto_increment' %} 是 {% endif %}</td>
    <td class="c5">{{ col['COLUMN_KEY'] }}</td>
    <td class="c6">{{ col['COLUMN_COMMENT'] }}</td>
    </tr>
    {% endfor %}
    </tbody></table></br>
    {% endfor %}
    </body>
    </html>
    """


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
    if inst_type == 'mysql':
        for db in dbs:
            sql_tbs = f"SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='{db}';"
            tbs = query_engine.query(sql=sql_tbs, cursorclass=MySQLdb.cursors.DictCursor, close_conn=False).rows
            table_metas = []
            for tb in tbs:
                _meta = dict()
                _meta['TABLE_INFO'] = tb
                sql_cols = f"""SELECT * FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA='{tb['TABLE_SCHEMA']}' AND TABLE_NAME='{tb['TABLE_NAME']}';"""
                _meta['COLUMNS'] = query_engine.query(sql=sql_cols,
                                                    cursorclass=MySQLdb.cursors.DictCursor, close_conn=False).rows
                table_metas.append(_meta)
            data = Template(html).render(db_name=db, tables=table_metas, export_time=datetime.datetime.now())
            with open(f'{path}/{instance_name}_{db}.html', 'w') as f:
                f.write(data)
    elif  inst_type == 'oracle':
        #直接获取所有结果集，减少查询次数
        for db in dbs:
            table_metas = []
            sql_cols = f""" SELECT bcs.TABLE_NAME TABLE_NAME,
                                   tcs.COMMENTS TABLE_COMMENTS,
                                   bcs.COLUMN_NAME COLUMN_NAME,
                                   bcs.data_type || case
                                     when bcs.data_precision is not null and nvl(data_scale, 0) > 0 then
                                      '(' || bcs.data_precision || ',' || data_scale || ')'
                                     when bcs.data_precision is not null and nvl(data_scale, 0) = 0 then
                                      '(' || bcs.data_precision || ')'
                                     when bcs.data_precision is null and data_scale is not null then
                                      '(*,' || data_scale || ')'
                                     when bcs.char_length > 0 then
                                      '(' || bcs.char_length || case char_used
                                        when 'B' then
                                         ' Byte'
                                        when 'C' then
                                         ' Char'
                                        else
                                         null
                                      end || ')'
                                   end data_type,
                                   bcs.DATA_DEFAULT,
                                   decode(nullable, 'N', ' NOT NULL') nullable,
                                   t1.index_name,
                                   lcs.comments comments
                              FROM dba_tab_columns bcs
                              left join dba_col_comments lcs
                                on bcs.OWNER = lcs.owner
                               and bcs.TABLE_NAME = lcs.table_name
                               and bcs.COLUMN_NAME = lcs.column_name
                              left join dba_tab_comments tcs
                                on bcs.OWNER = tcs.OWNER
                               and bcs.TABLE_NAME = tcs.TABLE_NAME
                              left join (select acs.OWNER,
                                                acs.TABLE_NAME,
                                                scs.column_name,
                                                acs.index_name
                                           from dba_cons_columns scs
                                           join dba_constraints acs
                                             on acs.constraint_name = scs.constraint_name
                                            and acs.owner = scs.OWNER
                                          where acs.constraint_type = 'P') t1
                                on t1.OWNER = bcs.OWNER
                               AND t1.TABLE_NAME = bcs.TABLE_NAME
                               AND t1.column_name = bcs.COLUMN_NAME
                             WHERE bcs.OWNER = '{db_name}'
                             order by bcs.TABLE_NAME, comments
                            """
            cols_req = query_engine.query(sql=sql_cols,close_conn=False).rows

            #给查询结果定义列名，query_engine.query的游标是0 1 2
            cols_df = pd.DataFrame( cols_req , columns=['TABLE_NAME', 'TABLE_COMMENTS',  'COLUMN_NAME','COLUMN_TYPE','COLUMN_DEFAULT','IS_NULLABLE'  , 'COLUMN_KEY'  ,'COLUMN_COMMENT'])

            #获得表名称去重
            col_list = cols_df.drop_duplicates('TABLE_NAME').to_dict('records')
            for cl in col_list  :

                _meta = dict()
                _meta['TABLE_INFO'] = {  'TABLE_NAME' : cl['TABLE_NAME'] , 'TABLE_COMMENTS' : cl['TABLE_COMMENTS'] }

                #查询DataFrame中满足表名的记录，并转为list
                table_name=cl['TABLE_NAME']
                _meta['COLUMNS'] = cols_df.query("TABLE_NAME == @table_name").to_dict('records')

                table_metas.append(_meta )

            data = Template(html).render(db_name=db, tables=table_metas, export_time=datetime.datetime.now())

            with open(f'{path}/{instance_name}_{db}.html', 'w') as f:
                f.write(data)


    # 关闭连接
    query_engine.close()
    if db_name:
        response = FileResponse(open(f'{path}/{instance_name}_{db_name}.html', 'rb'))
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = f'attachment;filename="{urlquote(instance_name)}_{urlquote(db_name)}.html"'
        return response

    else:
        return JsonResponse({'status': 0, 'msg': f'实例{instance_name}数据字典导出成功，请到downloads目录下载！', 'data': []})
