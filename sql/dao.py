# -*- coding: UTF-8 -*- 

import MySQLdb

from django.db import connection

class Dao(object):
    _CHART_DAYS = 90

    #连进指定的mysql实例里，读取所有databases并返回
    def getAlldbByCluster(self, masterHost, masterPort, masterUser, masterPassword):
        listDb = []
        conn = None
        cursor = None
        
        try:
            conn=MySQLdb.connect(host=masterHost, port=masterPort, user=masterUser, passwd=masterPassword, charset='utf8mb4')
            cursor = conn.cursor()
            sql = "show databases"
            n = cursor.execute(sql)
            listDb = [row[0] for row in cursor.fetchall() 
                         if row[0] not in ('information_schema', 'performance_schema', 'mysql', 'test')]
        except MySQLdb.Warning as w:
            print(str(w))
        except MySQLdb.Error as e:
            print(str(e))
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.commit()
                conn.close()
        return listDb

    # 连进指定的mysql实例里，读取所有tables并返回
    def getAllTableByDb(self, masterHost, masterPort, masterUser, masterPassword, dbName):
        listTb = []
        conn = None
        cursor = None

        try:
            conn = MySQLdb.connect(host=masterHost, port=masterPort, user=masterUser, passwd=masterPassword,
                                   db=dbName,
                                   charset='utf8mb4')
            cursor = conn.cursor()
            sql = "show tables"
            n = cursor.execute(sql)
            listTb = [row[0] for row in cursor.fetchall()
                      if row[0] not in (
                          'test')]
        except MySQLdb.Warning as w:
            print(str(w))
        except MySQLdb.Error as e:
            print(str(e))
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.commit()
                conn.close()
        return listTb

    # 连进指定的mysql实例里，读取所有Columns并返回
    def getAllColumnsByTb(self, masterHost, masterPort, masterUser, masterPassword, dbName, tbName):
        listCol = []
        conn = None
        cursor = None

        try:
            conn = MySQLdb.connect(host=masterHost, port=masterPort, user=masterUser, passwd=masterPassword,
                                   db=dbName,
                                   charset='utf8mb4')
            cursor = conn.cursor()
            sql = "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='%s' AND TABLE_NAME='%s';" % (
                dbName, tbName)
            n = cursor.execute(sql)
            listCol = [row[0] for row in cursor.fetchall()]
        except MySQLdb.Warning as w:
            print(str(w))
        except MySQLdb.Error as e:
            print(str(e))
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.commit()
                conn.close()
        return listCol

    # 连进指定的mysql实例里，执行sql并返回
    def mysql_query(self, masterHost, masterPort, masterUser, masterPassword, dbName, sql, limit_num):
        result = {}
        conn = None
        cursor = None

        try:
            conn = MySQLdb.connect(host=masterHost, port=masterPort, user=masterUser, passwd=masterPassword, db=dbName,
                                   charset='utf8mb4')
            cursor = conn.cursor()
            effect_row = cursor.execute(sql)
            # rows = cursor.fetchall()
            rows = cursor.fetchmany(size=int(limit_num))
            fields = cursor.description

            column_list = []
            for i in fields:
                column_list.append(i[0])
            result = {}
            result['column_list'] = column_list
            result['rows'] = rows
            result['effect_row'] = effect_row

        except MySQLdb.Warning as w:
            print(str(w))
            result['Warning'] = str(w)
        except MySQLdb.Error as e:
            print(str(e))
            result['Error'] = str(e)
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.rollback()
                conn.close()
        return result

    # 连进指定的mysql实例里，执行sql并返回
    def mysql_execute(self, masterHost, masterPort, masterUser, masterPassword, sql):
        result = {}
        conn = None
        cursor = None

        try:
            conn = MySQLdb.connect(host=masterHost, port=masterPort, user=masterUser, passwd=masterPassword,
                                   charset='utf8mb4', max_allowed_packet=1073741824)
            cursor = conn.cursor()
            effect_row = cursor.execute(sql)
            # result = {}
            # result['effect_row'] = effect_row
            conn.commit()
        except MySQLdb.Warning as w:
            print(str(w))
            result['Warning'] = str(w)
        except MySQLdb.Error as e:
            print(str(e))
            result['Error'] = str(e)
        finally:
            if result.get('Error') or result.get('Warning'):
                conn.close()
            elif cursor is not None:
                cursor.close()
                conn.close()
        return result

    def getWorkChartsByMonth(self):
        cursor = connection.cursor()
        sql = "select date_format(create_time, '%%m-%%d'),count(*) from sql_workflow where create_time>=date_add(now(),interval -%s day) group by date_format(create_time, '%%m-%%d') order by 1 asc;" % (Dao._CHART_DAYS)
        cursor.execute(sql)
        result = cursor.fetchall()
        return result

    def getWorkChartsByPerson(self):
        cursor = connection.cursor()
        sql = "select engineer, count(*) as cnt from sql_workflow where create_time>=date_add(now(),interval -%s day) group by engineer order by cnt desc limit 50;" % (Dao._CHART_DAYS)
        cursor.execute(sql)
        result = cursor.fetchall()
        return result
