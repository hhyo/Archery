# -*- coding: UTF-8 -*-
import re, time
import pymongo
import logging
import traceback
import json
import subprocess
import simplejson as json
import datetime
import tempfile
from bson.son import SON
from bson import json_util
from pymongo.errors import OperationFailure
from dateutil.parser import parse
from bson.objectid import ObjectId
from datetime import datetime

from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult

logger = logging.getLogger('default')

# mongo客户端安装在本机的位置
mongo = 'mongo'


# 自定义异常
class mongo_error(Exception):
    def __init__(self, error_info):
        super().__init__(self)
        self.error_info = error_info

    def __str__(self):
        return self.error_info


class JsonDecoder:
    '''处理传入mongodb语句中的条件，并转换成pymongo可识别的字典格式'''

    def __init__(self):
        pass

    def __json_object(self, tokener):
        # obj = collections.OrderedDict()
        obj = {}
        if tokener.cur_token() != '{':
            raise Exception('Json must start with "{"')

        while True:
            tokener.next()
            tk_temp = tokener.cur_token()
            if tk_temp == '}':
                return {}
            # 限制key的格式
            if not isinstance(tk_temp, str):  # or (not tk_temp.isidentifier() and not tk_temp.startswith("$"))
                raise Exception('invalid key %s' % tk_temp)
            key = tk_temp.strip()
            tokener.next()
            if tokener.cur_token() != ':':
                raise Exception('expect ":" after "%s"' % key)

            tokener.next()
            val = tokener.cur_token()
            if val == '[':
                val = self.__json_array(tokener)
            elif val == '{':
                val = self.__json_object(tokener)
            obj[key] = val

            tokener.next()
            tk_split = tokener.cur_token()
            if tk_split == ',':
                continue
            elif tk_split == '}':
                break
            else:
                if tk_split is None:
                    raise Exception('missing "}" at at the end of object')
                raise Exception('unexpected token "%s" at key "%s"' % (tk_split, key))
        return obj

    def __json_array(self, tokener):
        if tokener.cur_token() != '[':
            raise Exception('Json array must start with "["')

        arr = []
        while True:
            tokener.next()
            tk_temp = tokener.cur_token()
            if tk_temp == ']':
                return []
            if tk_temp == '{':
                val = self.__json_object(tokener)
            elif tk_temp == '[':
                val = self.__json_array(tokener)
            elif tk_temp in (',', ':', '}'):
                raise Exception('unexpected token "%s"' % tk_temp)
            else:
                val = tk_temp
            arr.append(val)

            tokener.next()
            tk_end = tokener.cur_token()
            if tk_end == ',':
                continue
            if tk_end == ']':
                break
            else:
                if tk_end is None:
                    raise Exception('missing "]" at the end of array')
        return arr

    def decode(self, json_str):
        tokener = JsonDecoder.__Tokener(json_str)
        if not tokener.next():
            return None
        first_token = tokener.cur_token()

        if first_token == '{':
            decode_val = self.__json_object(tokener)
        elif first_token == '[':
            decode_val = self.__json_array(tokener)
        else:
            raise Exception('Json must start with "{"')
        if tokener.next():
            raise Exception('unexpected token "%s"' % tokener.cur_token())
        return decode_val

    class __Tokener:  # Tokener 作为一个内部类
        def __init__(self, json_str):
            self.__str = json_str
            self.__i = 0
            self.__cur_token = None

        def __cur_char(self):
            if self.__i < len(self.__str):
                return self.__str[self.__i]
            return ''

        def __previous_char(self):
            if self.__i < len(self.__str):
                return self.__str[self.__i - 1]

        def __remain_str(self):
            if self.__i < len(self.__str):
                return self.__str[self.__i:]

        def __move_i(self, step=1):
            if self.__i < len(self.__str):
                self.__i += step

        def __next_string(self):
            '''当出现了"和'后就进入这个方法解析，直到出现与之对应的结束字符'''
            outstr = ''
            trans_flag = False
            start_ch = ""
            self.__move_i()
            while self.__cur_char() != '':
                ch = self.__cur_char()
                if start_ch == "": start_ch = self.__previous_char()
                if ch == '\\"':  # 判断是否是转义
                    trans_flag = True
                else:
                    if not trans_flag:
                        if (ch == '"' and start_ch == '"') or (ch == "'" and start_ch == "'"):
                            break
                    else:
                        trans_flag = False
                outstr += ch
                self.__move_i()
            return outstr

        def __next_number(self):
            expr = ''
            while self.__cur_char().isdigit() or self.__cur_char() in ('.', '+', '-'):
                expr += self.__cur_char()
                self.__move_i()
            self.__move_i(-1)
            if '.' in expr:
                return float(expr)
            else:
                return int(expr)

        def __next_const(self):
            '''处理没有被''和""包含的字符，如true和ObjectId'''
            outstr = ""
            data_type = ""
            while self.__cur_char().isalpha() or self.__cur_char() in ("$", "_", " "):
                outstr += self.__cur_char()
                self.__move_i()
                if outstr.replace(" ", "") in (
                        "ObjectId", "newDate", "ISODate", "newISODate"):  # ======类似的类型比较多还需单独处理，如int()等
                    data_type = outstr
                    for c in self.__remain_str():
                        outstr += c
                        self.__move_i()
                        if c == ")":
                            break

            self.__move_i(-1)

            if outstr in ('true', 'false', 'null'):
                return {'true': True, 'false': False, 'null': None}[outstr]
            elif data_type == "ObjectId":
                ojStr = re.findall(r"ObjectId\(.*?\)", outstr)  # 单独处理ObjectId
                if len(ojStr) > 0:
                    # return eval(ojStr[0])
                    id_str = re.findall(r"\(.*?\)", ojStr[0])
                    oid = id_str[0].replace(" ", "")[2:-2]
                    return ObjectId(oid)
            elif data_type.replace(" ", "") in ("newDate", "ISODate", "newISODate"):  # 处理时间格式
                tmp_type = "%s()" % data_type
                if outstr.replace(" ", "") == tmp_type.replace(" ", ""):
                    return datetime.datetime.now() + datetime.timedelta(hours=-8)  # mongodb默认时区为utc
                date_regex = re.compile(r'%s\("(.*)"\)' % data_type, re.IGNORECASE)
                date_content = date_regex.findall(outstr)
                if len(date_content) > 0:
                    return parse(date_content[0], yearfirst=True)
            elif outstr:
                return outstr
            raise Exception('Invalid symbol "%s"' % outstr)

        def next(self):
            is_white_space = lambda a_char: a_char in ('\x20', '\n', '\r', '\t')  # 定义一个匿名函数

            while is_white_space(self.__cur_char()):
                self.__move_i()

            ch = self.__cur_char()
            if ch == '':
                cur_token = None
            elif ch in ('{', '}', '[', ']', ',', ':'):
                cur_token = ch
            elif ch in ('"', "'"):  # 当字符为" '
                cur_token = self.__next_string()
            elif ch.isalpha() or ch in ("$", "_"):  # 字符串是否只由字母和"$","_"组成
                cur_token = self.__next_const()
            elif ch.isdigit() or ch in ('.', '-', '+'):  # 检测字符串是否只由数字组成
                cur_token = self.__next_number()
            else:
                raise Exception('Invalid symbol "%s"' % ch)
            self.__move_i()
            self.__cur_token = cur_token

            return cur_token is not None

        def cur_token(self):
            return self.__cur_token


class MongoEngine(EngineBase):
    error = None
    warning = None
    methodStr = None

    def exec_cmd(self, sql, db_name=None, slave_ok=''):
        """审核时执行的语句"""

        if self.user and self.password and self.port and self.host:
            msg = ""
            auth_db = self.instance.db_name or 'admin'
            sql_len = len(sql)
            is_load = False  # 默认不使用load方法执行mongodb sql语句
            try:
                if not sql.startswith('var host=') and sql_len > 4000:  # 在master节点执行的情况，如果sql长度大于4000,就采取load js的方法
                    # 因为用mongo load方法执行js脚本，所以需要重新改写一下sql，以便回显js执行结果
                    sql = 'var result = ' + sql + '\nprintjson(result);'
                    # 因为要知道具体的临时文件位置，所以用了NamedTemporaryFile模块
                    fp = tempfile.NamedTemporaryFile(suffix=".js", prefix="mongo_", dir='/tmp/', delete=True)
                    fp.write(sql.encode('utf-8'))
                    fp.seek(0)  # 把文件指针指向开始，这样写的sql内容才能落到磁盘文件上
                    cmd = "{mongo} --quiet -u {uname} -p '{password}' {host}:{port}/{auth_db} <<\\EOF\ndb=db.getSiblingDB(\"{db_name}\");{slave_ok}load('{tempfile_}')\nEOF".format(
                        mongo=mongo, uname=self.user, password=self.password, host=self.host, port=self.port,
                        db_name=db_name, sql=sql, auth_db=auth_db, slave_ok=slave_ok, tempfile_=fp.name)
                    is_load = True  # 标记使用了load方法，用来在finally里面判断是否需要强制删除临时文件
                elif not sql.startswith(
                        'var host=') and sql_len < 4000:  # 在master节点执行的情况， 如果sql长度小于4000,就直接用mongo shell执行，减少磁盘交换，节省性能
                    cmd = "{mongo} --quiet -u {uname} -p '{password}' {host}:{port}/{auth_db} <<\\EOF\ndb=db.getSiblingDB(\"{db_name}\");{slave_ok}printjson({sql})\nEOF".format(
                        mongo=mongo, uname=self.user, password=self.password, host=self.host, port=self.port,
                        db_name=db_name, sql=sql, auth_db=auth_db, slave_ok=slave_ok)
                else:
                    cmd = "{mongo} --quiet -u {user} -p '{password}' {host}:{port}/{auth_db} <<\\EOF\nrs.slaveOk();{sql}\nEOF".format(
                        mongo=mongo, user=self.user, password=self.password, host=self.host, port=self.port,
                        db_name=db_name, sql=sql, auth_db=auth_db)
                p = subprocess.Popen(cmd, shell=True,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     universal_newlines=True)
                re_msg = []
                for line in iter(p.stdout.read, ''):
                    re_msg.append(line)
                # 因为返回的line中也有可能带有换行符，因此需要先全部转换成字符串
                __msg = '\n'.join(re_msg)
                _re_msg = []
                for _line in __msg.split('\n'):
                    if not _re_msg and re.match('WARNING.*', _line):
                        # 第一行可能是WARNING语句，因此跳过
                        continue
                    _re_msg.append(_line)

                msg = '\n'.join(_re_msg)
            except Exception as e:
                logger.warning(f"mongo语句执行报错，语句：{sql}，{e}错误信息{traceback.format_exc()}")
            finally:
                if is_load:
                    fp.close()
        return msg

    def get_master(self):
        """获得主节点的port和host"""

        sql = "rs.isMaster().primary"
        master = self.exec_cmd(sql)
        if master != 'undefined' and master.find("TypeError") >= 0:
            sp_host = master.replace("\"", "").split(":")
            self.host = sp_host[0]
            self.port = int(sp_host[1])
        # return master

    def get_slave(self):
        """获得从节点的port和host"""

        sql = '''var host=""; rs.status().members.forEach(function(item) {i=1; if (item.stateStr =="SECONDARY") \
        {host=item.name } }); print(host);'''
        slave_msg = self.exec_cmd(sql)
        if slave_msg.lower().find('undefined') < 0:
            sp_host = slave_msg.replace("\"", "").split(":")
            self.host = sp_host[0]
            self.port = int(sp_host[1])
            return True
        else:
            return False

    def get_table_conut(self, table_name, db_name):
        try:
            count_sql = f"db.{table_name}.count()"
            status = self.get_slave()  # 查询总数据要求在slave节点执行
            if self.host and self.port and status:
                count = int(self.exec_cmd(count_sql, db_name, slave_ok='rs.slaveOk();'))
            else:
                count = int(self.exec_cmd(count_sql, db_name))
            return count
        except Exception as e:
            logger.debug("get_table_conut:" + str(e))
            return 0

    def execute_workflow(self, workflow):
        """执行上线单，返回Review set"""
        return self.execute(db_name=workflow.db_name, sql=workflow.sqlworkflowcontent.sql_content)

    def execute(self, db_name=None, sql=''):
        """mongo命令执行语句"""
        self.get_master()
        execute_result = ReviewSet(full_sql=sql)
        sql = sql.strip()
        # 以；切分语句，逐句执行
        sp_sql = sql.split(";")
        line = 0
        for exec_sql in sp_sql:
            if not exec_sql == '':
                exec_sql = exec_sql.strip()
                try:
                    # DeprecationWarning: time.clock has been deprecated in Python 3.3 and will be removed from Python 3.8: use time.perf_counter or time.process_time instead
                    start = time.perf_counter()
                    r = self.exec_cmd(exec_sql, db_name)
                    end = time.perf_counter()
                    line += 1
                    logger.debug("执行结果：" + r)
                    # 如果执行中有错误
                    rz = r.replace(' ', '').replace('"', '').lower()
                    tr = 1
                    if r.lower().find("syntaxerror") >= 0 or rz.find('ok:0') >= 0 or rz.find(
                            "error:invalid") >= 0 or rz.find("ReferenceError") >= 0 \
                            or rz.find("getErrorWithCode") >= 0 or rz.find("failedtoconnect") >= 0 or rz.find(
                        "Error: field") >= 0:
                        tr = 0
                    if (rz.find("errmsg") >= 0 or tr == 0) and (r.lower().find("already exist") < 0):
                        execute_result.error = r
                        result = ReviewResult(
                            id=line,
                            stage='Execute failed',
                            errlevel=2,
                            stagestatus='异常终止',
                            errormessage=f'mongo语句执行报错: {r}',
                            sql=exec_sql)
                    else:
                        # 把结果转换为ReviewSet
                        result = ReviewResult(
                            id=line, errlevel=0,
                            stagestatus='执行结束',
                            errormessage=r,
                            execute_time=round(end - start, 6),
                            actual_affected_rows=0,  # todo============这个值需要优化
                            sql=exec_sql)
                    execute_result.rows += [result]
                except Exception as e:
                    logger.warning(f"mongo语句执行报错，语句：{exec_sql}，错误信息{traceback.format_exc()}")
                    execute_result.error = str(e)
            # result_set.column_list = [i[0] for i in fields] if fields else []
        return execute_result

    def execute_check(self, db_name=None, sql=''):
        """上线单执行前的检查, 返回Review set"""
        line = 1
        count = 0
        check_result = ReviewSet(full_sql=sql)

        sql = sql.strip()
        if (sql.find(";") < 0):
            raise Exception("提交的语句请以分号结尾")
        # 以；切分语句，逐句执行
        sp_sql = sql.split(";")
        # 执行语句
        for check_sql in sp_sql:
            alert = ''  # 警告信息
            if not check_sql == '' and check_sql != '\n':
                check_sql = check_sql.strip()
                # check_sql = f'''{check_sql}'''
                # check_sql = check_sql.replace('\n', '') #处理成一行
                # 支持的命令列表
                supportMethodList = ["explain", "bulkWrite", "convertToCapped", "createIndex", "createIndexes",
                                     "deleteOne",
                                     "deleteMany", "drop", "dropIndex", "dropIndexes", "ensureIndex", "insert",
                                     "insertOne",
                                     "insertMany", "remove", "replaceOne", "renameCollection", "update", "updateOne",
                                     "updateMany", "createCollection", "renameCollection"]
                # 需要有表存在为前提的操作
                is_exist_premise_method = ["convertToCapped", "deleteOne", "deleteMany", "drop", "dropIndex",
                                           "dropIndexes",
                                           "remove", "replaceOne", "renameCollection", "update", "updateOne",
                                           "updateMany", "renameCollection"]
                pattern = re.compile(
                    r'''^db\.createCollection\(([\s\S]*)\)$|^db\.([\w\.-]+)\.(?:[A-Za-z]+)(?:\([\s\S]*\)$)|^db\.getCollection\((?:\s*)(?:'|")([\w-]*)('|")(\s*)\)\.([A-Za-z]+)(\([\s\S]*\)$)''')
                m = pattern.match(check_sql)
                if m is not None and (re.search(re.compile(r'}(?:\s*){'), check_sql) is None) and check_sql.count(
                        '{') == check_sql.count('}') and check_sql.count('(') == check_sql.count(')'):
                    sql_str = m.group()
                    table_name = (m.group(1) or m.group(2) or m.group(3)).strip()  # 通过正则的组拿到表名
                    table_name = table_name.replace('"', '').replace("'", "")
                    table_names = self.get_all_tables(db_name).rows
                    is_in = table_name in table_names  # 检查表是否存在
                    if not is_in:
                        alert = f"\n提示:{table_name}文档不存在!"
                    if sql_str:
                        count = 0
                        if sql_str.find('createCollection') > 0:  # 如果是db.createCollection()
                            methodStr = "createCollection"
                            alert = ""
                            if is_in:
                                check_result.error = "文档已经存在"
                                result = ReviewResult(id=line, errlevel=2,
                                                      stagestatus='文档已经存在',
                                                      errormessage='文档已经存在！',
                                                      affected_rows=count,
                                                      sql=check_sql)
                                check_result.rows += [result]
                                continue
                        else:
                            # method = sql_str.split('.')[2]
                            # methodStr = method.split('(')[0].strip()
                            methodStr = sql_str.split('(')[0].split('.')[-1].strip()  # 最后一个.和括号(之间的字符串作为方法
                        if methodStr in is_exist_premise_method and not is_in:
                            check_result.error = "文档不存在"
                            result = ReviewResult(id=line, errlevel=2,
                                                  stagestatus='文档不存在',
                                                  errormessage=f'文档不存在，不能进行{methodStr}操作！',
                                                  sql=check_sql)
                            check_result.rows += [result]
                            continue
                        if methodStr in supportMethodList:  # 检查方法是否支持
                            if methodStr == "createIndex" or methodStr == "createIndexes" or methodStr == "ensureIndex":  # 判断是否创建索引，如果大于500万，提醒不能在高峰期创建
                                p_back = re.compile(
                                    r'''(['"])(?:(?!\1)background)\1(?:\s*):(?:\s*)true|background\s*:\s*true|(['"])(?:(?!\1)background)\1(?:\s*):(?:\s*)(['"])(?:(?!\2)true)\2''',
                                    re.M)
                                m_back = re.search(p_back, check_sql)
                                if m_back is None:
                                    count = 5555555
                                    check_result.warning = '创建索引请加background:true'
                                    check_result.warning_count += 1
                                    result = ReviewResult(id=line, errlevel=2,
                                                          stagestatus='后台创建索引',
                                                          errormessage='创建索引没有加 background:true' + alert,
                                                          sql=check_sql)
                                elif not is_in:
                                    count = 0
                                else:
                                    count = self.get_table_conut(table_name, db_name)  # 获得表的总条数
                                    if count >= 5000000:
                                        check_result.warning = alert + '大于500万条，请在业务低谷期创建索引'
                                        check_result.warning_count += 1
                                        result = ReviewResult(id=line, errlevel=1,
                                                              stagestatus='大表创建索引',
                                                              errormessage='大于500万条，请在业务低谷期创建索引！',
                                                              affected_rows=count,
                                                              sql=check_sql)
                            if count < 5000000:
                                # 检测通过
                                affected_all_row_method = ["drop", "dropIndex", "dropIndexes", "createIndex",
                                                           "createIndexes", "ensureIndex"]
                                if methodStr not in affected_all_row_method:
                                    count = 0
                                else:
                                    count = self.get_table_conut(table_name, db_name)  # 获得表的总条数
                                result = ReviewResult(id=line, errlevel=0,
                                                      stagestatus='Audit completed',
                                                      errormessage='检测通过',
                                                      affected_rows=count,
                                                      sql=check_sql,
                                                      execute_time=0)
                        else:
                            result = ReviewResult(id=line, errlevel=2,
                                                  stagestatus='驳回不支持语句',
                                                  errormessage='仅支持DML和DDL语句，如需查询请使用数据库查询功能！',
                                                  sql=check_sql)

                else:
                    check_result.error = "语法错误"
                    result = ReviewResult(id=line, errlevel=2,
                                          stagestatus='语法错误',
                                          errormessage='请检查语句的正确性或（）{} },{是否正确匹配！',
                                          sql=check_sql)
                check_result.rows += [result]
                line += 1
                count = 0
        check_result.column_list = ['Result']  # 审核结果的列名
        check_result.checked = True
        check_result.warning = self.warning
        # 统计警告和错误数量
        for r in check_result.rows:
            if r.errlevel == 1:
                check_result.warning_count += 1
            if r.errlevel == 2:
                check_result.error_count += 1
        return check_result

    def get_connection(self, db_name=None):
        self.db_name = db_name or self.instance.db_name or 'admin'
        auth_db = self.instance.db_name or 'admin'
        self.conn = pymongo.MongoClient(self.host, self.port, authSource=auth_db, connect=True,
                                        connectTimeoutMS=10000)
        if self.user and self.password:
            self.conn[self.db_name].authenticate(self.user, self.password, auth_db)
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    @property
    def name(self):  # pragma: no cover
        return 'Mongo'

    @property
    def info(self):  # pragma: no cover
        return 'Mongo engine'

    def get_roles(self):
        sql_get_roles = "db.system.roles.find({},{_id:1})"
        result_set = self.query("admin", sql_get_roles)
        rows = ["read", "readWrite", "userAdminAnyDatabase"]
        for row in result_set.rows:
            rows.append(row[1])
        result_set.rows = rows
        return result_set

    def get_all_databases(self):
        result = ResultSet()
        conn = self.get_connection()
        try:
            result.rows = conn.list_database_names()
        except OperationFailure:
            result.rows = [self.db_name]
        return result

    def get_all_tables(self, db_name, **kwargs):
        result = ResultSet()
        conn = self.get_connection()
        db = conn[db_name]
        result.rows = db.list_collection_names()
        return result

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet"""
        # https://github.com/getredash/redash/blob/master/redash/query_runner/mongodb.py
        result = ResultSet()
        db = self.get_connection()[db_name]
        collection_name = tb_name
        documents_sample = []
        if "viewOn" in db[collection_name].options():
            for d in db[collection_name].find().limit(2):
                documents_sample.append(d)
        else:
            for d in db[collection_name].find().sort([("$natural", 1)]).limit(1):
                documents_sample.append(d)

            for d in db[collection_name].find().sort([("$natural", -1)]).limit(1):
                documents_sample.append(d)
        columns = []
        # _merge_property_names
        for document in documents_sample:
            for prop in document:
                if prop not in columns:
                    columns.append(prop)
        result.column_list = ['COLUMN_NAME']
        result.rows = columns
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        """return ResultSet 类似查询"""
        result = self.get_all_columns_by_tb(db_name=db_name, tb_name=tb_name)
        result.rows = [[[r], ] for r in result.rows]
        return result

    @staticmethod
    def dispose_str(parse_sql, start_flag, index):
        """解析处理字符串"""

        stop_flag = ""
        while index < len(parse_sql):
            if parse_sql[index] == stop_flag and parse_sql[index - 1] != "\\":
                return index
            index += 1
            stop_flag = start_flag
        raise Exception('near column %s,\' or \" has no close' % index)

    def dispose_pair(self, parse_sql, index, begin, end):
        """解析处理需要配对的字符{}[]() 检索一个左括号计数器加1，右括号计数器减1"""

        start_pos = -1
        stop_pos = 0
        count = 0
        while index < len(parse_sql):
            char = parse_sql[index]
            if char == begin:
                count += 1
                if start_pos == -1:
                    start_pos = index
            if char == end:
                count -= 1
                if count == 0:
                    stop_pos = index + 1
                    break
            if char in ("'", '"'):  # 避免字符串中带括号的情况，如{key:"{dd"}
                index = self.dispose_str(parse_sql, char, index)
            index += 1
        if count > 0:
            raise Exception("near column %s, The symbol %s has no closed" % (index, begin))

        re_char = parse_sql[start_pos:stop_pos]  # 截取
        return index, re_char

    def parse_query_sentence(self, parse_sql):
        """解析mongodb的查询语句，返回一个字典"""

        index = 0
        query_dict = {}

        # 开始解析查询语句
        while index < len(parse_sql):
            char = parse_sql[index]
            if char == "(":
                # 获得语句中的方法名
                head_sql = parse_sql[:index]
                method = parse_sql[:index].split(".")[-1].strip()
                index, re_char = self.dispose_pair(parse_sql, index, "(", ")")
                re_char = re_char.lstrip("(").rstrip(")")
                # 获得表名
                if method and "collection" not in query_dict:
                    collection = head_sql.replace("." + method, "").replace("db.", "")
                    query_dict["collection"] = collection
                # 分割查询条件和投影(返回字段)
                if method == "find":
                    p_index, condition = self.dispose_pair(re_char, 0, "{", "}")
                    query_dict["condition"] = condition
                    query_dict["method"] = method
                    # 获取查询返回字段
                    projection = re_char[p_index:].strip()[2:]
                    if projection:
                        query_dict["projection"] = projection
                # 聚合查询
                elif method == "aggregate":
                    pipeline = []
                    agg_index = 0
                    while agg_index < len(re_char):
                        p_index, condition = self.dispose_pair(re_char, agg_index, "{", "}")
                        agg_index = p_index + 1
                        if condition:
                            de = JsonDecoder()
                            step = de.decode(condition)
                            if "$sort" in step:
                                sort_list = []
                                for name, direction in step["$sort"].items():
                                    sort_list.append((name, direction))
                                step["$sort"] = SON(sort_list)
                            pipeline.append(step)
                        query_dict["condition"] = pipeline
                        query_dict["method"] = method
                elif method.lower() == "getcollection":  # 获得表名
                    collection = re_char.strip().replace("'", "").replace('"', '')
                    query_dict["collection"] = collection
                elif method.lower() == "getindexes":
                    query_dict["method"] = "index_information"
                else:
                    query_dict[method] = re_char
            index += 1

        logger.debug(query_dict)
        if query_dict:
            return query_dict

    def filter_sql(self, sql='', limit_num=0):
        """给查询语句改写语句, 返回修改后的语句"""
        sql = sql.split(";")[0].strip()
        # 执行计划
        if sql.startswith("explain"):
            sql = sql.replace("explain", "") + ".explain()"
        return sql.strip()

    def query_check(self, db_name=None, sql=''):
        """提交查询前的检查"""

        sql = sql.strip()
        if sql.startswith("explain"):
            sql = sql[7:] + ".explain()"
            sql = re.sub("[;\s]*.explain\(\)$", ".explain()", sql).strip()
        result = {'msg': '', 'bad_query': False, 'filtered_sql': sql, 'has_star': False}
        pattern = re.compile(
            r'''^db\.(\w+\.?)+(?:\([\s\S]*\)(\s*;*)$)|^db\.getCollection\((?:\s*)(?:'|")(\w+\.?)+('|")(\s*)\)\.([A-Za-z]+)(\([\s\S]*\)(\s*;*)$)''')
        m = pattern.match(sql)
        if m is not None:
            logger.debug(sql)
            query_dict = self.parse_query_sentence(sql)
            if "method" not in query_dict:
                result['msg'] += "错误：对不起，只支持查询相关方法"
                result['bad_query'] = True
                return result
            collection_name = query_dict["collection"]
            collection_names = self.get_all_tables(db_name).rows
            is_in = collection_name in collection_names  # 检查表是否存在
            if not is_in:
                result['msg'] += f"\n错误: {collection_name} 文档不存在!"
                result['bad_query'] = True
                return result
        else:
            result['msg'] += '请检查语句的正确性! 请使用原生查询语句'
            result['bad_query'] = True
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True, **kwargs):
        """执行查询"""

        result_set = ResultSet(full_sql=sql)
        find_cmd = ""

        # 提取命令中()中的内容
        query_dict = self.parse_query_sentence(sql)
        # 创建一个解析对象
        de = JsonDecoder()

        collection_name = query_dict["collection"]
        if "method" in query_dict and query_dict["method"]:
            method = query_dict["method"]
            find_cmd = "collection." + method
            if method == "index_information":
                find_cmd += "()"
        if "condition" in query_dict:
            if method == "aggregate":
                condition = query_dict["condition"]
            if method == "find":
                condition = de.decode(query_dict["condition"])
            find_cmd += "(condition)"
        if "projection" in query_dict and query_dict["projection"]:
            projection = de.decode(query_dict["projection"])
            find_cmd = find_cmd[:-1] + ",projection)"
        if "sort" in query_dict and query_dict["sort"]:
            sorting = []
            for k, v in de.decode(query_dict["sort"]).items():
                sorting.append((k, v))
            find_cmd += ".sort(sorting)"
        if method == "find" and "limit" not in query_dict and "explain" not in query_dict:
            find_cmd += ".limit(limit_num)"
        if "limit" in query_dict and query_dict["limit"]:
            query_limit = int(query_dict["limit"])
            limit = min(limit_num, query_limit) if query_limit else limit_num
            find_cmd += ".limit(limit)"
        if "count" in query_dict:
            find_cmd += ".count()"
        if "explain" in query_dict:
            find_cmd += ".explain()"

        try:
            conn = self.get_connection()
            db = conn[db_name]
            collection = db[collection_name]

            # 执行语句
            logger.debug(find_cmd)
            cursor = eval(find_cmd)

            columns = []
            rows = []
            if "count" in query_dict:
                columns.append("count")
                rows.append({"count": cursor})
            elif "explain" in query_dict:  # 生成执行计划数据
                columns.append("explain")
                cursor = json.loads(json_util.dumps(cursor))  # bson转换成json
                for k, v in cursor.items():
                    if k not in ("serverInfo", "ok"):
                        rows.append({k: v})
            elif method == "index_information":  # 生成返回索引数据
                columns.append("index_list")
                for k, v in cursor.items():
                    rows.append({k: v})
            elif method == "aggregate" and sql.find("$group") >= 0:  # 生成聚合数据
                row = []
                columns.insert(0, "mongodballdata")
                for ro in cursor:
                    json_col = json.dumps(ro, ensure_ascii=False, indent=2, separators=(",", ":"))
                    row.insert(0, json_col)
                    for k, v in ro.items():
                        if k not in columns:
                            columns.append(k)
                        row.append(v)
                    rows.append(tuple(row))
                    row.clear()
                rows = tuple(rows)
                result_set.rows = rows
            else:
                cursor = json.loads(json_util.dumps(cursor))
                cols = projection if 'projection' in dir() else None
                rows, columns = self.parse_tuple(cursor, db_name, collection_name, cols)
                result_set.rows = rows
            result_set.column_list = columns
            result_set.affected_rows = len(rows)
            if isinstance(rows, list):
                logger.debug(rows)
                result_set.rows = tuple(
                    [json.dumps(x, ensure_ascii=False, indent=2, separators=(",", ":"))] for x in rows)

        except Exception as e:
            logger.warning(f"Mongo命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}")
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    def parse_tuple(self, cursor, db_name, tb_name, projection=None):
        """前端bootstrap-table显示，需要转化mongo查询结果为tuple((),())的格式"""
        columns = []
        rows = []
        row = []
        if projection:
            for k in projection.keys():
                columns.append(k)
        else:
            result = self.get_all_columns_by_tb(db_name=db_name, tb_name=tb_name)
            columns = result.rows
        columns.insert(0, "mongodballdata")  # 隐藏JSON结果列
        columns = self.fill_query_columns(cursor, columns)

        for ro in cursor:
            json_col = json.dumps(ro, ensure_ascii=False, indent=2, separators=(",", ":"))
            row.insert(0, json_col)
            for key in columns[1:]:
                if key in ro:
                    value = ro[key]
                    if isinstance(value, list):
                        value = "(array) %d Elements" % len(value)
                    re_oid = re.compile(r"{\'\$oid\': \'[0-9a-f]{24}\'}")
                    re_date = re.compile(r"{\'\$date\': [0-9]{13}}")
                    # 转换$oid
                    ff = re.findall(re_oid, str(value))
                    for ii in ff:
                        value = str(value).replace(ii, "ObjectId(" + ii.split(":")[1].strip()[:-1] + ")")
                    # 转换时间戳$date
                    dd = re.findall(re_date, str(value))
                    for d in dd:
                        t = int(d.split(":")[1].strip()[:-1])
                        e = datetime.fromtimestamp(t / 1000)
                        value = str(value).replace(d, e.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
                    row.append(str(value))
                else:
                    row.append("(N/A)")
            rows.append(tuple(row))
            row.clear()
        return tuple(rows), columns

    @staticmethod
    def fill_query_columns(cursor, columns):
        """补充结果集中`get_all_columns_by_tb`未获取的字段"""
        cols = columns
        for ro in cursor:
            for key in ro.keys():
                if key not in cols:
                    cols.append(key)
        return cols

    def current_op(self, command_type):
        """
        获取当前连接信息
        
        command_type:
        Full    包含活跃与不活跃的连接，包含内部的连接，即全部的连接状态 
        All     包含活跃与不活跃的连接，不包含内部的连接
        Active  包含活跃
        Inner   内部连接
        """
        print(command_type)
        result_set = ResultSet(full_sql='db.aggregate([{"$currentOp": {"allUsers":true, "idleConnections":true}}])')
        try:
            conn = self.get_connection()
            processlists = []
            if not command_type:
                command_type = 'Active'
            if command_type in ['Full', 'All', 'Inner']:
                idle_connections = True
            else:
                idle_connections = False

            # conn.admin.current_op() 这个方法已经被pymongo废除，但mongodb3.6+才支持aggregate
            with conn.admin.aggregate(
                    [{'$currentOp': {'allUsers': True, 'idleConnections': idle_connections}}]) as cursor:
                for operation in cursor:
                    # 对sharding集群的特殊处理
                    if 'client' not in operation and \
                            operation.get('clientMetadata', {}).get('mongos', {}).get('client', {}):
                        operation['client'] = operation['clientMetadata']['mongos']['client']

                    # client_s 只是处理的mongos，并不是实际客户端
                    # client 在sharding获取不到？
                    if command_type in ['Full']:
                        processlists.append(operation)
                    elif command_type in ['All', 'Active']:
                        if 'clientMetadata' in operation:
                            processlists.append(operation)
                    elif command_type in ['Inner']:
                        if not 'clientMetadata' in operation:
                            processlists.append(operation)

            result_set.rows = processlists
        except Exception as e:
            logger.warning(f'mongodb获取连接信息错误，错误信息{traceback.format_exc()}')
            result_set.error = str(e)

        return result_set

    def get_kill_command(self, opids):
        """由传入的opid列表生成kill字符串"""
        conn = self.get_connection()
        active_opid = []
        with conn.admin.aggregate([{'$currentOp': {'allUsers': True, 'idleConnections': False}}]) as cursor:
            for operation in cursor:
                if 'opid' in operation and operation['opid'] in opids:
                    active_opid.append(operation['opid'])

        kill_command = ''
        for opid in active_opid:
            if isinstance(opid, int):
                kill_command = kill_command + 'db.killOp({});'.format(opid)
            else:
                kill_command = kill_command + 'db.killOp("{}");'.format(opid)

        return kill_command

    def kill_op(self, opids):
        """kill"""
        conn = self.get_connection()
        db = conn.admin
        for opid in opids:
            conn.admin.command({'killOp': 1, 'op': opid})
