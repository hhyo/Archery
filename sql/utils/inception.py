# -*-coding: utf-8-*-

import re
import simplejson as json
import MySQLdb
import traceback
import sqlparse
from django.db import connection

from sql.models import Instance, SqlWorkflow
from common.config import SysConfig
import logging

logger = logging.getLogger('default')


class InceptionDao(object):
    def __init__(self, instance_name=None):
        self.sys_config = SysConfig().sys_config
        self.inception_host = self.sys_config.get('inception_host')
        self.inception_port = int(self.sys_config.get('inception_port')) if self.sys_config.get(
            'inception_port') else 6669
        self.inception_remote_backup_host = self.sys_config.get('inception_remote_backup_host')
        self.inception_remote_backup_port = int(
            self.sys_config.get('inception_remote_backup_port')) if self.sys_config.get(
            'inception_remote_backup_port') else 3306
        self.inception_remote_backup_user = self.sys_config.get('inception_remote_backup_user')
        self.inception_remote_backup_password = self.sys_config.get('inception_remote_backup_password')
        if instance_name:
            try:
                instance_info = Instance.objects.get(instance_name=instance_name)
                self.host = instance_info.host
                self.port = int(instance_info.port)
                self.user = instance_info.user
                self.password = instance_info.raw_password
            except Exception:
                raise Exception('找不到对应的实例配置信息，请配置')

    def critical_ddl(self, sql_content):
        """
        识别DROP DATABASE, DROP TABLE, TRUNCATE PARTITION, TRUNCATE TABLE等高危DDL操作，因为对于这些操作，inception在备份时只能备份METADATA，而不会备份数据！
        如果识别到包含高危操作，则返回“审核不通过”
        """
        result_list = []
        critical_sql_found = 0
        critical_ddl_regex = self.sys_config.get('critical_ddl_regex')
        p = re.compile(critical_ddl_regex)
        # 删除注释语句
        sql_content = ''.join(
            map(lambda x: re.compile(r'(^--\s+.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
                sql_content.splitlines(1))).strip()

        for statement in sqlparse.split(sql_content):
            if p.match(statement.strip().lower()):
                result = (
                    '', '', 2, '驳回高危SQL', '禁止提交匹配' + critical_ddl_regex + '条件的语句！',
                    statement,
                    '', '', '', '')
                critical_sql_found = 1
            else:
                result = ('', '', 0, '', 'None', statement, '', '', '', '')
            result_list.append(result)
        if critical_sql_found == 1:
            return result_list
        else:
            return None

    def pre_check(self, sql_content):
        """
        在提交给inception之前，预先识别一些Inception不能正确审核的SQL,比如"alter table t1;"或"alter table test.t1;" 以免导致inception core dump
        """
        # 删除注释语句
        sql_content = ''.join(
            map(lambda x: re.compile(r'(^--\s+.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
                sql_content.splitlines(1))).strip()
        result_list = []
        syntax_error_sql_found = 0
        for statement in sqlparse.split(sql_content):
            # 注释不检测
            if re.match(r"(\s*)alter(\s+)table(\s+)(\S+)(\s*);|(\s*)alter(\s+)table(\s+)(\S+)\.(\S+)(\s*);",
                        statement.lower() + ";"):
                result = ('', '', 2, 'SQL语法错误', 'ALTER TABLE 必须带有选项', statement, '', '', '', '')
                syntax_error_sql_found = 1
            else:
                result = ('', '', 0, '', 'None', statement, '', '', '', '')
            result_list.append(result)
        if syntax_error_sql_found == 1:
            return result_list
        else:
            return None

    def sqlauto_review(self, sql_content, db_name, is_split="no"):
        """
        将sql交给inception进行自动审核，并返回审核结果。
        """
        # 高危SQL检查
        if self.sys_config.get('critical_ddl_regex', '') != '':
            critical_ddl_check = self.critical_ddl(sql_content)
        else:
            critical_ddl_check = None

        if critical_ddl_check is not None:
            result = critical_ddl_check
        else:
            pre_check_result = self.pre_check(sql_content)
            if pre_check_result is not None:
                result = pre_check_result
            else:
                if is_split == "yes":
                    # 这种场景只给osc进度功能使用
                    # 如果一个工单中同时包含DML和DDL，那么执行时被split后的SQL与提交的SQL会不一样（会在每条语句前面加use database;)，导致osc进度更新取不到正确的SHA1值。
                    # 请参考inception文档中--enable-split参数的说明

                    sql_split = "/*--user=%s; --password=%s; --host=%s; --enable-execute;--port=%d; --enable-ignore-warnings;--enable-split;*/\
                         inception_magic_start;\
                         use %s;\
                         %s\
                         inception_magic_commit;" % (
                        self.user,
                        self.password,
                        self.host,
                        self.port,
                        db_name,
                        sql_content)
                    split_result = self._fetchall(sql_split, self.inception_host, self.inception_port, '', '', '')
                    tmp_list = []
                    for splitRow in split_result:
                        sql_tmp = splitRow[1]
                        sql = "/*--user=%s;--password=%s;--host=%s;--enable-check;--port=%d; --enable-ignore-warnings;*/\
                                inception_magic_start;\
                                %s\
                                inception_magic_commit;" % (
                            self.user,
                            self.password,
                            self.host,
                            self.port,
                            sql_tmp)
                        review_result = self._fetchall(sql, self.inception_host, self.inception_port, '', '', '')
                        tmp_list.append(review_result)

                    # 二次加工一下
                    final_list = []
                    for splitRow in tmp_list:
                        for sqlRow in splitRow:
                            final_list.append(list(sqlRow))
                    result = final_list
                else:
                    # 工单审核使用
                    sql = "/*--user=%s;--password=%s;--host=%s;--enable-check=1;--port=%d;*/\
                      inception_magic_start;\
                      use %s;\
                      %s\
                      inception_magic_commit;" % (
                        self.user,
                        self.password,
                        self.host,
                        self.port,
                        db_name,
                        sql_content)
                    result = self._fetchall(sql, self.inception_host, self.inception_port, '', '', '')
        return result

    def execute_final(self, workflow_detail):
        """
        将sql交给inception进行最终执行，并返回执行结果。
        """
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
        split_result = self._fetchall(sql_split, self.inception_host, self.inception_port, '', '', '')

        tmp_list = []
        # 对于split好的结果，再次交给inception执行.这里无需保持在长连接里执行，短连接即可.
        for splitRow in split_result:
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

            execute_result = self._fetchall(sql_execute, self.inception_host, self.inception_port, '', '', '')
            for sqlRow in execute_result:
                tmp_list.append(sqlRow)
            # 每执行一次，就将执行结果更新到工单的execute_result，便于获取osc进度时对比
            workflow_detail.execute_result = json.dumps(tmp_list)
            try:
                workflow_detail.save()
            except Exception:
                # 关闭后重新获取连接，防止超时
                connection.close()
                workflow_detail.save()

        # 二次加工一下，目的是为了和sqlautoReview()函数的return保持格式一致，便于在detail页面渲染.
        final_status = "已正常结束"
        final_list = []
        for sqlRow in tmp_list:
            # 如果发现任何一个行执行结果里有errLevel为1或2，并且stagestatus列没有包含Execute Successfully字样，则判断最终执行结果为有异常.
            if (sqlRow[2] == 1 or sqlRow[2] == 2) and re.match(r"\w*Execute Successfully\w*", sqlRow[3]) is None:
                final_status = "执行有异常"
            final_list.append(list(sqlRow))

        return final_status, final_list

    def get_rollback_sql_list(self, workflow_id):
        workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
        list_execute_result = json.loads(workflow_detail.execute_result)
        # 回滚数据倒序展示
        list_execute_result.reverse()
        list_backup_sql = []
        # 创建连接
        conn = MySQLdb.connect(host=self.inception_remote_backup_host,
                               user=self.inception_remote_backup_user,
                               passwd=self.inception_remote_backup_password,
                               port=self.inception_remote_backup_port,
                               charset='utf8')
        cur = conn.cursor()
        for row in list_execute_result:
            try:
                # 获取backup_dbname
                if row[8] == 'None':
                    continue
                backup_db_name = row[8]
                sequence = row[7]
                sql = row[5]
                opid_time = sequence.replace("'", "")
                sql_table = "select tablename from %s.$_$Inception_backup_information$_$ where opid_time='%s';" % (
                    backup_db_name, opid_time)
                cur.execute(sql_table)
                list_tables = cur.fetchall()
                if list_tables:
                    table_name = list_tables[0][0]
                    sql_back = "select rollback_statement from %s.%s where opid_time='%s'" % (
                        backup_db_name, table_name, opid_time)
                    cur.execute(sql_back)
                    list_backup = cur.fetchall()
                    block_rollback_sql_list = [sql]
                    block_rollback_sql = '\n'.join([back_info[0] for back_info in list_backup])
                    block_rollback_sql_list.append(block_rollback_sql)
                    list_backup_sql.append(block_rollback_sql_list)
            except Exception as e:
                logger.error(traceback.format_exc())
                raise Exception(e)
        return list_backup_sql

    @staticmethod
    def _fetchall(sql, param_host, param_port, param_user, param_passwd, param_db):
        """
        封装mysql连接和获取结果集方法
        """
        try:
            conn = MySQLdb.connect(host=param_host, user=param_user, passwd=param_passwd, db=param_db, port=param_port,
                                   charset='utf8')
            cur = conn.cursor()
            cur.execute(sql)
            result = cur.fetchall()
        except Exception as e:
            logger.error(traceback.format_exc())
            raise Exception(e)
        else:
            cur.close()
            conn.close()
        return result

    def get_osc_percent(self, sql_sha1):
        """
        已知SHA1值，去inception里查看OSC进度
        """
        sql_str = "inception get osc_percent '%s'" % sql_sha1
        result = self._fetchall(sql_str, self.inception_host, self.inception_port, '', '', '')
        if len(result) > 0:
            percent = result[0][3]
            time_remained = result[0][4]
            pct_result = {"status": 0, "msg": "ok", "data": {"percent": percent, "time_remained": time_remained}}
        else:
            pct_result = {"status": 1, "msg": "没找到该SQL的进度信息，是否已经执行完毕？",
                          "data": {"percent": -100, "time_remained": -100}}
        return pct_result

    def stop_osc_progress(self, sql_sha1):
        """
        已知SHA1值，调用inception命令停止OSC进程，涉及的Inception命令和注意事项，请参考http://mysql-inception.github.io/inception-document/osc/
        """
        sql_str = "inception stop alter '%s'" % sql_sha1
        result = self._fetchall(sql_str, self.inception_host, self.inception_port, '', '', '')
        if result is not None:
            opt_result = {"status": 0, "msg": "已成功停止OSC进程，请注意清理触发器和临时表，先清理触发器再删除临时表", "data": ""}
        else:
            opt_result = {"status": 1, "msg": "ERROR 2624 (HY000):未找到OSC执行进程，可能已经执行完成", "data": ""}
        return opt_result

    def query_print(self, sql_content, db_name):
        """
        将sql交给inception打印语法树。
        """
        # 工单审核使用
        sql = "/*--user=%s;--password=%s;--host=%s;--port=%d;--enable-query-print;*/\
                          inception_magic_start;\
                          use %s;\
                          %s\
                          inception_magic_commit;" % (
            self.user,
            self.password,
            self.host,
            self.port,
            db_name,
            sql_content)
        result = self._fetchall(sql, self.inception_host, self.inception_port, '', '', '')
        return result
