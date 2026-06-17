# -*- coding: UTF-8 -*-
import re
import time
import pymongo
import logging
import traceback
import simplejson as json
import datetime
from bson.son import SON
from bson import json_util
from pymongo.errors import OperationFailure
from dateutil.parser import parse
from bson.objectid import ObjectId
from bson.int64 import Int64
from bson.regex import Regex

from sql.utils.data_masking import data_masking

from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult
from common.config import SysConfig

logger = logging.getLogger("default")


# 自定义异常
class mongo_error(Exception):
    def __init__(self, error_info):
        super().__init__(self)
        self.error_info = error_info

    def __str__(self):
        return self.error_info


class JsonDecoder:
    """处理传入mongodb语句中的条件，并转换成pymongo可识别的字典格式"""

    def __init__(self):
        pass

    def __json_object(self, tokener):
        # obj = collections.OrderedDict()
        obj = {}
        if tokener.cur_token() != "{":
            raise Exception('Json must start with "{"')

        while True:
            tokener.next()
            tk_temp = tokener.cur_token()
            if tk_temp == "}":
                return {}
            # 限制key的格式
            if not isinstance(
                tk_temp, str
            ):  # or (not tk_temp.isidentifier() and not tk_temp.startswith("$"))
                raise Exception("invalid key %s" % tk_temp)
            key = tk_temp.strip()
            tokener.next()
            if tokener.cur_token() != ":":
                raise Exception('expect ":" after "%s"' % key)

            tokener.next()
            val = tokener.cur_token()
            if val == "[":
                val = self.__json_array(tokener)
            elif val == "{":
                val = self.__json_object(tokener)
            obj[key] = val

            tokener.next()
            tk_split = tokener.cur_token()
            if tk_split == ",":
                continue
            elif tk_split == "}":
                break
            else:
                if tk_split is None:
                    raise Exception('missing "}" at at the end of object')
                raise Exception('unexpected token "%s" at key "%s"' % (tk_split, key))
        return obj

    def __json_array(self, tokener):
        if tokener.cur_token() != "[":
            raise Exception('Json array must start with "["')

        arr = []
        while True:
            tokener.next()
            tk_temp = tokener.cur_token()
            if tk_temp == "]":
                return []
            if tk_temp == "{":
                val = self.__json_object(tokener)
            elif tk_temp == "[":
                val = self.__json_array(tokener)
            elif tk_temp in (",", ":", "}"):
                raise Exception('unexpected token "%s"' % tk_temp)
            else:
                val = tk_temp
            arr.append(val)

            tokener.next()
            tk_end = tokener.cur_token()
            if tk_end == ",":
                continue
            if tk_end == "]":
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

        if first_token == "{":
            decode_val = self.__json_object(tokener)
        elif first_token == "[":
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
            return ""

        def __previous_char(self):
            if self.__i < len(self.__str):
                return self.__str[self.__i - 1]

        def __remain_str(self):
            if self.__i < len(self.__str):
                return self.__str[self.__i :]

        def __move_i(self, step=1):
            if self.__i < len(self.__str):
                self.__i += step

        def __next_string(self):
            """当出现了"和'后就进入这个方法解析，直到出现与之对应的结束字符"""
            outstr = ""
            trans_flag = False
            start_ch = ""
            self.__move_i()
            while self.__cur_char() != "":
                ch = self.__cur_char()
                if start_ch == "":
                    start_ch = self.__previous_char()
                if ch == '\\"':  # 判断是否是转义
                    trans_flag = True
                else:
                    if not trans_flag:
                        if (ch == '"' and start_ch == '"') or (
                            ch == "'" and start_ch == "'"
                        ):
                            break
                    else:
                        trans_flag = False
                outstr += ch
                self.__move_i()
            return outstr

        def __next_number(self):
            expr = ""
            while self.__cur_char().isdigit() or self.__cur_char() in (".", "+", "-"):
                expr += self.__cur_char()
                self.__move_i()
            self.__move_i(-1)
            if "." in expr:
                return float(expr)
            else:
                return int(expr)

        def __next_regex(self):
            """处理 MongoDB 原生正则字面量 /pattern/flags，返回 bson.regex.Regex"""
            self.__move_i()  # 跳过起始的 /
            pattern = ""
            trans_flag = False
            while self.__cur_char() != "":
                ch = self.__cur_char()
                if trans_flag:
                    # 保留反斜杠与转义字符，交给正则引擎自行解析
                    pattern += ch
                    trans_flag = False
                    self.__move_i()
                    continue
                if ch == "\\":
                    pattern += ch
                    trans_flag = True
                    self.__move_i()
                    continue
                if ch == "/":
                    break
                pattern += ch
                self.__move_i()
            if self.__cur_char() != "/":
                raise Exception('missing closing "/" in regex')

            # 读取 flags: i m s x (MongoDB 支持的正则选项)
            self.__move_i()  # 跳过闭合的 /
            flags_str = ""
            while self.__cur_char() in ("i", "m", "s", "x"):
                flags_str += self.__cur_char()
                self.__move_i()
            # 回退一步，让外层 next() 的 __move_i 推进到下一个字符
            self.__move_i(-1)

            return Regex(pattern, flags_str)

        def __next_const(self):
            """处理没有被''和""包含的字符，如true和ObjectId"""
            outstr = ""
            data_type = ""
            while self.__cur_char().isalpha() or self.__cur_char() in ("$", "_", " "):
                outstr += self.__cur_char()
                self.__move_i()
                if outstr.replace(" ", "") in (
                    "ObjectId",
                    "newDate",
                    "ISODate",
                    "newISODate",
                    "NumberLong",
                ):  # ======类似的类型比较多还需单独处理，如int()等
                    data_type = outstr
                    for c in self.__remain_str():
                        outstr += c
                        self.__move_i()
                        if c == ")":
                            break

            self.__move_i(-1)

            stripped = outstr.strip()
            if stripped in ("true", "false", "null"):
                return {"true": True, "false": False, "null": None}[stripped]
            elif data_type == "ObjectId":
                ojStr = re.findall(r"ObjectId\(.*?\)", outstr)  # 单独处理ObjectId
                if len(ojStr) > 0:
                    # return eval(ojStr[0])
                    id_str = re.findall(r"\(.*?\)", ojStr[0])
                    oid = id_str[0].replace(" ", "")[2:-2]
                    return ObjectId(oid)
            elif data_type.replace(" ", "") in (
                "newDate",
                "ISODate",
                "newISODate",
            ):  # 处理时间格式
                tmp_type = "%s()" % data_type
                if outstr.replace(" ", "") == tmp_type.replace(" ", ""):
                    return datetime.datetime.now() + datetime.timedelta(
                        hours=-8
                    )  # mongodb默认时区为utc
                date_regex = re.compile(r'%s\("(.*)"\)' % data_type, re.IGNORECASE)
                date_content = date_regex.findall(outstr)
                if len(date_content) > 0:
                    return parse(date_content[0], yearfirst=True)
            elif data_type.replace(" ", "") in ("NumberLong",):
                nuStr = re.findall(r"NumberLong\(.*?\)", outstr)  # 单独处理NumberLong
                if len(nuStr) > 0:
                    id_str = re.findall(r"\(.*?\)", nuStr[0])
                    nlong = id_str[0].replace(" ", "")[2:-2]
                    return Int64(nlong)
            elif stripped:
                return stripped
            raise Exception('Invalid symbol "%s"' % outstr)

        def next(self):
            is_white_space = lambda a_char: a_char in (
                "\x20",
                "\n",
                "\r",
                "\t",
            )  # 定义一个匿名函数

            while is_white_space(self.__cur_char()):
                self.__move_i()

            ch = self.__cur_char()
            if ch == "":
                cur_token = None
            elif ch in ("{", "}", "[", "]", ",", ":"):
                cur_token = ch
            elif ch in ('"', "'"):  # 当字符为" '
                cur_token = self.__next_string()
            elif ch.isalpha() or ch in ("$", "_"):  # 字符串是否只由字母和"$","_"组成
                cur_token = self.__next_const()
            elif ch.isdigit() or ch in (".", "-", "+"):  # 检测字符串是否只由数字组成
                cur_token = self.__next_number()
            elif ch == "/":  # MongoDB 原生正则字面量 /pattern/flags
                cur_token = self.__next_regex()
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

    def test_connection(self):
        return self.get_all_databases()

    def get_master(self):
        """获得主节点的port和host"""
        try:
            conn = self.get_connection()
            master = conn.admin.command("isMaster").get("primary")
            if master:
                master = master.strip().replace('"', "").replace("'", "")
                if master != "undefined" and ":" in master:
                    sp_host = master.split(":")
                    self.host = sp_host[0]
                    if len(sp_host) > 1:
                        self.port = int(sp_host[1])
        except Exception:
            logger.warning(
                f"mongodb获取主节点信息错误，错误信息{traceback.format_exc()}"
            )

    def get_slave(self):
        """获得从节点的port和host"""
        try:
            conn = self.get_connection()
            rs_status = conn.admin.command("replSetGetStatus")
            slave_msg = ""
            for member in rs_status.get("members", []):
                if member.get("stateStr") == "SECONDARY":
                    slave_msg = member.get("name", "")
                    break
            # 如果是阿里云的云mongodb，会获取不到备节点真实的ip和端口，那就干脆不获取，直接用主节点来执行sql
            # 如果是自建mongodb，获取到备节点的ip是192.168.1.33:27019这样的值；但如果是阿里云mongodb，获取到的备节点ip是SECONDARY、hiddenNode这样的值
            # 所以，为了使代码更加通用，通过有无冒号来判断自建Mongod还是阿里云mongdb；没有冒号就判定为阿里云mongodb，直接返回false；
            if ":" not in slave_msg:
                return False
            if slave_msg.lower().find("undefined") < 0:
                sp_host = slave_msg.replace('"', "").split(":")
                self.host = sp_host[0]
                self.port = int(sp_host[1])
                return True
            else:
                return False
        except Exception:
            logger.warning(
                f"mongodb获取从节点信息错误，错误信息{traceback.format_exc()}"
            )
            return False

    def get_table_conut(self, table_name, db_name):
        try:
            self.get_slave()  # 查询总数据要求在slave节点执行，会更新 self.host/port
            conn = self.get_connection(db_name)
            db = conn[db_name]
            count = db[table_name].count_documents({})
            return count
        except Exception as e:
            logger.debug("get_table_conut:" + str(e))
            return 0

    def __split_args(self, args_str):
        """安全地按逗号分割参数，忽略 {}[]() 和字符串内部的逗号"""
        args = []
        current = []
        depth = 0
        in_string = False
        string_char = None

        for i, ch in enumerate(args_str):
            if ch in ('"', "'") and (i == 0 or args_str[i - 1] != "\\"):
                if not in_string:
                    in_string = True
                    string_char = ch
                elif ch == string_char:
                    in_string = False
                    string_char = None
                current.append(ch)
            elif in_string:
                current.append(ch)
            elif ch in ("{", "[", "("):
                depth += 1
                current.append(ch)
            elif ch in ("}", "]", ")"):
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
            else:
                current.append(ch)

        if current:
            args.append("".join(current).strip())

        return args

    def _execute_shell_sql(self, sql, db_name):
        """
        解析 MongoDB shell 语句并通过 pymongo 执行
        返回 (success: bool, result_json: str, affected_rows: int)
        """
        sql = sql.strip().rstrip(";")

        # 找到最后一个 ".method(" 的位置
        last_dot_pos = -1
        in_string = False
        string_char = None
        paren_depth = 0

        for i, ch in enumerate(sql):
            if ch in ('"', "'") and (i == 0 or sql[i - 1] != "\\"):
                if not in_string:
                    in_string = True
                    string_char = ch
                elif ch == string_char:
                    in_string = False
                    string_char = None
            elif not in_string:
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth -= 1
                elif ch == "." and paren_depth == 0:
                    last_dot_pos = i

        if last_dot_pos < 0:
            return False, f"无法解析语句: {sql}", 0

        method_part = sql[last_dot_pos + 1 :]
        paren_pos = method_part.find("(")
        if paren_pos < 0:
            return False, f"无法解析方法参数: {sql}", 0

        method = method_part[:paren_pos].strip()

        # 提取参数
        _, args_with_parens = self.dispose_pair(
            sql, last_dot_pos + 1 + paren_pos, "(", ")"
        )
        args_str = args_with_parens.strip("()")
        args = self.__split_args(args_str)

        # 解析参数为 Python 对象
        de = JsonDecoder()
        parsed_args = []
        for arg in args:
            arg = arg.strip()
            if not arg:
                continue
            if arg.startswith("{") or arg.startswith("["):
                parsed_args.append(de.decode(arg))
            elif arg.startswith('"') or arg.startswith("'"):
                parsed_args.append(arg[1:-1])
            elif arg.isdigit():
                parsed_args.append(int(arg))
            elif arg == "true":
                parsed_args.append(True)
            elif arg == "false":
                parsed_args.append(False)
            else:
                parsed_args.append(arg)

        # 提取 collection
        head = sql[:last_dot_pos].strip()

        conn = self.get_connection(db_name)
        db = conn[db_name]

        if method == "createCollection":
            coll = None
            coll_name = parsed_args[0] if parsed_args else None
        else:
            if "getCollection" in head:
                gc_start = head.find("getCollection")
                _, gc_args = self.dispose_pair(
                    head, gc_start + len("getCollection"), "(", ")"
                )
                collection = gc_args.strip("()").strip().strip('"').strip("'")
            else:
                collection = head.replace("db.", "").strip()
            coll = db[collection]

        affected_rows = 0

        def _to_bool(v):
            """将整数 1/0、字符串 '1'/'0'/'true'/'false' 归一化为布尔值"""
            if isinstance(v, bool):
                return v
            if isinstance(v, (int, float)):
                return bool(v)
            if isinstance(v, str):
                s = v.strip().lower()
                if s in ("true", "1"):
                    return True
                if s in ("false", "0"):
                    return False
            return v

        def _normalize_bool_opts(opts, keys=("upsert", "multi", "justOne")):
            """对 opts 中已知布尔选项做类型归一化，避免 pymongo 校验报错"""
            if isinstance(opts, dict):
                for k in keys:
                    if k in opts:
                        opts[k] = _to_bool(opts[k])
            return opts

        try:
            if method == "insertOne":
                result = coll.insert_one(parsed_args[0])
                affected_rows = 1
                result_doc = {
                    "acknowledged": result.acknowledged,
                    "insertedId": str(result.inserted_id),
                }
            elif method == "insertMany":
                result = coll.insert_many(parsed_args[0])
                affected_rows = len(result.inserted_ids)
                result_doc = {
                    "acknowledged": result.acknowledged,
                    "insertedIds": [str(i) for i in result.inserted_ids],
                }
            elif method == "insert":
                if isinstance(parsed_args[0], list):
                    result = coll.insert_many(parsed_args[0])
                    affected_rows = len(result.inserted_ids)
                    result_doc = {
                        "acknowledged": result.acknowledged,
                        "insertedIds": [str(i) for i in result.inserted_ids],
                    }
                else:
                    result = coll.insert_one(parsed_args[0])
                    affected_rows = 1
                    result_doc = {
                        "acknowledged": result.acknowledged,
                        "insertedId": str(result.inserted_id),
                    }
            elif method == "updateOne":
                opts = _normalize_bool_opts(
                    parsed_args[2] if len(parsed_args) > 2 else {}
                )
                result = coll.update_one(parsed_args[0], parsed_args[1], **(opts or {}))
                affected_rows = result.modified_count
                result_doc = {
                    "acknowledged": result.acknowledged,
                    "matchedCount": result.matched_count,
                    "modifiedCount": result.modified_count,
                }
            elif method == "updateMany":
                opts = _normalize_bool_opts(
                    parsed_args[2] if len(parsed_args) > 2 else {}
                )
                result = coll.update_many(
                    parsed_args[0], parsed_args[1], **(opts or {})
                )
                affected_rows = result.modified_count
                result_doc = {
                    "acknowledged": result.acknowledged,
                    "matchedCount": result.matched_count,
                    "modifiedCount": result.modified_count,
                }
            elif method == "update":
                opts = _normalize_bool_opts(
                    parsed_args[2] if len(parsed_args) > 2 else {}
                )
                opts = opts or {}
                use_many = opts.get("multi", False) if isinstance(opts, dict) else False
                if use_many:
                    result = coll.update_many(parsed_args[0], parsed_args[1], **opts)
                else:
                    result = coll.update_one(parsed_args[0], parsed_args[1], **opts)
                affected_rows = result.modified_count
                result_doc = {
                    "acknowledged": result.acknowledged,
                    "matchedCount": result.matched_count,
                    "modifiedCount": result.modified_count,
                }
            elif method == "replaceOne":
                opts = _normalize_bool_opts(
                    parsed_args[2] if len(parsed_args) > 2 else {}
                )
                result = coll.replace_one(
                    parsed_args[0], parsed_args[1], **(opts or {})
                )
                affected_rows = result.modified_count
                result_doc = {
                    "acknowledged": result.acknowledged,
                    "matchedCount": result.matched_count,
                    "modifiedCount": result.modified_count,
                }
            elif method == "deleteOne":
                opts = _normalize_bool_opts(
                    parsed_args[1] if len(parsed_args) > 1 else {}
                )
                result = coll.delete_one(parsed_args[0], **(opts or {}))
                affected_rows = result.deleted_count
                result_doc = {
                    "acknowledged": result.acknowledged,
                    "deletedCount": result.deleted_count,
                }
            elif method == "deleteMany":
                opts = _normalize_bool_opts(
                    parsed_args[1] if len(parsed_args) > 1 else {}
                )
                result = coll.delete_many(parsed_args[0], **(opts or {}))
                affected_rows = result.deleted_count
                result_doc = {
                    "acknowledged": result.acknowledged,
                    "deletedCount": result.deleted_count,
                }
            elif method == "remove":
                opts = _normalize_bool_opts(
                    parsed_args[1] if len(parsed_args) > 1 else {}
                )
                opts = opts or {}
                just_one = (
                    opts.get("justOne", False) if isinstance(opts, dict) else False
                )
                if just_one:
                    result = coll.delete_one(parsed_args[0])
                else:
                    result = coll.delete_many(parsed_args[0])
                affected_rows = result.deleted_count
                result_doc = {
                    "acknowledged": result.acknowledged,
                    "deletedCount": result.deleted_count,
                }
            elif method == "drop":
                coll.drop()
                affected_rows = 0
                result_doc = {"ok": 1}
            elif method == "createCollection":
                coll_name = parsed_args[0] if parsed_args else None
                opts = parsed_args[1] if len(parsed_args) > 1 else {}
                db.create_collection(coll_name, **(opts or {}))
                affected_rows = 0
                result_doc = {"ok": 1}
            elif method in ("createIndex", "ensureIndex"):
                keys = parsed_args[0]
                if isinstance(keys, dict):
                    keys = list(keys.items())
                opts = parsed_args[1] if len(parsed_args) > 1 else {}
                idx_name = coll.create_index(keys, **(opts or {}))
                affected_rows = 0
                result_doc = {"ok": 1, "indexName": idx_name}
            elif method == "createIndexes":
                from pymongo.operations import IndexModel

                indexes = []
                for idx_def in parsed_args[0]:
                    keys = idx_def.get("key", {})
                    if isinstance(keys, dict):
                        keys = list(keys.items())
                    opts = {k: v for k, v in idx_def.items() if k != "key"}
                    indexes.append(IndexModel(keys, **opts))
                idx_names = coll.create_indexes(indexes)
                affected_rows = 0
                result_doc = {"ok": 1, "indexNames": idx_names}
            elif method == "dropIndex":
                coll.drop_index(parsed_args[0])
                affected_rows = 0
                result_doc = {"ok": 1}
            elif method == "dropIndexes":
                coll.drop_indexes()
                affected_rows = 0
                result_doc = {"ok": 1}
            elif method == "renameCollection":
                new_name = parsed_args[0] if parsed_args else None
                opts = parsed_args[1] if len(parsed_args) > 1 else {}
                coll.rename(new_name, **(opts or {}))
                affected_rows = 0
                result_doc = {"ok": 1}
            elif method == "convertToCapped":
                size = (
                    parsed_args[0].get("size", 0)
                    if isinstance(parsed_args[0], dict)
                    else parsed_args[0]
                )
                result = db.command("convertToCapped", collection, size=size)
                affected_rows = 0
                result_doc = result
            elif method == "bulkWrite":
                from pymongo.operations import (
                    InsertOne,
                    UpdateOne,
                    UpdateMany,
                    DeleteOne,
                    DeleteMany,
                    ReplaceOne,
                )

                operations = []
                ops_list = parsed_args[0]
                opts = parsed_args[1] if len(parsed_args) > 1 else {}

                for op in ops_list:
                    op_type = list(op.keys())[0]
                    op_detail = op[op_type]
                    if op_type == "insertOne":
                        operations.append(InsertOne(op_detail["document"]))
                    elif op_type == "updateOne":
                        operations.append(
                            UpdateOne(
                                op_detail["filter"],
                                op_detail["update"],
                                upsert=_to_bool(op_detail.get("upsert", False)),
                            )
                        )
                    elif op_type == "updateMany":
                        operations.append(
                            UpdateMany(
                                op_detail["filter"],
                                op_detail["update"],
                                upsert=_to_bool(op_detail.get("upsert", False)),
                            )
                        )
                    elif op_type == "deleteOne":
                        operations.append(DeleteOne(op_detail["filter"]))
                    elif op_type == "deleteMany":
                        operations.append(DeleteMany(op_detail["filter"]))
                    elif op_type == "replaceOne":
                        operations.append(
                            ReplaceOne(
                                op_detail["filter"],
                                op_detail["replacement"],
                                upsert=_to_bool(op_detail.get("upsert", False)),
                            )
                        )

                result = coll.bulk_write(operations, **(opts or {}))
                affected_rows = (
                    result.modified_count + result.deleted_count + result.inserted_count
                )
                result_doc = {
                    "acknowledged": result.acknowledged,
                    "insertedCount": result.inserted_count,
                    "matchedCount": result.matched_count,
                    "modifiedCount": result.modified_count,
                    "deletedCount": result.deleted_count,
                    "upsertedCount": result.upserted_count,
                }
            else:
                return False, f"暂不支持的语句: {sql}", 0

            return True, json.dumps(result_doc, ensure_ascii=False), affected_rows
        except Exception:
            logger.warning(
                f"mongo pymongo执行报错，语句：{sql}，错误信息{traceback.format_exc()}"
            )
            return False, str(traceback.format_exc()), 0

    def execute_workflow(self, workflow):
        """执行上线单，返回Review set"""
        return self.execute(
            db_name=workflow.db_name, sql=workflow.sqlworkflowcontent.sql_content
        )

    def execute(self, db_name=None, sql=""):
        """mongo命令执行语句"""
        self.get_master()
        execute_result = ReviewSet(full_sql=sql)
        sql = sql.strip()
        # 以；切分语句，逐句执行
        sp_sql = sql.split(";")
        line = 0
        for exec_sql in sp_sql:
            if not exec_sql == "":
                exec_sql = exec_sql.strip()
                try:
                    start = time.perf_counter()

                    success, r, actual_affected_rows = self._execute_shell_sql(
                        exec_sql, db_name
                    )
                    end = time.perf_counter()
                    line += 1
                    if not success:
                        execute_result.error = r
                        result = ReviewResult(
                            id=line,
                            stage="Execute failed",
                            errlevel=2,
                            stagestatus="异常终止",
                            errormessage=f"mongo语句执行报错: {r}",
                            sql=exec_sql,
                        )
                    else:
                        result = ReviewResult(
                            id=line,
                            errlevel=0,
                            stagestatus="执行结束",
                            errormessage=r,
                            execute_time=round(end - start, 6),
                            affected_rows=actual_affected_rows,
                            sql=exec_sql,
                        )
                    execute_result.rows += [result]
                except Exception as e:
                    logger.warning(
                        f"mongo语句执行报错，语句：{exec_sql}，错误信息{traceback.format_exc()}"
                    )
                    execute_result.error = str(e)
            # result_set.column_list = [i[0] for i in fields] if fields else []
        return execute_result

    def execute_check(self, db_name=None, sql=""):
        """上线单执行前的检查, 返回Review set"""
        line = 1
        count = 0
        check_result = ReviewSet(full_sql=sql)

        # 获取real_row_count参数选项
        real_row_count = SysConfig().get("real_row_count", False)

        sql = sql.strip()
        # sql 检查过滤注释语句
        sql = re.sub(r"^\s*//.*$", "", sql, flags=re.MULTILINE)
        if sql.find(";") < 0:
            raise Exception("提交的语句请以分号结尾")
        # 以；切分语句，逐句执行
        sp_sql = sql.split(";")
        # 执行语句
        for check_sql in sp_sql:
            alert = ""  # 警告信息
            check_sql = check_sql.strip()
            if not check_sql == "" and check_sql != "\n":
                # check_sql = f'''{check_sql}'''
                # check_sql = check_sql.replace('\n', '') #处理成一行
                # 支持的命令列表
                supportMethodList = [
                    "explain",
                    "bulkWrite",
                    "convertToCapped",
                    "createIndex",
                    "createIndexes",
                    "deleteOne",
                    "deleteMany",
                    "drop",
                    "dropIndex",
                    "dropIndexes",
                    "ensureIndex",
                    "insert",
                    "insertOne",
                    "insertMany",
                    "remove",
                    "replaceOne",
                    "renameCollection",
                    "update",
                    "updateOne",
                    "updateMany",
                    "createCollection",
                    "renameCollection",
                ]
                # 需要有表存在为前提的操作
                is_exist_premise_method = [
                    "convertToCapped",
                    "deleteOne",
                    "deleteMany",
                    "drop",
                    "dropIndex",
                    "dropIndexes",
                    "remove",
                    "replaceOne",
                    "renameCollection",
                    "update",
                    "updateOne",
                    "updateMany",
                    "renameCollection",
                ]
                pattern = re.compile(
                    r"""^db\.createCollection\(([\s\S]*)\)$|^db\.([\w\.-]+)\.(?:[A-Za-z]+)(?:\([\s\S]*\)$)|^db\.getCollection\((?:\s*)(?:'|")([\w\.-]+)('|")(\s*)\)\.([A-Za-z]+)(\([\s\S]*\)$)"""
                )
                m = pattern.match(check_sql)
                if (
                    m is not None
                    and (re.search(re.compile(r"}(?:\s*){"), check_sql) is None)
                    and check_sql.count("{") == check_sql.count("}")
                    and check_sql.count("(") == check_sql.count(")")
                ):
                    sql_str = m.group()
                    table_name = (
                        m.group(1) or m.group(2) or m.group(3)
                    ).strip()  # 通过正则的组拿到表名
                    table_name = table_name.replace('"', "").replace("'", "")
                    table_names = self.get_all_tables(db_name).rows
                    is_in = table_name in table_names  # 检查表是否存在
                    if not is_in:
                        alert = f"\n提示:{table_name}文档不存在!"
                    if sql_str:
                        count = 0
                        if (
                            sql_str.find("createCollection") > 0
                        ):  # 如果是db.createCollection()
                            methodStr = "createCollection"
                            alert = ""
                            if is_in:
                                check_result.error = "文档已经存在"
                                result = ReviewResult(
                                    id=line,
                                    errlevel=2,
                                    stagestatus="文档已经存在",
                                    errormessage="文档已经存在！",
                                    affected_rows=count,
                                    sql=check_sql,
                                )
                                check_result.rows += [result]
                                continue
                        else:
                            methodStr = sql_str.split(").")[-1].split("(")[0].strip()
                            if "." in methodStr:
                                methodStr = methodStr.split(".")[-1]
                        if methodStr in is_exist_premise_method and not is_in:
                            check_result.error = "文档不存在"
                            result = ReviewResult(
                                id=line,
                                errlevel=2,
                                stagestatus="文档不存在",
                                errormessage=f"文档不存在，不能进行{methodStr}操作！",
                                sql=check_sql,
                            )
                            check_result.rows += [result]
                            continue
                        if methodStr in supportMethodList:  # 检查方法是否支持
                            if (
                                methodStr == "createIndex"
                                or methodStr == "createIndexes"
                                or methodStr == "ensureIndex"
                            ):  # 判断是否创建索引，如果大于500万，提醒不能在高峰期创建
                                p_back = re.compile(
                                    r"""(['"])(?:(?!\1)background)\1(?:\s*):(?:\s*)true|background\s*:\s*true|(['"])(?:(?!\1)background)\1(?:\s*):(?:\s*)(['"])(?:(?!\2)true)\2""",
                                    re.M,
                                )
                                m_back = re.search(p_back, check_sql)
                                if m_back is None:
                                    count = 5555555
                                    check_result.warning = "创建索引请加background:true"
                                    check_result.warning_count += 1
                                    result = ReviewResult(
                                        id=line,
                                        errlevel=2,
                                        stagestatus="后台创建索引",
                                        errormessage="创建索引没有加 background:true"
                                        + alert,
                                        sql=check_sql,
                                    )
                                elif not is_in:
                                    count = 0
                                else:
                                    count = self.get_table_conut(
                                        table_name, db_name
                                    )  # 获得表的总条数
                                    if count >= 5000000:
                                        check_result.warning = (
                                            alert
                                            + "大于500万条，请在业务低谷期创建索引"
                                        )
                                        check_result.warning_count += 1
                                        result = ReviewResult(
                                            id=line,
                                            errlevel=1,
                                            stagestatus="大表创建索引",
                                            errormessage="大于500万条，请在业务低谷期创建索引！",
                                            affected_rows=count,
                                            sql=check_sql,
                                        )
                            if count < 5000000:
                                # 检测通过
                                affected_all_row_method = [
                                    "drop",
                                    "dropIndex",
                                    "dropIndexes",
                                    "createIndex",
                                    "createIndexes",
                                    "ensureIndex",
                                ]
                                if methodStr not in affected_all_row_method:
                                    count = 0
                                else:
                                    count = self.get_table_conut(
                                        table_name, db_name
                                    )  # 获得表的总条数
                                result = ReviewResult(
                                    id=line,
                                    errlevel=0,
                                    stagestatus="Audit completed",
                                    errormessage="检测通过",
                                    affected_rows=count,
                                    sql=check_sql,
                                    execute_time=0,
                                )
                            if real_row_count:
                                if methodStr == "insertOne":
                                    count = 1
                                elif methodStr in ("insert", "insertMany"):
                                    insert_str = re.search(
                                        rf"{methodStr}\((.*)\)", sql_str, re.S
                                    ).group(1)
                                    first_char = insert_str.replace(" ", "").replace(
                                        "\n", ""
                                    )[0]
                                    if first_char == "{":
                                        count = 1
                                    elif first_char == "[":
                                        insert_values = re.search(
                                            r"\[(.*?)\]", insert_str, re.S
                                        ).group(0)
                                        de = JsonDecoder()
                                        insert_values = de.decode(insert_values)
                                        count = len(insert_values)
                                    else:
                                        count = 0
                                elif methodStr in (
                                    "update",
                                    "updateOne",
                                    "updateMany",
                                    "deleteOne",
                                    "deleteMany",
                                    "remove",
                                ):
                                    if sql_str.find("find(") > 0:
                                        count_sql = sql_str.replace(methodStr, "count")
                                    else:
                                        count_sql = (
                                            sql_str.replace(methodStr, "find")
                                            + ".count()"
                                        )
                                    query_dict = self.parse_query_sentence(count_sql)
                                    count_sql = f"""db.getCollection("{query_dict["collection"]}").find({query_dict["condition"]}).count()"""
                                    query_result = self.query(db_name, count_sql)
                                    count = json.loads(query_result.rows[0][0]).get(
                                        "count", 0
                                    )
                                    if (
                                        methodStr == "update"
                                        and "multi:true"
                                        not in sql_str.replace(" ", "")
                                        .replace('"', "")
                                        .replace("'", "")
                                        .replace("\n", "")
                                    ) or methodStr in ("deleteOne", "updateOne"):
                                        count = 1 if count > 0 else 0
                            if methodStr in (
                                "insertOne",
                                "insert",
                                "insertMany",
                                "update",
                                "updateOne",
                                "updateMany",
                                "deleteOne",
                                "deleteMany",
                                "remove",
                            ):
                                result = ReviewResult(
                                    id=line,
                                    errlevel=0,
                                    stagestatus="Audit completed",
                                    errormessage="检测通过",
                                    affected_rows=count,
                                    sql=check_sql,
                                    execute_time=0,
                                )
                        else:
                            result = ReviewResult(
                                id=line,
                                errlevel=2,
                                stagestatus="驳回不支持语句",
                                errormessage="仅支持DML和DDL语句，如需查询请使用数据库查询功能！",
                                sql=check_sql,
                            )
                else:
                    check_result.error = "语法错误"
                    result = ReviewResult(
                        id=line,
                        errlevel=2,
                        stagestatus="语法错误",
                        errormessage="请检查语句的正确性或（）{} },{是否正确匹配！",
                        sql=check_sql,
                    )
                check_result.rows += [result]
                line += 1
                count = 0
        check_result.column_list = ["Result"]  # 审核结果的列名
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
        self.db_name = db_name or self.instance.db_name or "admin"
        auth_db = self.instance.db_name or "admin"

        options = {
            "host": self.host,
            "port": self.port,
            "username": self.user,
            "password": self.password,
            "authSource": auth_db,
            "connect": True,
            "connectTimeoutMS": 10000,
        }

        # only set TLS options while the instance enabled the TLS, to avoid
        # tlsInsecure option being set but the instance is not enabled the TLS
        # which would cause pymongo.ConfigurationError
        if self.instance.is_ssl:
            options["tls"] = True
            options["tlsInsecure"] = not self.instance.verify_ssl

        if self.user and self.password:
            self.conn = pymongo.MongoClient(**options)
        else:
            self.conn = pymongo.MongoClient(**options)

        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    name = "Mongo"

    info = "Mongo engine"

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
            db_list = conn.list_database_names()
        except OperationFailure:
            db_list = [self.db_name]
        result.rows = db_list
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
            for d in db[collection_name].find().sort([("_id", 1)]).limit(1):
                documents_sample.append(d)

            for d in db[collection_name].find().sort([("_id", -1)]).limit(1):
                documents_sample.append(d)
        columns = []
        # _merge_property_names
        for document in documents_sample:
            for prop in document:
                if prop not in columns:
                    columns.append(prop)
        result.column_list = ["COLUMN_NAME"]
        result.rows = columns
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        """return ResultSet 类似查询"""
        result = self.get_all_columns_by_tb(db_name=db_name, tb_name=tb_name)
        result.rows = [
            [
                [r],
            ]
            for r in result.rows
        ]
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
        raise Exception("near column %s,' or \" has no close" % index)

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
            raise Exception(
                "near column %s, The symbol %s has no closed" % (index, begin)
            )

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
                        p_index, condition = self.dispose_pair(
                            re_char, agg_index, "{", "}"
                        )
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
                    collection = re_char.strip().replace("'", "").replace('"', "")
                    query_dict["collection"] = collection
                elif method.lower() == "getindexes":
                    query_dict["method"] = "index_information"
                elif method == "count":
                    query_dict["method"] = "count"
                    if "condition" not in query_dict:
                        query_dict["condition"] = re_char
                    query_dict["count"] = re_char
                elif method == "findOne":
                    query_dict["method"] = method
                    if re_char.strip():
                        try:
                            p_index, fo_condition = self.dispose_pair(
                                re_char, 0, "{", "}"
                            )
                            query_dict["findOne_filter"] = fo_condition or "{}"
                            # dispose_pair 返回的 p_index 指向闭合大括号本身，需跳过
                            fo_projection = (
                                re_char[p_index + 1 :].strip().lstrip(",").strip()
                            )
                            if fo_projection:
                                query_dict["findOne_projection"] = fo_projection
                        except Exception:
                            query_dict["findOne_filter"] = "{}"
                    else:
                        query_dict["findOne_filter"] = "{}"
                elif method == "countDocuments":
                    query_dict["method"] = method
                    if re_char.strip():
                        try:
                            p_index, cd_condition = self.dispose_pair(
                                re_char, 0, "{", "}"
                            )
                            query_dict["countDocuments_filter"] = cd_condition or "{}"
                            # dispose_pair 返回的 p_index 指向闭合大括号本身，需跳过
                            cd_opts = re_char[p_index + 1 :].strip().lstrip(",").strip()
                            if cd_opts:
                                query_dict["countDocuments_options"] = cd_opts
                        except Exception:
                            query_dict["countDocuments_filter"] = "{}"
                    else:
                        query_dict["countDocuments_filter"] = "{}"
                elif method == "distinct":
                    query_dict["method"] = method
                    query_dict["distinct_args"] = re_char
                elif method == "stats":
                    query_dict["method"] = method
                else:
                    query_dict[method] = re_char
            index += 1

        logger.debug(query_dict)
        if query_dict:
            return query_dict

    def filter_sql(self, sql="", limit_num=0):
        """给查询语句改写语句, 返回修改后的语句"""
        sql = sql.split(";")[0].strip()
        # 执行计划
        if sql.startswith("explain"):
            sql = sql.replace("explain", "") + ".explain()"
        return sql.strip()

    def query_check(self, db_name=None, sql=""):
        """提交查询前的检查"""

        sql = sql.strip()
        sql = re.sub(r"^\s*//.*$", "", sql, flags=re.MULTILINE)
        if sql.startswith("explain"):
            sql = sql[7:] + ".explain()"
            sql = re.sub("[;\s]*.explain\(\)$", ".explain()", sql).strip()
        result = {"msg": "", "bad_query": False, "filtered_sql": sql, "has_star": False}
        pattern = re.compile(
            r"""^db\.(\w+\.?)+(?:\([\s\S]*\)(\s*;*)$)|^db\.getCollection\((?:\s*)(?:'|")(\w+\.?)+('|")(\s*)\)\.([A-Za-z]+)(\([\s\S]*\)(\s*;*)$)"""
        )
        m = pattern.match(sql)
        if m is not None:
            logger.debug(sql)
            query_dict = self.parse_query_sentence(sql)
            if "method" not in query_dict:
                result["msg"] += "错误：对不起，只支持查询相关方法"
                result["bad_query"] = True
                return result
            collection_name = query_dict["collection"]
            collection_names = self.get_all_tables(db_name).rows
            is_in = collection_name in collection_names  # 检查表是否存在
            if not is_in:
                result["msg"] += f"\n错误: {collection_name} 文档不存在!"
                result["bad_query"] = True
                return result
        else:
            result["msg"] += "请检查语句的正确性! 请使用原生查询语句"
            result["bad_query"] = True
        return result

    def query(self, db_name=None, sql="", limit_num=0, close_conn=True, **kwargs):
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
                # 给aggregate查询加limit行数限制，防止返回结果过多导致archery挂掉
                condition.append({"$limit": limit_num})
            if method == "find":
                condition = de.decode(query_dict["condition"])
            if method == "count":
                condition = (
                    de.decode(query_dict["condition"])
                    if query_dict.get("condition")
                    else {}
                )
                condition = condition or {}
            find_cmd += "(condition)"
        if "projection" in query_dict and query_dict["projection"]:
            projection = de.decode(query_dict["projection"])
            find_cmd = find_cmd[:-1] + ",projection)"
        if "sort" in query_dict and query_dict["sort"]:
            sorting = []
            for k, v in de.decode(query_dict["sort"]).items():
                sorting.append((k, v))
            find_cmd += ".sort(sorting)"
        if (
            method == "find"
            and "limit" not in query_dict
            and "explain" not in query_dict
        ):
            find_cmd += ".limit(limit_num)"
        if "limit" in query_dict and query_dict["limit"]:
            query_limit = int(query_dict["limit"])
            limit = min(limit_num, query_limit) if query_limit else limit_num
            find_cmd += f".limit({limit})"
        if "skip" in query_dict and query_dict["skip"]:
            query_skip = int(query_dict["skip"])
            find_cmd += f".skip({query_skip})"
        if "count" in query_dict:
            if condition:
                find_cmd = "collection.count_documents(condition)"
            else:
                find_cmd = "collection.count_documents({})"
        if "explain" in query_dict:
            find_cmd += ".explain()"

        # 覆盖 findOne/countDocuments/distinct/stats 对应的 pymongo 命令
        if method == "findOne":
            findone_filter = de.decode(query_dict.get("findOne_filter", "{}")) or {}
            if "findOne_projection" in query_dict:
                findone_projection = de.decode(query_dict["findOne_projection"])
                find_cmd = "collection.find_one(findone_filter, findone_projection)"
            else:
                find_cmd = "collection.find_one(findone_filter)"
        elif method == "countDocuments":
            countdoc_filter = (
                de.decode(query_dict.get("countDocuments_filter", "{}")) or {}
            )
            if "countDocuments_options" in query_dict:
                countdoc_options = de.decode(query_dict["countDocuments_options"]) or {}
                find_cmd = (
                    "collection.count_documents(countdoc_filter, **countdoc_options)"
                )
            else:
                find_cmd = "collection.count_documents(countdoc_filter)"
        elif method == "distinct":
            distinct_parts = self.__split_args(query_dict.get("distinct_args", "")) or [
                ""
            ]
            distinct_field = distinct_parts[0].strip().strip('"').strip("'")
            if len(distinct_parts) > 1 and distinct_parts[1].strip():
                distinct_filter = de.decode(distinct_parts[1]) or {}
                find_cmd = "collection.distinct(distinct_field, distinct_filter)"
            else:
                find_cmd = "collection.distinct(distinct_field)"
        elif method == "stats":
            find_cmd = 'db.command("collStats", collection_name)'

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
            elif method == "findOne":
                columns.append("findOne")
                if cursor is None:
                    rows = []
                else:
                    doc = json.loads(json_util.dumps(cursor))
                    rows = [doc]
            elif method == "countDocuments":
                columns.append("count")
                rows.append({"count": cursor})
            elif method == "distinct":
                columns.append("distinct")
                distinct_values = json.loads(json_util.dumps(cursor))
                for v in distinct_values:
                    rows.append({"value": v})
            elif method == "stats":
                columns.append("stats")
                stats_result = json.loads(json_util.dumps(cursor))
                for k, v in stats_result.items():
                    if k != "ok":
                        rows.append({k: v})
            elif method == "aggregate" and sql.find("$group") >= 0:  # 生成聚合数据
                row = []
                columns.insert(0, "mongodballdata")
                for ro in cursor:
                    json_col = json.dumps(
                        ro, ensure_ascii=False, indent=2, separators=(",", ":")
                    )
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
                cols = projection if "projection" in dir() else None
                rows, columns = self.parse_tuple(cursor, db_name, collection_name, cols)
                result_set.rows = rows
            result_set.column_list = columns
            result_set.affected_rows = len(rows)
            if isinstance(rows, list):
                logger.debug(rows)
                result_set.rows = tuple(
                    [json.dumps(x, ensure_ascii=False, indent=2, separators=(",", ":"))]
                    for x in rows
                )

        except Exception as e:
            logger.warning(
                f"Mongo命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}"
            )
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
            json_col = json.dumps(
                ro, ensure_ascii=False, indent=2, separators=(",", ":")
            )
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
                        value = str(value).replace(
                            ii, "ObjectId(" + ii.split(":")[1].strip()[:-1] + ")"
                        )
                    # 转换时间戳$date
                    dd = re.findall(re_date, str(value))
                    for d in dd:
                        t = int(d.split(":")[1].strip()[:-1])
                        e = datetime.datetime.fromtimestamp(t / 1000)
                        value = str(value).replace(
                            d, e.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        )
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

    def processlist(self, command_type, **kwargs):
        """
        获取当前连接信息

        command_type:
        Full    包含活跃与不活跃的连接，包含内部的连接，即全部的连接状态
        All     包含活跃与不活跃的连接，不包含内部的连接
        Active  包含活跃
        Inner   内部连接
        """
        result_set = ResultSet(
            full_sql='db.aggregate([{"$currentOp": {"allUsers":true, "idleConnections":true}}])'
        )
        try:
            conn = self.get_connection()
            processlists = []
            if not command_type:
                command_type = "Active"
            if command_type in ["Full", "All", "Inner"]:
                idle_connections = True
            else:
                idle_connections = False

            # conn.admin.current_op() 这个方法已经被pymongo废除，但mongodb3.6+才支持aggregate
            with conn.admin.aggregate(
                [
                    {
                        "$currentOp": {
                            "allUsers": True,
                            "idleConnections": idle_connections,
                        }
                    }
                ]
            ) as cursor:
                for operation in cursor:
                    # 对sharding集群的特殊处理
                    if "client" not in operation and operation.get(
                        "clientMetadata", {}
                    ).get("mongos", {}).get("client", {}):
                        operation["client"] = operation["clientMetadata"]["mongos"][
                            "client"
                        ]

                    # 获取此会话的用户名
                    effective_users_key = "effectiveUsers_user"
                    effective_users = operation.get("effectiveUsers", [])
                    if isinstance(effective_users, list) and effective_users:
                        first_user = effective_users[0]
                        if isinstance(first_user, dict):
                            operation[effective_users_key] = first_user.get("user", [])
                        else:
                            operation[effective_users_key] = None
                    else:
                        operation[effective_users_key] = None

                    # client_s 只是处理的mongos，并不是实际客户端
                    # client 在sharding获取不到？
                    if command_type in ["Full"]:
                        processlists.append(operation)
                    elif command_type in ["All", "Active"]:
                        if "clientMetadata" in operation:
                            processlists.append(operation)
                    elif command_type in ["Inner"]:
                        if not "clientMetadata" in operation:
                            processlists.append(operation)

            result_set.rows = processlists
        except Exception as e:
            logger.warning(f"mongodb获取连接信息错误，错误信息{traceback.format_exc()}")
            result_set.error = str(e)

        return result_set

    def get_kill_command(self, opids):
        """由传入的opid列表生成kill字符串"""
        conn = self.get_connection()
        active_opid = []
        with conn.admin.aggregate(
            [{"$currentOp": {"allUsers": True, "idleConnections": False}}]
        ) as cursor:
            for operation in cursor:
                if "opid" in operation and operation["opid"] in opids:
                    active_opid.append(operation["opid"])

        kill_command = ""
        for opid in active_opid:
            if isinstance(opid, int):
                kill_command = kill_command + "db.killOp({});".format(opid)
            else:
                kill_command = kill_command + 'db.killOp("{}");'.format(opid)

        return kill_command

    def kill_op(self, opids):
        """kill"""
        result = ResultSet()
        try:
            conn = self.get_connection()
        except Exception as e:
            logger.error(f"{self.name} 连接失败, error: {str(e)}")
            result.error = str(e)
            return result
        for opid in opids:
            try:
                conn.admin.command({"killOp": 1, "op": opid})
            except Exception as e:
                sql = {"killOp": 1, "op": opid}
                logger.warning(
                    f"{self.name}语句执行killOp报错，语句：db.runCommand({sql}) ，错误信息{traceback.format_exc()}"
                )
                result.error = str(e)
        return result

    # 排除的系统库
    forbidden_databases = [
        "admin",
        "config",
        "local",
    ]

    def tablespace(self, offset=0, row_count=14, schema_search=""):
        """获取表空间信息"""
        result_set = ResultSet(
            full_sql="db.collection.aggregate([ { $collStats: { storageStats: { } } } ])"
        )
        try:
            conn = self.get_connection()
            try:
                db_list = conn.list_database_names()
            except OperationFailure:
                db_list = [self.db_name]

            rows = []
            for db_name in db_list:
                if db_name in self.forbidden_databases:
                    continue
                db = conn[db_name]
                collection_names = db.list_collection_names()
                for coll_name in collection_names:
                    try:
                        stats_cursor = db[coll_name].aggregate(
                            [{"$collStats": {"storageStats": {}}}]
                        )
                        for stats in stats_cursor:
                            storage = stats.get("storageStats", {})
                            row = {
                                "ns": storage.get("ns", f"{db_name}.{coll_name}"),
                                "totalSize": round(
                                    storage.get("totalSize", 0) / 1024 / 1024, 2
                                ),
                                "count": storage.get("count", 0),
                                "size": round(storage.get("size", 0) / 1024 / 1024, 2),
                                "avgObjSize": storage.get("avgObjSize", 0),
                                "storageSize": round(
                                    storage.get("storageSize", 0) / 1024 / 1024, 2
                                ),
                                "freeStorageSize": round(
                                    storage.get("freeStorageSize", 0) / 1024 / 1024, 2
                                ),
                                "capped": storage.get("capped", False),
                                "nindexes": storage.get("nindexes", 0),
                                "totalIndexSize": round(
                                    storage.get("totalIndexSize", 0) / 1024 / 1024, 2
                                ),
                            }
                            rows.append(row)
                    except Exception as e:
                        logger.warning(
                            f"mongodb获取集合{db_name}.{coll_name}存储信息错误，错误信息{str(e)}"
                        )
                        continue

            # 搜索过滤
            if schema_search:
                search_lower = schema_search.lower()
                rows = [
                    row for row in rows if search_lower in row.get("ns", "").lower()
                ]

            # 按照 totalSize 倒序
            rows.sort(key=lambda x: x["totalSize"], reverse=True)
            # 分页
            rows = rows[offset : offset + row_count]
            result_set.rows = rows
            result_set.column_list = [
                "ns",
                "totalSize",
                "count",
                "size",
                "avgObjSize",
                "storageSize",
                "freeStorageSize",
                "capped",
                "nindexes",
                "totalIndexSize",
            ]
        except Exception as e:
            logger.warning(
                f"mongodb获取表空间信息错误，错误信息{traceback.format_exc()}"
            )
            result_set.error = str(e)
        return result_set

    def tablespace_count(self, schema_search=""):
        """获取表空间数量"""
        result_set = ResultSet()
        try:
            conn = self.get_connection()
            try:
                db_list = conn.list_database_names()
            except OperationFailure:
                db_list = [self.db_name]

            count = 0
            for db_name in db_list:
                if db_name in self.forbidden_databases:
                    continue
                db = conn[db_name]
                collection_names = db.list_collection_names()
                if schema_search:
                    search_lower = schema_search.lower()
                    collection_names = [
                        c
                        for c in collection_names
                        if search_lower in f"{db_name}.{c}".lower()
                    ]
                count += len(collection_names)
            result_set.rows = [(count,)]
        except Exception as e:
            logger.warning(
                f"mongodb获取表空间数量错误，错误信息{traceback.format_exc()}"
            )
            result_set.error = str(e)
        return result_set

    def get_all_databases_summary(self):
        """实例数据库管理功能，获取实例所有的数据库描述信息"""
        query_result = self.get_all_databases()
        if not query_result.error:
            dbs = query_result.rows
            conn = self.get_connection()

            # 获取数据库用户信息
            rows = []
            for db_name in dbs:
                # 执行语句
                listing = conn[db_name].command(command="usersInfo")
                grantees = []
                for user_obj in listing["users"]:
                    grantees.append(
                        {"user": user_obj["user"], "roles": user_obj["roles"]}.__str__()
                    )
                row = {
                    "db_name": db_name,
                    "grantees": grantees,
                    "saved": False,
                }
                rows.append(row)
            query_result.rows = rows
        return query_result

    def get_instance_users_summary(self):
        """实例账号管理功能，获取实例所有账号信息"""
        query_result = self.get_all_databases()
        if not query_result.error:
            dbs = query_result.rows
            conn = self.get_connection()

            # 获取数据库用户信息
            rows = []
            for db_name in dbs:
                # 执行语句
                listing = conn[db_name].command(command="usersInfo")
                for user_obj in listing["users"]:
                    rows.append(
                        {
                            "db_name_user": f"{db_name}.{user_obj['user']}",
                            "db_name": db_name,
                            "user": user_obj["user"],
                            "roles": [role["role"] for role in user_obj["roles"]],
                            "saved": False,
                        }
                    )
            query_result.rows = rows
        return query_result

    def create_instance_user(self, **kwargs):
        """实例账号管理功能，创建实例账号"""
        exec_result = ResultSet()
        db_name = kwargs.get("db_name", "")
        user = kwargs.get("user", "")
        password1 = kwargs.get("password1", "")
        remark = kwargs.get("remark", "")
        try:
            conn = self.get_connection()
            conn[db_name].command("createUser", user, pwd=password1, roles=[])
            exec_result.rows = [
                {
                    "instance": self.instance,
                    "db_name": db_name,
                    "user": user,
                    "password": password1,
                    "remark": remark,
                }
            ]
        except Exception as e:
            exec_result.error = str(e)
        return exec_result

    def drop_instance_user(self, db_name_user: str, **kwarg):
        """实例账号管理功能，删除实例账号"""
        arr = db_name_user.split(".")
        db_name = arr[0]
        user = arr[1]
        exec_result = ResultSet()
        try:
            conn = self.get_connection()
            conn[db_name].command("dropUser", user)
        except Exception as e:
            exec_result.error = str(e)
        return exec_result

    def reset_instance_user_pwd(self, db_name_user: str, reset_pwd: str, **kwargs):
        """实例账号管理功能，重置实例账号密码"""
        arr = db_name_user.split(".")
        db_name = arr[0]
        user = arr[1]
        exec_result = ResultSet()
        try:
            conn = self.get_connection()
            conn[db_name].command("updateUser", user, pwd=reset_pwd)
        except Exception as e:
            exec_result.error = str(e)
        return exec_result

    def query_masking(self, db_name=None, sql="", resultset=None):
        """传入 sql语句, db名, 结果集,
        返回一个脱敏后的结果集"""
        mask_result = data_masking(self.instance, db_name, sql, resultset)
        return mask_result
