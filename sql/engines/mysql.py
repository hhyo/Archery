import logging
import traceback
import json
import MySQLdb
import re
import sqlparse

from . import EngineBase
from .models import ResultSet, EngineResult
from sql.utils.inception import InceptionDao
from common.config import SysConfig
logger = logging.getLogger('default')
def get_inception_connection():
    """返回 inception的连接 是 MySQLdb.connect 对象"""
    archer_config = SysConfig()
    inception_host = archer_config.get('inception_host')
    inception_port = int(archer_config.get('inception_port', 6669))
    inception_user = archer_config.get('inception_user','')
    inception_password = archer_config.get('inception_password','')
    return MySQLdb.connect(host=inception_host, port=inception_port, user=inception_user,
                                passwd=inception_password, charset='utf8')
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
            return result_set
        except Exception as e:
            logger.error(traceback.format_exc())
            result_set.error = str(e)
        finally:
            cursor.close()
            conn.close()
        return result_set

    def query_check(self, db_name=None, sql=''):
        # 连进指定的mysql实例里，执行sql并返回
        if '*' in sql:
            return {'bad_query':True}

    def execute_check(self, db_name=None, sql=''):
        """上线单执行前的检查"""
        archer_config = SysConfig()
        check_result = ResultSet(full_sql=sql)
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
                    result = EngineResult (
                        id=line, errlevel=2, stagestatus = '驳回高危SQL', 
                        errormessage = '禁止提交匹配' + critical_ddl_regex + '条件的语句！',
                        sql=statement)
                    check_result.is_critical = True
                else:
                    result = EngineResult(id=line,errlevel= 0, sql=statement)
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
                result = EngineResult (
                        id=line, errlevel=2, stagestatus = 'SQL语法错误', 
                        errormessage = 'ALTER TABLE 必须带有选项',
                        sql=statement)
                check_result.is_critical = True
            else:
                result = EngineResult(id=line,errlevel= 0, sql=statement)
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
        inception_conn = get_inception_connection()
        try:
            cursor = inception_conn.cursor()
            cursor.execute(inception_sql)
            result = cursor.fetchall()
        except Exception as e:
            logger.error(traceback.format_exc())
            raise Exception(e)
        finally:
            cursor.close()
            inception_conn.close()
        for line in result:
            check_result.rows += [EngineResult(
                inception_result=line
            )]
        return check_result

    def execute(self, manual=False):
        """执行上线单"""
        workflow_detail = self.workflow
        if workflow_detail.is_manual == 0:
            # 执行之前重新split并check一遍，更新SHA1缓存；因为如果在执行中，其他进程去做这一步操作的话，会导致inception core dump挂掉
            try:
                check_engine = InceptionDao(instance_name=self.instance_name)
                split_review_result = check_engine.sqlauto_review(workflow_detail.sql_content,
                                                                                            workflow_detail.db_name,
                                                                                            is_split='yes')
            except Exception as msg:
                logger.error(traceback.format_exc())
                context = {'errMsg': msg}
                return context
            workflow_detail.review_content = json.dumps(split_review_result)
            workflow_detail.save()
            execute_engine = InceptionDao(instance_name=self.instance_name)
            inc_result = execute_engine.execute_final(self.workflow)
        else:
            return self._execute(db_name=workflow_detail.db_name, sql=workflow_detail.sql_content)

    def get_rollback(self):
        """获取回滚语句列表"""
        ExecuteEngine = InceptionDao(instance_name=self.instance_name)
        return ExecuteEngine.get_rollback_sql_list(self.workflow.id)
    def _execute(self, db_name=None, sql=''):
        result = ResultSet(full_sql=sql)
        try:
            conn = self.Connection
            cursor = conn.cursor()
            for row in sql.strip(';').split(';'):
                cursor.execute(row)
            conn.commit()
        except Exception as e:
            logger.error(traceback.format_exc())
            result.error = str(e)
        finally:
            cursor.close()
            conn.close()
        return result