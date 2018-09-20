# -*-coding: utf-8-*-

import re
import simplejson as json
import MySQLdb
import traceback
from django.db import connection

from sql.models import Instance, SqlWorkflow
from common.utils.aes_decryptor import Prpcrypt
from common.config import SysConfig
from sql.utils.dao import Dao
import logging

logger = logging.getLogger('default')


class InceptionDao(object):
    def __init__(self):
        self.sys_config = SysConfig().sys_config
        self.inception_host = self.sys_config.get('inception_host')
        if self.sys_config.get('inception_port'):
            self.inception_port = int(self.sys_config.get('inception_port'))
        else:
            self.inception_port = 6669

        self.inception_remote_backup_host = self.sys_config.get('inception_remote_backup_host')
        if self.sys_config.get('inception_remote_backup_port'):
            self.inception_remote_backup_port = int(self.sys_config.get('inception_remote_backup_port'))
        else:
            self.inception_remote_backup_port = 3306
        self.inception_remote_backup_user = self.sys_config.get('inception_remote_backup_user')
        self.inception_remote_backup_password = self.sys_config.get('inception_remote_backup_password')
        self.prpCryptor = Prpcrypt()

    def criticalDDL(self, sql_content):
        '''
        识别DROP DATABASE, DROP TABLE, TRUNCATE PARTITION, TRUNCATE TABLE等高危DDL操作，因为对于这些操作，inception在备份时只能备份METADATA，而不会备份数据！
        如果识别到包含高危操作，则返回“审核不通过”
        '''
        resultList = []
        criticalSqlFound = 0
        critical_ddl_regex = self.sys_config.get('critical_ddl_regex')
        p = re.compile(critical_ddl_regex)
        # 删除注释语句
        sql_content = ''.join(
            map(lambda x: re.compile(r'(^--\s+.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
                sql_content.splitlines(1))).strip()

        for row in sql_content.rstrip(';').split(';'):
            if p.match(row.strip().lower()):
                result = (
                    '', '', 2, '驳回高危SQL', '禁止提交匹配' + critical_ddl_regex + '条件的语句！',
                    row,
                    '', '', '', '')
                criticalSqlFound = 1
            else:
                result = ('', '', 0, '', 'None', row, '', '', '', '')
            resultList.append(result)
        if criticalSqlFound == 1:
            return resultList
        else:
            return None

    def preCheck(self, sql_content):
        '''
        在提交给inception之前，预先识别一些Inception不能正确审核的SQL,比如"alter table t1;"或"alter table test.t1;" 以免导致inception core dump
        '''
        resultList = []
        syntaxErrorSqlFound = 0
        for row in sql_content.rstrip(';').split(';'):
            if re.match(r"(\s*)alter(\s+)table(\s+)(\S+)(\s*);|(\s*)alter(\s+)table(\s+)(\S+)\.(\S+)(\s*);",
                        row.lower() + ";"):
                result = ('', '', 2, 'SQL语法错误', 'ALTER TABLE 必须带有选项', row, '', '', '', '')
                syntaxErrorSqlFound = 1
            else:
                result = ('', '', 0, '', 'None', row, '', '', '', '')
            resultList.append(result)
        if syntaxErrorSqlFound == 1:
            return resultList
        else:
            return None

    def sqlautoReview(self, sql_content, instance_name, db_name, isSplit="no"):
        '''
        将sql交给inception进行自动审核，并返回审核结果。
        '''
        instance_info = Instance.objects.get(instance_name=instance_name)

        # 高危SQL检查
        if self.sys_config.get('critical_ddl_regex', '') != '':
            criticalDDL_check = self.criticalDDL(sql_content)
        else:
            criticalDDL_check = None

        if criticalDDL_check is not None:
            result = criticalDDL_check
        else:
            preCheckResult = self.preCheck(sql_content)
            if preCheckResult is not None:
                result = preCheckResult
            else:
                if isSplit == "yes":
                    # 这种场景只给osc进度功能使用
                    # 如果一个工单中同时包含DML和DDL，那么执行时被split后的SQL与提交的SQL会不一样（会在每条语句前面加use database;)，导致osc进度更新取不到正确的SHA1值。
                    # 请参考inception文档中--enable-split参数的说明

                    sqlSplit = "/*--user=%s; --password=%s; --host=%s; --enable-execute;--port=%s; --enable-ignore-warnings;--enable-split;*/\
                         inception_magic_start;\
                         use %s;\
                         %s\
                         inception_magic_commit;" % (
                        instance_info.user,
                        self.prpCryptor.decrypt(instance_info.password),
                        instance_info.host,
                        str(instance_info.port),
                        db_name,
                        sql_content)
                    splitResult = self._fetchall(sqlSplit, self.inception_host, self.inception_port, '', '', '')
                    tmpList = []
                    for splitRow in splitResult:
                        sqlTmp = splitRow[1]
                        sql = "/*--user=%s;--password=%s;--host=%s;--enable-check;--port=%s; --enable-ignore-warnings;*/\
                                inception_magic_start;\
                                %s\
                                inception_magic_commit;" % (
                            instance_info.user,
                            self.prpCryptor.decrypt(instance_info.password),
                            instance_info.host,
                            str(instance_info.port),
                            sqlTmp)
                        reviewResult = self._fetchall(sql, self.inception_host, self.inception_port, '', '', '')
                        tmpList.append(reviewResult)

                    # 二次加工一下
                    finalList = []
                    for splitRow in tmpList:
                        for sqlRow in splitRow:
                            finalList.append(list(sqlRow))
                    result = finalList
                else:
                    # 工单审核使用
                    sql = "/*--user=%s;--password=%s;--host=%s;--enable-check=1;--port=%s;*/\
                      inception_magic_start;\
                      use %s;\
                      %s\
                      inception_magic_commit;" % (
                        instance_info.user,
                        self.prpCryptor.decrypt(instance_info.password),
                        instance_info.host,
                        str(instance_info.port),
                        db_name,
                        sql_content)
                    result = self._fetchall(sql, self.inception_host, self.inception_port, '', '', '')
        return result

    def executeFinal(self, workflowDetail, instance_name):
        '''
        将sql交给inception进行最终执行，并返回执行结果。
        '''
        if workflowDetail.is_backup == '是':
            strBackup = "--enable-remote-backup;"
        else:
            strBackup = "--disable-remote-backup;"

        instance_info = Instance.objects.get(instance_name=instance_name)

        # 根据inception的要求，执行之前最好先split一下
        sqlSplit = "/*--user=%s; --password=%s; --host=%s; --enable-execute;--port=%s; --enable-ignore-warnings;--enable-split;*/\
             inception_magic_start;\
             use %s;\
             %s\
             inception_magic_commit;" % (
            instance_info.user,
            self.prpCryptor.decrypt(instance_info.password),
            instance_info.host,
            str(instance_info.port),
            workflowDetail.db_name, workflowDetail.sql_content)
        splitResult = self._fetchall(sqlSplit, self.inception_host, self.inception_port, '', '', '')

        tmpList = []
        # 对于split好的结果，再次交给inception执行.这里无需保持在长连接里执行，短连接即可.
        for splitRow in splitResult:
            sqlTmp = splitRow[1]
            sqlExecute = "/*--user=%s;--password=%s;--host=%s;--enable-execute;--port=%s; --enable-ignore-warnings;%s*/\
                    inception_magic_start;\
                    %s\
                    inception_magic_commit;" % (
                instance_info.user,
                self.prpCryptor.decrypt(instance_info.password),
                instance_info.host,
                str(instance_info.port),
                strBackup,
                sqlTmp)

            executeResult = self._fetchall(sqlExecute, self.inception_host, self.inception_port, '', '', '')
            for sqlRow in executeResult:
                tmpList.append(sqlRow)
            # 每执行一次，就将执行结果更新到工单的execute_result，便于获取osc进度时对比
            workflowDetail.execute_result = json.dumps(tmpList)
            try:
                workflowDetail.save()
            except Exception:
                # 关闭后重新获取连接，防止超时
                connection.close()
                workflowDetail.save()

        # 二次加工一下，目的是为了和sqlautoReview()函数的return保持格式一致，便于在detail页面渲染.
        finalStatus = "已正常结束"
        finalList = []
        for sqlRow in tmpList:
            # 如果发现任何一个行执行结果里有errLevel为1或2，并且stagestatus列没有包含Execute Successfully字样，则判断最终执行结果为有异常.
            if (sqlRow[2] == 1 or sqlRow[2] == 2) and re.match(r"\w*Execute Successfully\w*", sqlRow[3]) is None:
                finalStatus = "执行有异常"
            finalList.append(list(sqlRow))

        return (finalStatus, finalList)

    def getRollbackSqlList(self, workflowId):
        workflowDetail = SqlWorkflow.objects.get(id=workflowId)
        listExecuteResult = json.loads(workflowDetail.execute_result)
        # 回滚数据倒序展示
        listExecuteResult.reverse()
        listBackupSql = []
        for row in listExecuteResult:
            try:
                # 获取backup_dbname
                if row[8] == 'None':
                    continue
                backupDbName = row[8]
                sequence = row[7]
                sql = row[5]
                opidTime = sequence.replace("'", "")
                sqlTable = "select tablename from %s.$_$Inception_backup_information$_$ where opid_time='%s';" % (
                    backupDbName, opidTime)
                listTables = self._fetchall(sqlTable, self.inception_remote_backup_host,
                                            self.inception_remote_backup_port, self.inception_remote_backup_user,
                                            self.inception_remote_backup_password, '')
                if listTables:
                    tableName = listTables[0][0]
                    sqlBack = "select rollback_statement from %s.%s where opid_time='%s'" % (
                        backupDbName, tableName, opidTime)
                    listBackup = self._fetchall(sqlBack, self.inception_remote_backup_host,
                                                self.inception_remote_backup_port, self.inception_remote_backup_user,
                                                self.inception_remote_backup_password, '')
                    block_rollback_sql_list = [sql]
                    block_rollback_sql = '\n'.join([back_info[0] for back_info in listBackup])
                    block_rollback_sql_list.append(block_rollback_sql)
                    listBackupSql.append(block_rollback_sql_list)
            except Exception as e:
                raise Exception(e)
        return listBackupSql

    def _fetchall(self, sql, paramHost, paramPort, paramUser, paramPasswd, paramDb):
        '''
        封装mysql连接和获取结果集方法
        '''
        try:
            conn = MySQLdb.connect(host=paramHost, user=paramUser, passwd=paramPasswd, db=paramDb, port=paramPort,
                                   charset='utf8')
            cur = conn.cursor()
            ret = cur.execute(sql)
            result = cur.fetchall()
        except Exception as e:
            logger.error(traceback.format_exc())
            raise Exception(e)
        else:
            cur.close()
            conn.close()
        return result

    def getOscPercent(self, sqlSHA1):
        """已知SHA1值，去inception里查看OSC进度"""
        sqlStr = "inception get osc_percent '%s'" % sqlSHA1
        result = self._fetchall(sqlStr, self.inception_host, self.inception_port, '', '', '')
        if len(result) > 0:
            percent = result[0][3]
            timeRemained = result[0][4]
            pctResult = {"status": 0, "msg": "ok", "data": {"percent": percent, "timeRemained": timeRemained}}
        else:
            pctResult = {"status": 1, "msg": "没找到该SQL的进度信息，是否已经执行完毕？", "data": {"percent": -100, "timeRemained": -100}}
        return pctResult

    def stopOscProgress(self, sqlSHA1):
        """已知SHA1值，调用inception命令停止OSC进程，涉及的Inception命令和注意事项，请参考http://mysql-inception.github.io/inception-document/osc/"""
        sqlStr = "inception stop alter '%s'" % sqlSHA1
        result = self._fetchall(sqlStr, self.inception_host, self.inception_port, '', '', '')
        if result is not None:
            optResult = {"status": 0, "msg": "已成功停止OSC进程，请注意清理触发器和临时表，先清理触发器再删除临时表", "data": ""}
        else:
            optResult = {"status": 1, "msg": "ERROR 2624 (HY000):未找到OSC执行进程，可能已经执行完成", "data": ""}
        return optResult

    def query_print(self, sql_content, instance_name, dbName):
        '''
        将sql交给inception打印语法树。
        '''
        instance_info = Instance.objects.get(instance_name=instance_name)
        # 工单审核使用
        sql = "/*--user=%s;--password=%s;--host=%s;--port=%s;--enable-query-print;*/\
                          inception_magic_start;\
                          use %s;\
                          %s\
                          inception_magic_commit;" % (
            instance_info.user,
            self.prpCryptor.decrypt(instance_info.password),
            instance_info.host,
            str(instance_info.port),
            dbName,
            sql_content)
        result = self._fetchall(sql, self.inception_host, self.inception_port, '', '', '')
        return result

    # inception执行情况统计
    def statistic(self):
        sql = '''
             select
                 sum(deleting)     deleting,
                 sum(inserting)    inserting,
                 sum(updating)     updating,
                 sum(selecting)    selecting,
                 sum(altertable)   altertable,
                 sum(renaming)     renaming,
                 sum(createindex)  createindex,
                 sum(dropindex)    dropindex,
                 sum(addcolumn)    addcolumn,
                 sum(dropcolumn)   dropcolumn,
                 sum(changecolumn) changecolumn,
                 sum(alteroption)  alteroption,
                 sum(alterconvert) alterconvert,
                 sum(createtable)  createtable,
                 sum(droptable)    droptable,
                 sum(createdb)     createdb,
                 sum(truncating)   truncating
               from statistic;'''
        try:
            return Dao(host=self.inception_remote_backup_host,
                       user=self.inception_remote_backup_user,
                       port=self.inception_remote_backup_port,
                       password=self.inception_remote_backup_password).mysql_query('inception', sql)
        except Exception:
            return {'column_list': [], 'rows': [], 'effect_row': 0}
