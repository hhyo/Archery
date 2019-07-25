# -*- coding: UTF-8 -*-
import simplejson as json

from sql.engines import get_engine
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse

from common.utils.extend_json_encoder import ExtendJSONEncoder
from .models import Instance


@permission_required('sql.menu_data_dictionary', raise_exception=True)
def table_list(request):
    """数据字典获取表列表"""
    instance_name = request.GET.get('instance_name', '')
    db_name = request.GET.get('db_name', '')
    if instance_name and db_name:
        data = {}
        try:
            instance = Instance.objects.get(instance_name=instance_name, db_type='mysql')
            query_engine = get_engine(instance=instance)
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
    if instance_name and db_name and tb_name:
        data = {}
        try:
            instance = Instance.objects.get(instance_name=instance_name, db_type='mysql')
            query_engine = get_engine(instance=instance)

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
            res = {'status': 0, 'data': data}
        except Instance.DoesNotExist:
            res = {'status': 1, 'msg': 'Instance.DoesNotExist'}
        except Exception as e:
            res = {'status': 1, 'msg': str(e)}
    else:
        res = {'status': 1, 'msg': '非法调用！'}
    return HttpResponse(json.dumps(res, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
