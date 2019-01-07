import logging
import traceback
import json
import MySQLdb
import re
import sqlparse

from . import EngineBase
from .models import ResultSet, ReviewResult, ReviewSet
from .inception import InceptionEngine
from sql.utils.inception import InceptionDao
from common.config import SysConfig
logger = logging.getLogger('default')


class MysqlEngine(EngineBase):
    @property
    def Connection(self):
        return MySQLdb.connect(host=self.host,
                                    port=self.port, user=self.user, passwd=self.password, charset='utf8')
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
        sql = "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='%s' AND TABLE_NAME='%s';" % (
                db_name, tb_name)
        result = self.query(sql=sql)
        col_list = [row[0] for row in result.rows]
        return col_list

    def query(self, db_name=None, sql='', limit_num=0):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.Connection
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
            conn.close()
        return result_set

    def query_check(self, db_name=None, sql=''):
        # 连进指定的mysql实例里，执行sql并返回
        if '*' in sql:
            return {'bad_query':True}

    def execute_check(self, db_name=None, sql=''):
        """上线单执行前的检查, 返回Review set"""
        archer_config = SysConfig()
        check_result = ReviewSet(full_sql=sql)
        if archer_config.get('critical_ddl_regex'):
            # 如果启用critical_ddl 的检查
            critical_ddl_regex = archer_config.get('critical_ddl_regex')
            p = re.compile(critical_ddl_regex)
            # 删除注释语句
            sql = ''.join(
                map(lambda x: re.compile(r'(^--\s+.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
                    sql.splitlines(1))).strip()
            # 逐行匹配正则
            line = 1
            for statement in sqlparse.split(sql):
                if p.match(statement.strip().lower()):
                    result = ReviewResult (
                        id=line, errlevel=2, stagestatus = '驳回高危SQL', 
                        errormessage = '禁止提交匹配' + critical_ddl_regex + '条件的语句！',
                        sql=statement)
                    check_result.is_critical = True
                else:
                    result = ReviewResult(id=line,errlevel= 0, sql=statement)
                check_result.rows += [result]
                line += 1
            if check_result.is_critical:
                return check_result
        
        # 检查 inception 不支持的函数
        # 删除注释语句
        sql = ''.join(
            map(lambda x: re.compile(r'(^--\s+.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
                sql.splitlines(1))).strip()
        check_result.rows = []
        line = 1 
        for statement in sqlparse.split(sql):
            # 注释不检测
            if re.match(r"(\s*)alter(\s+)table(\s+)(\S+)(\s*);|(\s*)alter(\s+)table(\s+)(\S+)\.(\S+)(\s*);",
                        statement.lower() + ";"):
                result = ReviewSet (
                        id=line, errlevel=2, stagestatus = 'SQL语法错误', 
                        errormessage = 'ALTER TABLE 必须带有选项',
                        sql=statement)
                check_result.is_critical = True
            else:
                result = ReviewSet(id=line,errlevel= 0, sql=statement)
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

    def execute(self, manual=False):
        """执行上线单"""
        workflow_detail = self.workflow
        if workflow_detail.is_manual == 1:
            return self._execute(db_name=workflow_detail.db_name, sql=workflow_detail.sql_content)
        execute_result = ReviewSet(full_sql=workflow_detail.sql_content)
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
            workflow_detail.db_name, workflow_detail.sql_content)
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
                
            # 每执行一次，就将执行结果更新到工单的execute_result，便于获取osc进度时对比
            workflow_detail.execute_result = execute_result.json()
            workflow_detail.save()

        # 二次加工一下，目的是为了和sqlautoReview()函数的return保持格式一致，便于在detail页面渲染.
        execute_result.status = "已正常结束"
        for sqlRow in execute_result.rows:
            # 如果发现任何一个行执行结果里有errLevel为1或2，并且stagestatus列没有包含Execute Successfully字样，则判断最终执行结果为有异常.
            if (sqlRow.errlevel == 1 or sqlRow.errlevel == 2) and re.match(r"\w*Execute Successfully\w*", sqlRow.stagestatus) is None:
                execute_result.status = "执行有异常"
                execute_result.error = "Line {0} has error/warning: {1}".format(sqlRow.id, sqlRow.errormessage)

        return execute_result

    def get_rollback(self):
        """获取回滚语句列表"""
        ExecuteEngine = InceptionDao(instance_name=self.instance_name)
        return ExecuteEngine.get_rollback_sql_list(self.workflow.id)
    def _execute(self, db_name=None, sql=''):
        result = ResultSet(full_sql=sql)
        conn = self.Connection
        try:
            cursor = conn.cursor()
            for row in sql.strip(';').split(';'):
                cursor.execute(row)
            conn.commit()
            cursor.close()
        except Exception as e:
            logger.error(traceback.format_exc())
            result.error = str(e)
        conn.close()
        return result