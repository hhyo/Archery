#-*-coding: utf-8-*-

import re
import json
import MySQLdb
from django.conf import settings

from .models import master_config, workflow
from .aes_decryptor import Prpcrypt

class InceptionDao(object):
    def __init__(self):
        try:
            self.inception_host = getattr(settings, 'INCEPTION_HOST')
            self.inception_port = int(getattr(settings, 'INCEPTION_PORT'))
            
            self.inception_remote_backup_host = getattr(settings, 'INCEPTION_REMOTE_BACKUP_HOST')
            self.inception_remote_backup_port = int(getattr(settings, 'INCEPTION_REMOTE_BACKUP_PORT'))
            self.inception_remote_backup_user = getattr(settings, 'INCEPTION_REMOTE_BACKUP_USER')
            self.inception_remote_backup_password = getattr(settings, 'INCEPTION_REMOTE_BACKUP_PASSWORD')
            self.prpCryptor = Prpcrypt()
        except AttributeError as a:
            print("Error: %s" % a)
        except ValueError as v:
            print("Error: %s" % v)
        
    def criticalDDL(self, sqlContent):
        '''
        识别DROP DATABASE, DROP TABLE, TRUNCATE PARTITION, TRUNCATE TABLE等高危DDL操作，因为对于这些操作，inception在备份时只能备份METADATA，而不会备份数据！
        如果识别到包含高危操作，则返回“审核不通过”
        '''
        resultList = []
        criticalSqlFound = 0
        for row in sqlContent.rstrip(';').split(';'):
            if re.match(r"([\s\S]*)drop(\s+)database(\s+.*)|([\s\S]*)drop(\s+)table(\s+.*)|([\s\S]*)truncate(\s+.*)|([\s\S]*)truncate(\s+)partition(\s+.*)|([\s\S]*)truncate(\s+)table(\s+.*)", row.lower()):
                result = ('', '', 2, '驳回高危SQL', '不能包含【DROP DATABASE】|【DROP TABLE】|【TRUNCATE PARTITION】|【TRUNCATE TABLE】关键字！', row, '', '', '', '')
                criticalSqlFound = 1
            else:
                result = ('', '', 0, '', 'None', row, '', '', '', '')
            resultList.append(result)
        if criticalSqlFound == 1:
            return resultList
        else:
            return None

    def preCheck(self, sqlContent):
        '''
        在提交给inception之前，预先识别一些Inception不能正确审核的SQL,比如"alter table t1;"或"alter table test.t1;" 以免导致inception core dump
        '''
        resultList = []
        syntaxErrorSqlFound = 0
        for row in sqlContent.rstrip(';').split(';'):
            if re.match(r"(\s*)alter(\s+)table(\s+)(\S+)(\s*);|(\s*)alter(\s+)table(\s+)(\S+)\.(\S+)(\s*);", row.lower() + ";"):
                result = ('', '', 2, 'SQL语法错误', 'ALTER TABLE 必须带有选项', row, '', '', '', '')
                syntaxErrorSqlFound = 1
            else:
                result = ('', '', 0, '', 'None', row, '', '', '', '')
            resultList.append(result)
        if syntaxErrorSqlFound == 1:
            return resultList
        else:
            return None

    def sqlautoReview(self, sqlContent, clusterName, isSplit="no"):
        '''
        将sql交给inception进行自动审核，并返回审核结果。
        '''
        listMasters = master_config.objects.filter(cluster_name=clusterName)
        if len(listMasters) != 1:
            print("Error: 主库配置返回为0")
        masterHost = listMasters[0].master_host
        masterPort = listMasters[0].master_port
        masterUser = listMasters[0].master_user
        masterPassword = self.prpCryptor.decrypt(listMasters[0].master_password)

        #这里无需判断字符串是否以；结尾，直接抛给inception enable check即可。
        #if sqlContent[-1] != ";":
            #sqlContent = sqlContent + ";"

        if hasattr(settings, 'CRITICAL_DDL_ON_OFF') == True:
            if getattr(settings, 'CRITICAL_DDL_ON_OFF') == "on":
                criticalDDL_check = self.criticalDDL(sqlContent)
            else:
                criticalDDL_check = None

            if criticalDDL_check is not None:
                result = criticalDDL_check
            else:
                preCheckResult = self.preCheck(sqlContent)
                if preCheckResult is not None:
                    result = preCheckResult
                else:
                    if isSplit == "yes":
                        # 这种场景只给osc进度功能使用
                        # 如果一个工单中同时包含DML和DDL，那么执行时被split后的SQL与提交的SQL会不一样（会在每条语句前面加use database;)，导致osc进度更新取不到正确的SHA1值。
                        # 请参考inception文档中--enable-split参数的说明

                        sqlSplit = "/*--user=%s; --password=%s; --host=%s; --enable-execute;--port=%s; --enable-ignore-warnings;--enable-split;*/\
                             inception_magic_start;\
                             %s\
                             inception_magic_commit;" % (masterUser, masterPassword, masterHost, str(masterPort), sqlContent)
                        splitResult = self._fetchall(sqlSplit, self.inception_host, self.inception_port, '', '', '')
                        tmpList = []
                        for splitRow in splitResult:
                            sqlTmp = splitRow[1]
                            sql = "/*--user=%s;--password=%s;--host=%s;--enable-check;--port=%s; --enable-ignore-warnings;*/\
                                    inception_magic_start;\
                                    %s\
                                    inception_magic_commit;" % (masterUser, masterPassword, masterHost, str(masterPort), sqlTmp)
                            reviewResult = self._fetchall(sql, self.inception_host, self.inception_port, '', '', '')
                            tmpList.append(reviewResult)

                        #二次加工一下
                        finalList = []
                        for splitRow in tmpList:
                            for sqlRow in splitRow:
                                finalList.append(list(sqlRow))
                        result = finalList
                    else:
                        # 工单审核使用
                        sql="/*--user=%s;--password=%s;--host=%s;--enable-check=1;--port=%s;*/\
                          inception_magic_start;\
                          %s\
                          inception_magic_commit;" % (masterUser, masterPassword, masterHost, str(masterPort), sqlContent)
                        result = self._fetchall(sql, self.inception_host, self.inception_port, '', '', '')
        return result
        
    def executeFinal(self, workflowDetail, dictConn):
        '''
        将sql交给inception进行最终执行，并返回执行结果。
        '''
        strBackup = ""
        if workflowDetail.is_backup == '是':
            strBackup = "--enable-remote-backup;"
        else:
            strBackup = "--disable-remote-backup;"

        #根据inception的要求，执行之前最好先split一下
        sqlSplit = "/*--user=%s; --password=%s; --host=%s; --enable-execute;--port=%s; --enable-ignore-warnings;--enable-split;*/\
             inception_magic_start;\
             %s\
             inception_magic_commit;" % (dictConn['masterUser'], dictConn['masterPassword'], dictConn['masterHost'], str(dictConn['masterPort']), workflowDetail.sql_content)
        splitResult = self._fetchall(sqlSplit, self.inception_host, self.inception_port, '', '', '')

        tmpList = []
        #对于split好的结果，再次交给inception执行.这里无需保持在长连接里执行，短连接即可. 
        for splitRow in splitResult:
            sqlTmp = splitRow[1]
            sqlExecute = "/*--user=%s;--password=%s;--host=%s;--enable-execute;--port=%s; --enable-ignore-warnings;%s*/\
                    inception_magic_start;\
                    %s\
                    inception_magic_commit;" % (dictConn['masterUser'], dictConn['masterPassword'], dictConn['masterHost'], str(dictConn['masterPort']), strBackup, sqlTmp)
                    
            executeResult = self._fetchall(sqlExecute, self.inception_host, self.inception_port, '', '', '')
            for sqlRow in executeResult:
                tmpList.append(sqlRow)
            # 每执行一次，就将执行结果更新到工单的execute_result，便于获取osc进度时对比
            workflowDetail.execute_result = json.dumps(tmpList)
            workflowDetail.save()

        #二次加工一下，目的是为了和sqlautoReview()函数的return保持格式一致，便于在detail页面渲染.
        finalStatus = "已正常结束"
        finalList = []
        for sqlRow in tmpList:
            #如果发现任何一个行执行结果里有errLevel为1或2，并且stagestatus列没有包含Execute Successfully字样，则判断最终执行结果为有异常.
            if (sqlRow[2] == 1 or sqlRow[2] == 2) and re.match(r"\w*Execute Successfully\w*", sqlRow[3]) is None:
                finalStatus = "执行有异常"
            finalList.append(list(sqlRow))
        
        return (finalStatus, finalList)

    def getRollbackSqlList(self, workflowId):
        workflowDetail = workflow.objects.get(id=workflowId)
        listExecuteResult = json.loads(workflowDetail.execute_result)
        listBackupSql = []
        for row in listExecuteResult:
            #获取backup_dbname
            if row[8] == 'None':
                continue;
            backupDbName = row[8]
            sequence = row[7]
            opidTime = sequence.replace("'", "")
            sqlTable = "select tablename from %s.$_$Inception_backup_information$_$ where opid_time='%s';" % (backupDbName, opidTime)
            listTables = self._fetchall(sqlTable, self.inception_remote_backup_host, self.inception_remote_backup_port, self.inception_remote_backup_user, self.inception_remote_backup_password, '')
            if listTables is None or len(listTables) != 1:
                print("Error: returned listTables more than 1.")
            
            tableName = listTables[0][0]
            sqlBack = "select rollback_statement from %s.%s where opid_time='%s'" % (backupDbName, tableName, opidTime)
            listBackup = self._fetchall(sqlBack, self.inception_remote_backup_host, self.inception_remote_backup_port, self.inception_remote_backup_user, self.inception_remote_backup_password, '')
            if listBackup is not None and len(listBackup) !=0:
                for rownum in range(len(listBackup)):
                    listBackupSql.append(listBackup[rownum][0])
        return listBackupSql
            

    def _fetchall(self, sql, paramHost, paramPort, paramUser, paramPasswd, paramDb):
        '''
        封装mysql连接和获取结果集方法
        '''
        result = None
        conn = None
        cur = None

        try:
            conn=MySQLdb.connect(host=paramHost, user=paramUser, passwd=paramPasswd, db=paramDb, port=paramPort, charset='utf8mb4')
            cur=conn.cursor()
            ret=cur.execute(sql)
            result=cur.fetchall()
        except MySQLdb.Error as e:
            print("Mysql Error %d: %s" % (e.args[0], e.args[1]))
        finally:
            if cur is not None:
                cur.close()
            if conn is not None:
                conn.close()
        return result

    def getOscPercent(self, sqlSHA1):
        """已知SHA1值，去inception里查看OSC进度"""
        sqlStr = "inception get osc_percent '%s'" % sqlSHA1
        result = self._fetchall(sqlStr, self.inception_host, self.inception_port, '', '', '')
        if len(result) > 0:
            percent = result[0][3]
            timeRemained = result[0][4]
            pctResult = {"status":0, "msg":"ok", "data":{"percent":percent, "timeRemained":timeRemained}}
        else:
            pctResult = {"status":1, "msg":"没找到该SQL的进度信息，是否已经执行完毕？", "data":{"percent":-100, "timeRemained":-100}}
        return pctResult

    def stopOscProgress(self, sqlSHA1):
        """已知SHA1值，调用inception命令停止OSC进程，涉及的Inception命令和注意事项，请参考http://mysql-inception.github.io/inception-document/osc/"""
        sqlStr = "inception stop alter '%s'" % sqlSHA1
        result = self._fetchall(sqlStr, self.inception_host, self.inception_port, '', '', '')
        if result is not None:
            optResult = {"status":0, "msg":"已成功停止OSC进程，请注意清理触发器和临时表", "data":""}
        else:
            optResult = {"status":1, "msg":"ERROR 2624 (HY000):未找到OSC执行进程，可能已经执行完成", "data":""}
        return optResult
