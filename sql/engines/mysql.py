import logging
import traceback
import MySQLdb
import re
import sqlparse

from . import EngineBase
from .models import ResultSet, ReviewResult, ReviewSet
from .inception import InceptionEngine
from sql.utils.data_masking import Masking
from common.config import SysConfig

logger = logging.getLogger('default')


class MysqlEngine(EngineBase):
    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        self.conn = MySQLdb.connect(host=self.host,
                                    port=self.port, user=self.user, passwd=self.password, charset='utf8')
        return self.conn

    @property
    def name(self):
        return 'MySQL'

    @property
    def info(self):
        return 'MySQL engine'

    # 连进指定的mysql实例里，读取所有databases并返回
    def get_all_databases(self):
        sql = "show databases"
        result = self.query(sql=sql)
        db_list = [row[0] for row in result.rows
                   if row[0] not in ('information_schema', 'performance_schema', 'mysql', 'test', 'sys')]
        return db_list

    # 连进指定的mysql实例里，读取所有tables并返回
    def get_all_tables(self, db_name):
        sql = "show tables"
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in ['test']]
        return tb_list

    # 连进指定的mysql实例里，读取所有Columns并返回
    def get_all_columns_by_tb(self, db_name, tb_name):
        """return list [columns]"""
        result = self.describe_table(db_name, tb_name)
        column_list = [row[0] for row in result.rows]
        return column_list

    def describe_table(self, db_name, tb_name):
        """return ResultSet 类似查询"""
        sql = """SELECT 
    COLUMN_NAME,
    COLUMN_TYPE,
    CHARACTER_SET_NAME,
    IS_NULLABLE,
    COLUMN_KEY,
    EXTRA,
    COLUMN_COMMENT
FROM
    information_schema.COLUMNS
WHERE
    TABLE_SCHEMA = '{0}'
        AND TABLE_NAME = '{1}'
ORDER BY ORDINAL_POSITION;""".format(
            db_name, tb_name)
        result = self.query(sql=sql)
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            if db_name:
                cursor.execute('use {}'.format(db_name))
            effect_row = cursor.execute(sql)
            if int(limit_num) > 0:
                rows = cursor.fetchmany(size=int(limit_num))
            else:
                rows = cursor.fetchall()
            fields = cursor.description

            column_list = []
            if fields:
                for i in fields:
                    column_list.append(i[0])
            result_set.column_list = column_list
            result_set.rows = rows
            result_set.affected_rows = effect_row
        except Exception as e:
            logger.error(traceback.format_exc())
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    def query_check(self, db_name=None, sql='', limit_num=10):
        # 连进指定的mysql实例里，执行sql并返回
        check_result = {'has_star': False, 'msg': '', 'filtered_sql': sql}
        if '*' in sql:
            check_result['has_star'] = True
            check_result['msg'] = 'SQL语句中含有 * '
        # 对查询sql增加limit限制
        if re.match(r"^select", sql.lower()):
            if re.search(r"limit\s+(\d+)$", sql.lower()) is None:
                if re.search(r"limit\s+\d+\s*,\s*(\d+)$", sql.lower()) is None:
                    check_result['filtered_sql'] = sql + ' limit ' + str(limit_num)
        return check_result

    def query_masking(self, db_name=None, sql='', resultset=None):
        """传入 sql语句, db名, 结果集,
        返回一个脱敏后的结果集"""
        # 解析语法树
        mask_tool = Masking()
        resultset_dict = resultset.__dict__
        inception_mask_result = mask_tool.data_masking(self.instance_name, db_name, sql, resultset_dict)
        # 传参进去之后, 就已经被处理
        resultset.rows = resultset_dict['rows']
        hit_rule = inception_mask_result['data']['hit_rule']
        if hit_rule == 1:
            resultset.is_masked = True
        if inception_mask_result['status'] != 0:
            resultset.is_critical = True
            resultset.error = inception_mask_result['msg']
        resultset.status = inception_mask_result['status']
        return resultset

    def execute_check(self, db_name=None, sql=''):
        """上线单执行前的检查, 返回Review set"""
        archer_config = SysConfig()
        check_result = ReviewSet(full_sql=sql)
        if archer_config.get('critical_ddl_regex'):
            # 如果启用critical_ddl 的检查
            critical_ddl_regex = archer_config.get('critical_ddl_regex')
            p = re.compile(critical_ddl_regex)
            # 逐行匹配正则
            line = 1
            for statement in sqlparse.split(sql):
                # 删除注释语句
                statement = sqlparse.format(statement, strip_comments=True)
                if p.match(statement.strip().lower()):
                    result = ReviewResult(id=line, errlevel=2,
                                          stagestatus='驳回高危SQL',
                                          errormessage='禁止提交匹配' + critical_ddl_regex + '条件的语句！',
                                          sql=statement)
                    check_result.is_critical = True
                else:
                    result = ReviewResult(id=line, errlevel=0, sql=statement)
                check_result.rows += [result]
                line += 1
            if check_result.is_critical:
                return check_result

        # 检查 inception 不支持的函数
        check_result.rows = []
        line = 1
        for statement in sqlparse.split(sql):
            # 删除注释语句
            statement = sqlparse.format(statement, strip_comments=True)
            if re.match(r"(\s*)alter(\s+)table(\s+)(\S+)(\s*);|(\s*)alter(\s+)table(\s+)(\S+)\.(\S+)(\s*);",
                        statement.lower() + ";"):
                result = ReviewSet(
                    id=line, errlevel=2, stagestatus='SQL语法错误',
                    errormessage='ALTER TABLE 必须带有选项',
                    sql=statement)
                check_result.is_critical = True
            else:
                result = ReviewSet(id=line, errlevel=0, sql=statement)
            check_result.rows += [result]
            line += 1
        if check_result.is_critical:
            return check_result

        # inception 校验
        check_result.rows = []
        inception_sql = "/*--user=%s;--password=%s;--host=%s;--enable-check=1;--port=%d;*/\
            inception_magic_start;\
            use %s;\
            %s\
            inception_magic_commit;" % (
            self.user,
            self.password,
            self.host,
            self.port,
            db_name,
            sql)
        inception_engine = InceptionEngine()
        inception_result = inception_engine.query(sql=inception_sql)
        for r in inception_result.rows:
            check_result.rows += [ReviewResult(inception_result=r)]
        check_result.column_list = inception_result.column_list
        return check_result

    def execute_workflow(self):
        """执行上线单"""
        workflow_detail = self.workflow
        if workflow_detail.is_manual == 1:
            return self.execute(db_name=workflow_detail.db_name, sql=workflow_detail.sqlworkflowcontent.sql_content)
        execute_result = ReviewSet(full_sql=workflow_detail.sqlworkflowcontent.sql_content)
        inception_engine = InceptionEngine()
        if workflow_detail.is_backup == '是':
            str_backup = "--enable-remote-backup;"
        else:
            str_backup = "--disable-remote-backup;"
        # 根据inception的要求，执行之前最好先split一下
        sql_split = "/*--user=%s; --password=%s; --host=%s; --enable-execute;--port=%d; --enable-ignore-warnings;--enable-split;*/\
             inception_magic_start;\
             use %s;\
             %s\
             inception_magic_commit;" % (
            self.user,
            self.password,
            self.host,
            self.port,
            workflow_detail.db_name, workflow_detail.sqlworkflowcontent.sql_content)
        split_result = inception_engine.query(sql=sql_split)

        execute_result.rows = []
        # 对于split好的结果，再次交给inception执行.这里无需保持在长连接里执行，短连接即可.
        for splitRow in split_result.rows:
            sql_tmp = splitRow[1]
            sql_execute = "/*--user=%s;--password=%s;--host=%s;--enable-execute;--port=%d; --enable-ignore-warnings;%s*/\
                    inception_magic_start;\
                    %s\
                    inception_magic_commit;" % (
                self.user,
                self.password,
                self.host,
                self.port,
                str_backup,
                sql_tmp)

            one_line_execute_result = inception_engine.query(sql=sql_execute)
            # 执行, 把结果转换为ReviewSet
            for sqlRow in one_line_execute_result.to_dict():
                execute_result.rows.append(ReviewResult(
                    id=sqlRow['ID'],
                    stage=sqlRow['stage'],
                    errlevel=sqlRow['errlevel'],
                    stagestatus=sqlRow['stagestatus'],
                    errormessage=sqlRow['errormessage'],
                    sql=sqlRow['SQL'],
                    affected_rows=sqlRow['Affected_rows'],
                    actual_affected_rows=sqlRow['Affected_rows'],
                    sequence=sqlRow['sequence'],
                    backup_dbname=sqlRow['backup_dbname'],
                    execute_time=sqlRow['execute_time'],
                    sqlsha1=sqlRow['sqlsha1']))

            # 每执行一次，就将执行结果更新到工单的execute_result
            workflow_detail.sqlworkflowcontent.execute_result = execute_result.json()
            from django.db import connection
            if connection.connection is not None:
                connection.close()
            workflow_detail.sqlworkflowcontent.save()
            workflow_detail.save()

        # 二次加工一下，目的是为了和sqlautoReview()函数的return保持格式一致，便于在detail页面渲染.
        execute_result.status = "workflow_finish"
        for sqlRow in execute_result.rows:
            # 如果发现任何一个行执行结果里有errLevel为1或2，并且stagestatus列没有包含Execute Successfully字样，则判断最终执行结果为有异常.
            if (sqlRow.errlevel == 1 or sqlRow.errlevel == 2) and re.match(r"\w*Execute Successfully\w*",
                                                                           sqlRow.stagestatus) is None:
                execute_result.status = "workflow_exception"
                execute_result.error = "Line {0} has error/warning: {1}".format(sqlRow.id, sqlRow.errormessage)

        return execute_result

    def get_rollback(self):
        """获取回滚语句列表"""
        inception_engine = InceptionEngine()
        return inception_engine.get_rollback_list(self.workflow.id)

    def execute(self, db_name=None, sql='', close_conn=True):
        result = ResultSet(full_sql=sql)
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            for statement in sqlparse.split(sql):
                cursor.execute(statement)
            conn.commit()
            cursor.close()
        except Exception as e:
            logger.error(traceback.format_exc())
            result.error = str(e)
        if close_conn:
            self.close()
        return result

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
