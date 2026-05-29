# -*- coding: UTF-8 -*-
import taosws
from .models import ResultSet, ReviewResult, ReviewSet
from sql.utils.sql_utils import get_syntax_type
from common.utils.timer import FuncTimer
from common.config import SysConfig
from . import EngineBase
from pymysql import escape_string
import sqlparse
import logging
import re

logger = logging.getLogger("default")


class TDengineEngine(EngineBase):
    test_query = "SELECT 1"

    def __init__(self, instance=None):
        super(TDengineEngine, self).__init__(instance=instance)
        self.config = SysConfig()

    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if db_name:
            self.conn = taosws.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=db_name,
                read_timeout="600",
            )
        else:
            self.conn = taosws.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                read_timeout="600",
            )
        return self.conn

    name = "TDengine"
    info = "TDengine engine"

    def escape_string(self, value: str) -> str:
        """字符串参数转义"""
        return escape_string(value)

    @property
    def auto_backup(self):
        """是否支持备份"""
        return False

    @property
    def server_version(self):
        sql = "select server_version();"
        result = self.query(sql=sql)
        version = result.rows[0][0]
        return tuple([int(n) for n in version.split(".")[:3]])

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "show databases"
        result = self.query(sql=sql)
        db_list = [
            row[0]
            for row in result.rows
            if row[0] not in ("information_schema", "performance_schema", "log")
        ]
        result.rows = sorted(db_list)
        return result

    def get_all_tables(self, db_name, **kwargs):
        """获取table 列表, 包含普通表和超级表，返回一个ResultSet"""
        ntable_sql = """select
            table_name
        from
            information_schema.ins_tables
        where 
            type = 'NORMAL_TABLE'
        and db_name = '%s';
        """ % self.escape_string(db_name)
        table_result = self.query(db_name=db_name, sql=ntable_sql)
        tb_list = sorted([row[0] for row in table_result.rows])
        tb_list.insert(0, "普通表") if tb_list else []
        stable_sql = """select
            stable_name
        from
            information_schema.ins_stables
        where 
            db_name = '%s';
        """ % self.escape_string(db_name)
        stable_result = self.query(db_name=db_name, sql=stable_sql)
        stb_list = sorted([row[0] for row in stable_result.rows])
        stb_list.insert(0, "超级表") if stb_list else []
        tb_list.extend(stb_list)
        stable_result.rows = tb_list
        return stable_result

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet"""
        sql = """select
            col_name,
            col_type
        from
            information_schema.ins_columns
        where
            db_name = '%s'
        and table_name = '%s';"""
        result = self.query(
            db_name=db_name,
            sql=sql,
            parameters=(db_name, tb_name),
        )
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def get_table_type(self, db_name, tb_name, **kwargs):
        """获取表类型, 返回stable或table"""
        stable_sql = """select
            stable_name
        from
            information_schema.ins_stables
        where
            db_name = '%s'
        and stable_name = '%s';"""
        stable_result = self.query(
            db_name=db_name,
            sql=stable_sql,
            parameters=(db_name, tb_name),
        )
        if stable_result.rows:
            return "stable"
        table_sql = """select
            table_name
        from
            information_schema.ins_tables
        where
            db_name = '%s'
        and table_name = '%s';"""
        table_result = self.query(
            db_name=db_name,
            sql=table_sql,
            parameters=(db_name, tb_name),
        )
        if table_result.rows:
            return "table"
        return None

    def describe_table(self, db_name, tb_name, **kwargs):
        """return ResultSet 类似查询"""
        tb_name = self.escape_string(tb_name)
        table_type = self.get_table_type(db_name, tb_name)
        if table_type == "table":
            sql = f"show create table `{tb_name}`;"
        else:
            sql = f"show create stable `{tb_name}`;"
        result = self.query(db_name=db_name, sql=sql)
        formatted = re.sub(
            r"(CREATE\s+(?:STABLE|TABLE)\s+`[^`]+`\s*)\(`",
            r"\1(\n    `",
            result.rows[0][1],
        )
        formatted = formatted.replace(", `", ",\n    `")
        formatted = re.sub(r"\)\s*TAGS", "\n)\nTAGS", formatted)
        formatted = re.sub(r"\)\s*SMA", "\n)\nSMA", formatted)
        formatted = formatted.replace("TAGS (`", "TAGS (\n    `")
        formatted = formatted.replace("SMA(`", "SMA(\n    `")
        formatted = re.sub(r"(?<!\n)\)\s*$", r"\n)", formatted)

        result.rows[0] = (tb_name,) + (formatted,)
        return result

    def query(
        self,
        db_name=None,
        sql="",
        limit_num=0,
        close_conn=True,
        parameters=None,
        **kwargs,
    ):
        """返回 ResultSet"""
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection(db_name=db_name)
            cursor = conn.cursor()
            if parameters:
                parameters = tuple(self.escape_string(str(p)) for p in parameters)
                cursor.execute(sql % parameters)
            else:
                cursor.execute(sql)
            if int(limit_num) > 0:
                rows = cursor.fetchmany(size=int(limit_num))
            else:
                rows = cursor.fetchall()
            fields = cursor.description

            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = rows
            result_set.affected_rows = len(rows)
        except Exception as e:
            logger.warning(f"TDengine语句执行报错，语句：{sql}，错误信息{e}")
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    def query_check(self, db_name=None, sql=""):
        # 查询语句的检查、注释去除、切分
        result = {"msg": "", "bad_query": False, "filtered_sql": sql, "has_star": False}
        # 删除注释语句，进行语法判断，执行第一条有效sql
        try:
            sql = sqlparse.format(sql, strip_comments=True)
            sql = sqlparse.split(sql)[0]
            result["filtered_sql"] = sql.strip()
        except IndexError:
            result["bad_query"] = True
            result["msg"] = "没有有效的SQL语句"
        if re.match(r"^select|^show|^explain|^with", sql, re.I) is None:
            result["bad_query"] = True
            result["msg"] = "不支持的查询语法类型!"
        if "*" in sql:
            result["has_star"] = True
            result["msg"] = "SQL语句中含有 * "
        # select语句先使用Explain判断语法是否正确
        if re.match(r"^select", sql, re.I):
            explain_result = self.query(db_name=db_name, sql=f"explain {sql}")
            if explain_result.error:
                result["bad_query"] = True
                result["msg"] = explain_result.error

        return result

    def filter_sql(self, sql="", limit_num=0):
        # 对查询sql增加limit限制,limit n 或 limit n,n 或 limit n offset n统一改写成limit n
        sql = sql.rstrip(";").strip()
        if re.match(r"^select", sql, re.I):
            # LIMIT N
            limit_n = re.compile(r"limit\s+(\d+)\s*$", re.I)
            # LIMIT M OFFSET N
            limit_offset = re.compile(r"limit\s+(\d+)\s+offset\s+(\d+)\s*$", re.I)
            # LIMIT M,N
            offset_comma_limit = re.compile(r"limit\s+(\d+)\s*,\s*(\d+)\s*$", re.I)
            if limit_n.search(sql):
                sql_limit = limit_n.search(sql).group(1)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_n.sub(f"limit {limit_num};", sql)
            elif limit_offset.search(sql):
                sql_limit = limit_offset.search(sql).group(1)
                sql_offset = limit_offset.search(sql).group(2)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_offset.sub(f"limit {limit_num} offset {sql_offset};", sql)
            elif offset_comma_limit.search(sql):
                sql_offset = offset_comma_limit.search(sql).group(1)
                sql_limit = offset_comma_limit.search(sql).group(2)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = offset_comma_limit.sub(f"limit {sql_offset},{limit_num};", sql)
            else:
                sql = f"{sql} limit {limit_num};"
        else:
            sql = f"{sql};"
        return sql

    def processlist(self, command_type, **kwargs):
        """获取query会话信息"""
        sql = "show queries"

        return self.query(sql=sql)

    def get_kill_command(self, kill_ids):
        """由传入的kill_id列表生成kill命令"""
        # 校验传参，kill_ids格式：[kill_id1:xxx, kill_id2:xxx]
        if any(
            [
                i if re.fullmatch(r"[0-9a-zA-Z]+:[0-9a-zA-Z]+", i) is None else None
                for i in kill_ids
            ]
        ):
            return None
        all_kill_sql = "".join(f"kill query '{i}';" for i in kill_ids)

        return all_kill_sql

    def kill_query(self, kill_ids):
        """kill query"""
        # 校验传参，kill_ids格式：[kill_id1:xxx, kill_id2:xxx]
        if any(
            [
                i if re.fullmatch(r"[0-9a-zA-Z]+:[0-9a-zA-Z]+", i) is None else None
                for i in kill_ids
            ]
        ):
            return ResultSet(full_sql="")
        # 查询最新processlist，校验query还未完成的，才进行kill操作
        processlist_result = self.processlist(command_type="all")
        latest_kill_ids = [row[0] for row in processlist_result.rows]
        valid_kill_ids = [i for i in kill_ids if i in latest_kill_ids]
        if not valid_kill_ids:
            return ResultSet(full_sql="")
        all_kill_sql = "".join(f"kill query '{i}';" for i in valid_kill_ids)
        return self.execute(sql=all_kill_sql)

    def execute(self, db_name=None, sql="", close_conn=True, parameters=None):
        """执行语句"""
        result = ResultSet(full_sql=sql)
        conn = self.get_connection(db_name=db_name)
        try:
            cursor = conn.cursor()
            for statement in sqlparse.split(sql):
                execute_result = cursor.execute(statement)
                result.affected_rows += execute_result
            cursor.close()
        except Exception as e:
            logger.warning(f"TDengine语句执行报错，语句：{sql}，错误信息{e}")
            result.error = str(e)
        if close_conn:
            self.close()
        return result

    def obj_check(self, db_name=None, obj_name=None, obj_type="table"):
        """判断对象是否存在，返回 {'exists': bool, 'type': str|None}。

        obj_type 仅支持：database、table。
        table 类型会按 stable(超级表) -> ctable(子表) -> table(普通表) 顺序检查。
        支持带反引号的对象名，例如 xx.`xxx` 或 `xx`.`xxx`。
        """
        raw_db_name = (db_name or "").strip()
        raw_obj_name = (obj_name or "").strip()

        def _normalize_ident(name):
            return name.strip().strip("`")

        db_name = self.escape_string(_normalize_ident(raw_db_name))

        result = {"exists": False, "type": None}

        if obj_type == "database":
            normalized_obj_name = self.escape_string(_normalize_ident(raw_obj_name))
            sql = """select
                name
            from
                information_schema.ins_databases
            where
                name = '%s';""" % normalized_obj_name
            db_result = self.query(sql=sql)
            if db_result.rows:
                result["exists"] = True
                result["type"] = "database"
            return result

        if obj_type != "table" or not raw_obj_name:
            return result

        # obj_name 支持 table / db.table / db.`table` / `db`.`table`。
        qualified_match = re.match(
            r"^\s*(?:`([^`]+)`|([a-zA-Z_][0-9a-zA-Z_]*))\s*\.\s*(?:`([^`]+)`|([a-zA-Z_][0-9a-zA-Z_]*))\s*$",
            raw_obj_name,
        )
        has_db_prefix = qualified_match is not None
        search_db_name = db_name
        search_obj_name = self.escape_string(_normalize_ident(raw_obj_name))
        if has_db_prefix:
            parsed_db = qualified_match.group(1) or qualified_match.group(2)
            parsed_obj = qualified_match.group(3) or qualified_match.group(4)
            search_db_name = self.escape_string(_normalize_ident(parsed_db))
            search_obj_name = self.escape_string(_normalize_ident(parsed_obj))

        if not search_db_name or not search_obj_name:
            return result

        stable_sql = """select
            stable_name
        from
            information_schema.ins_stables
        where
            db_name = '%s'
        and stable_name = '%s';""" % (search_db_name, search_obj_name)
        stable_result = self.query(db_name=search_db_name, sql=stable_sql)
        if stable_result.rows:
            result["exists"] = True
            result["type"] = "stable"
            return result

        ctable_sql = """select
            table_name
        from
            information_schema.ins_tables
        where
            db_name = '%s'
        and table_name = '%s'
        and type = 'CHILD_TABLE';""" % (search_db_name, search_obj_name)
        ctable_result = self.query(db_name=search_db_name, sql=ctable_sql)
        if ctable_result.rows:
            result["exists"] = True
            result["type"] = "ctable"

        table_sql = """select
            table_name
        from
            information_schema.ins_tables
        where
            db_name = '%s'
        and table_name = '%s'
        and type = 'NORMAL_TABLE';""" % (search_db_name, search_obj_name)
        table_result = self.query(db_name=search_db_name, sql=table_sql)
        if table_result.rows:
            result["exists"] = True
            result["type"] = "table"
            return result

        return result

    def execute_check(self, db_name=None, sql=""):
        """上线单执行前的检查, 返回Review set"""
        sql = sqlparse.format(sql, strip_comments=True)
        sql_list = sqlparse.split(sql)

        bare_ident = r"[a-zA-Z_][0-9a-zA-Z_]*"
        quoted_ident = r"`[^`]+`"
        ident = rf"(?:{quoted_ident}|{bare_ident})"
        ident_with_db = rf"{ident}(?:\s*\.\s*{ident})?"
        table_option = r"(?:ttl\s+\d+|comment\s+'[^']*')"
        stable_option = r"(?:comment\s+'[^']*'|keep\s+\d+)"
        created_databases = set()
        created_tables = {}

        def _success_result(statement, line):
            return ReviewResult(
                id=line,
                errlevel=0,
                stagestatus="Audit completed",
                errormessage="None",
                sql=statement,
                affected_rows=0,
                execute_time=0,
            )

        def _build_option_patterns(patterns):
            return [re.compile(rf"\s*(?:{p})", re.I | re.S) for p in patterns]

        def _is_valid_option_sequence(option_str, option_patterns):
            option_str = (option_str or "").strip()
            if not option_str:
                return True
            pos = 0
            length = len(option_str)
            while pos < length:
                matched = False
                for ptn in option_patterns:
                    m = ptn.match(option_str, pos)
                    if m and m.end() > pos:
                        pos = m.end()
                        matched = True
                        break
                if not matched:
                    return False
                while pos < length and option_str[pos].isspace():
                    pos += 1
            return True

        def _normalize_sql_name(name):
            return re.sub(r"\s*\.\s*", ".", name.strip())

        def _strip_ident_quotes(name):
            return name.strip().strip("`")

        def _object_key(raw_name, default_db=None):
            normalized = _normalize_sql_name(raw_name)
            parts = normalized.split(".", 1)
            if len(parts) == 2:
                return (_strip_ident_quotes(parts[0]), _strip_ident_quotes(parts[1]))
            return (
                _strip_ident_quotes(default_db or ""),
                _strip_ident_quotes(parts[0]),
            )

        def _workflow_obj_check(db_name=None, obj_name=None, obj_type="table"):
            result = self.obj_check(
                db_name=db_name, obj_name=obj_name, obj_type=obj_type
            )
            if result["exists"]:
                return result
            if obj_type == "database":
                db_key = _strip_ident_quotes(obj_name or "")
                if db_key in created_databases:
                    return {"exists": True, "type": "database"}
                return result
            if obj_type == "table":
                table_type = created_tables.get(_object_key(obj_name or "", db_name))
                if table_type:
                    return {"exists": True, "type": table_type}
            return result

        def _mark_database_created(name):
            created_databases.add(_strip_ident_quotes(name))

        def _mark_table_created(name, table_type, default_db=None):
            created_tables[_object_key(name, default_db)] = table_type

        def _consume_parenthesized(text, start):
            if start >= len(text) or text[start] != "(":
                return None
            depth = 0
            quote = None
            index = start
            while index < len(text):
                ch = text[index]
                if quote:
                    if ch == quote:
                        if (
                            quote == "'"
                            and index + 1 < len(text)
                            and text[index + 1] == "'"
                        ):
                            index += 2
                            continue
                        quote = None
                    index += 1
                    continue
                if ch in ("'", "`"):
                    quote = ch
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        return text[start + 1 : index], index + 1
                index += 1
            return None

        def _match_ident_at(text, pos):
            return re.match(rf"\s*({ident_with_db})", text[pos:], re.I | re.S)

        def _parse_ident_list(list_str):
            return [
                _strip_ident_quotes(i.strip()).lower()
                for i in list_str.split(",")
                if i.strip()
            ]

        def _parse_file_clause(text, pos):
            return re.match(r"\s*file\s+'[^']+'\s*", text[pos:], re.I | re.S)

        def _parse_insert_blocks(insert_body):
            rest = insert_body
            pos = 0
            blocks = []
            while pos < len(rest):
                ident_match = _match_ident_at(rest, pos)
                if not ident_match:
                    return []
                tb_name = _normalize_sql_name(ident_match.group(1).strip())
                pos += ident_match.end()

                using_name = None
                using_match = re.match(
                    rf"\s+using\s+({ident_with_db})", rest[pos:], re.I | re.S
                )
                if using_match:
                    using_name = _normalize_sql_name(using_match.group(1).strip())
                    pos += using_match.end()
                    if pos < len(rest) and rest[pos:].lstrip().startswith("("):
                        pos += len(rest[pos:]) - len(rest[pos:].lstrip())
                        parsed_cols = _consume_parenthesized(rest, pos)
                        if not parsed_cols:
                            return []
                        pos = parsed_cols[1]
                    tags_match = re.match(r"\s+tags\s*", rest[pos:], re.I | re.S)
                    if not tags_match:
                        return []
                    pos += tags_match.end()
                    pos += len(rest[pos:]) - len(rest[pos:].lstrip())
                    parsed_tags = _consume_parenthesized(rest, pos)
                    if not parsed_tags:
                        return []
                    pos = parsed_tags[1]

                columns = []
                pos += len(rest[pos:]) - len(rest[pos:].lstrip())
                if pos < len(rest) and rest[pos] == "(":
                    parsed_columns = _consume_parenthesized(rest, pos)
                    if not parsed_columns:
                        return []
                    columns = _parse_ident_list(parsed_columns[0])
                    pos = parsed_columns[1]

                values_match = re.match(r"\s*values\s*", rest[pos:], re.I | re.S)
                file_match = _parse_file_clause(rest, pos)
                if values_match:
                    pos += values_match.end()
                    parsed_values = False
                    while True:
                        pos += len(rest[pos:]) - len(rest[pos:].lstrip())
                        if pos >= len(rest) or rest[pos] != "(":
                            break
                        parsed_tuple = _consume_parenthesized(rest, pos)
                        if not parsed_tuple:
                            return []
                        parsed_values = True
                        pos = parsed_tuple[1]
                    if not parsed_values:
                        return []
                elif file_match:
                    pos += file_match.end()
                else:
                    return []

                blocks.append((tb_name, using_name, "tbname" in columns))
                pos += len(rest[pos:]) - len(rest[pos:].lstrip())
            return blocks

        def _parse_subtable_blocks(body):
            pos = 0
            blocks = []
            while pos < len(body):
                ident_match = _match_ident_at(body, pos)
                if not ident_match:
                    return []
                subtable_name = _normalize_sql_name(ident_match.group(1).strip())
                pos += ident_match.end()
                using_match = re.match(
                    rf"\s+using\s+({ident_with_db})", body[pos:], re.I | re.S
                )
                if not using_match:
                    return []
                using_name = _normalize_sql_name(using_match.group(1).strip())
                pos += using_match.end()
                if pos < len(body) and body[pos:].lstrip().startswith("("):
                    pos += len(body[pos:]) - len(body[pos:].lstrip())
                    parsed_cols = _consume_parenthesized(body, pos)
                    if not parsed_cols:
                        return []
                    pos = parsed_cols[1]
                tags_match = re.match(r"\s+tags\s*", body[pos:], re.I | re.S)
                if not tags_match:
                    return []
                pos += tags_match.end()
                pos += len(body[pos:]) - len(body[pos:].lstrip())
                parsed_tags = _consume_parenthesized(body, pos)
                if not parsed_tags or not parsed_tags[0].strip():
                    return []
                pos = parsed_tags[1]
                blocks.append((subtable_name, using_name))
                pos += len(body[pos:]) - len(body[pos:].lstrip())
            return blocks

        value_expr = r"(?:'[^']*'|`[^`]+`|[+-]?\d+[a-zA-Z]*|[a-zA-Z_][0-9a-zA-Z_]*)"
        create_db_option_patterns = _build_option_patterns(
            [
                rf"vgroups\s+{value_expr}",
                r"precision\s+(?:'?(?:ms|us|ns)'?)",
                rf"replica\s+{value_expr}",
                rf"buffer\s+{value_expr}",
                rf"pages\s+{value_expr}",
                rf"pagesize\s+{value_expr}",
                r"cachemodel\s+(?:'?(?:none|last_row|last_value|both)'?)",
                rf"cachesize\s+{value_expr}",
                rf"cacheshardbits\s+{value_expr}",
                r"comp\s+(?:0|1|2)",
                rf"duration\s+{value_expr}",
                rf"maxrows\s+{value_expr}",
                rf"minrows\s+{value_expr}",
                rf"keep\s+{value_expr}",
                rf"keep_time_offset\s+{value_expr}",
                rf"stt_trigger\s+{value_expr}",
                r"single_stable\s+(?:0|1)",
                rf"table_prefix\s+{value_expr}",
                rf"table_suffix\s+{value_expr}",
                rf"dnodes\s+{value_expr}",
                rf"tsdb_pagesize\s+{value_expr}",
                r"wal_level\s+(?:1|2)",
                rf"wal_fsync_period\s+{value_expr}",
                rf"wal_retention_period\s+{value_expr}",
                rf"wal_retention_size\s+{value_expr}",
                rf"compact_interval\s+{value_expr}",
                rf"compact_time_range\s+{value_expr}",
                rf"compact_time_offset\s+{value_expr}",
                rf"ss_keeplocal\s+{value_expr}",
                rf"ss_chunkpages\s+{value_expr}",
                rf"ss_compact\s+{value_expr}",
            ]
        )
        alter_db_option_patterns = _build_option_patterns(
            [
                r"cachemodel\s+(?:'?(?:none|last_row|last_value|both)'?)",
                rf"cachesize\s+{value_expr}",
                rf"cacheshardbits\s+{value_expr}",
                rf"buffer\s+{value_expr}",
                rf"pages\s+{value_expr}",
                rf"replica\s+{value_expr}",
                rf"stt_trigger\s+{value_expr}",
                rf"wal_level\s+{value_expr}",
                rf"wal_fsync_period\s+{value_expr}",
                rf"keep\s+{value_expr}",
                rf"wal_retention_period\s+{value_expr}",
                rf"wal_retention_size\s+{value_expr}",
                rf"minrows\s+{value_expr}",
                rf"compact_interval\s+{value_expr}",
                rf"compact_time_range\s+{value_expr}",
                rf"compact_time_offset\s+{value_expr}",
            ]
        )
        create_table_option_patterns = _build_option_patterns(
            [
                r"comment\s+'[^']*'",
                rf"sma\s*\(\s*{ident}(?:\s*,\s*{ident})*\s*\)",
                rf"ttl\s+{value_expr}",
            ]
        )
        create_stable_option_patterns = _build_option_patterns(
            [
                r"comment\s+'[^']*'",
                rf"sma\s*\(\s*{ident}(?:\s*,\s*{ident})*\s*\)",
                rf"keep\s+{value_expr}",
                r"virtual\s+(?:0|1)",
            ]
        )

        normal_table_clause_regex = [
            re.compile(rf"^{table_option}(?:\s+{table_option})*$", re.I),
            re.compile(rf"^add\s+column\s+{ident}\s+.+$", re.I),
            re.compile(rf"^drop\s+column\s+{ident}$", re.I),
            re.compile(rf"^modify\s+column\s+{ident}\s+.+$", re.I),
            re.compile(rf"^rename\s+column\s+{ident}\s+{ident}$", re.I),
        ]
        ctable_clause_regex = [
            re.compile(rf"^{table_option}(?:\s+{table_option})*$", re.I),
            re.compile(
                rf"^set\s+tag\s+{ident}\s*=\s*(?:'(?:''|[^'])*'|[^,]+)(?:\s*,\s*{ident}\s*=\s*(?:'(?:''|[^'])*'|[^,]+))*$",
                re.I,
            ),
        ]
        stable_clause_regex = [
            re.compile(rf"^{stable_option}(?:\s+{stable_option})*$", re.I),
            re.compile(rf"^add\s+column\s+{ident}\s+.+$", re.I),
            re.compile(rf"^drop\s+column\s+{ident}$", re.I),
            re.compile(rf"^modify\s+column\s+{ident}\s+.+$", re.I),
            re.compile(rf"^add\s+tag\s+{ident}\s+.+$", re.I),
            re.compile(rf"^drop\s+tag\s+{ident}$", re.I),
            re.compile(rf"^modify\s+tag\s+{ident}\s+.+$", re.I),
            re.compile(rf"^rename\s+tag\s+{ident}\s+{ident}$", re.I),
        ]

        # 禁用/高危语句检查
        check_result = ReviewSet(full_sql=sql)
        line = 1
        critical_ddl_regex = self.config.get("critical_ddl_regex", "")
        p = re.compile(critical_ddl_regex)
        check_result.syntax_type = 2  # TODO 工单类型 0、其他 1、DDL，2、DML

        for statement in sql_list:
            statement = statement.rstrip(";")
            # 禁用语句
            if re.match(r"^select|^show", statement, re.M | re.IGNORECASE):
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="驳回不支持语句",
                    errormessage="仅支持DML和DDL语句，查询语句请使用SQL查询功能！",
                    sql=statement,
                )
            # 高危语句
            elif critical_ddl_regex and p.match(statement.strip().lower()):
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="驳回高危SQL",
                    errormessage="禁止提交匹配" + critical_ddl_regex + "条件的语句！",
                    sql=statement,
                )
            # create语句
            elif re.match(r"^create", statement, re.M | re.IGNORECASE):
                create_db_match = re.match(
                    rf"^create\s+database\s+(if\s+not\s+exists\s+)?({ident})\s*(.*)$",
                    statement,
                    re.M | re.IGNORECASE | re.S,
                )
                create_stable_match = re.match(
                    rf"^create\s+(?:stable|table)\s+(if\s+not\s+exists\s+)?({ident_with_db})\s*\((.+)\)\s+tags\s*\((.+)\)\s*(.*)$",
                    statement,
                    re.M | re.IGNORECASE | re.S,
                )
                create_table_match = re.match(
                    rf"^create\s+table\s+(if\s+not\s+exists\s+)?({ident_with_db})\s*\((.+)\)\s*(.*)$",
                    statement,
                    re.M | re.IGNORECASE | re.S,
                )
                subtable_match = re.match(
                    rf"^create\s+table\s+(if\s+not\s+exists\s+)?(?=\s*{ident_with_db}\s+using)(.+)$",
                    statement,
                    re.M | re.IGNORECASE | re.S,
                )
                csv_subtable_match = re.match(
                    rf"^create\s+table\s+(if\s+not\s+exists\s+)?using\s+({ident_with_db})(?:\s*\((.*?)\))?\s+file\s+'[^']+'\s*$",
                    statement,
                    re.M | re.IGNORECASE | re.S,
                )

                if create_db_match:
                    with_if_not_exists = bool(create_db_match.group(1))
                    db_name_to_create = create_db_match.group(2).strip().strip("`")
                    db_options = create_db_match.group(3).strip()
                    db_check = _workflow_obj_check(
                        obj_name=db_name_to_create, obj_type="database"
                    )
                    if db_check["exists"] and not with_if_not_exists:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="对象已存在",
                            errormessage=f"数据库 {db_name_to_create} 已存在，不允许重复创建！",
                            sql=statement,
                        )
                    elif _is_valid_option_sequence(
                        db_options, create_db_option_patterns
                    ):
                        result = _success_result(statement, line)
                        _mark_database_created(db_name_to_create)
                    else:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="驳回不支持SQL",
                            errormessage="CREATE DATABASE 语法不正确！",
                            sql=statement,
                        )
                elif create_stable_match:
                    with_if_not_exists = bool(create_stable_match.group(1))
                    stable_name = re.sub(
                        r"\s*\.\s*", ".", create_stable_match.group(2).strip()
                    )
                    col_defs = create_stable_match.group(3).strip()
                    tag_defs = create_stable_match.group(4).strip()
                    stable_options = create_stable_match.group(5).strip()
                    stable_check = _workflow_obj_check(
                        db_name=db_name, obj_name=stable_name, obj_type="table"
                    )
                    if stable_check["exists"] and not with_if_not_exists:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="对象已存在",
                            errormessage=f"对象 {stable_name} 已存在，不允许重复创建！",
                            sql=statement,
                        )
                    elif (
                        col_defs
                        and tag_defs
                        and _is_valid_option_sequence(
                            stable_options, create_stable_option_patterns
                        )
                    ):
                        result = _success_result(statement, line)
                        _mark_table_created(stable_name, "stable", db_name)
                    else:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="驳回不支持SQL",
                            errormessage="CREATE STABLE 语法不正确！",
                            sql=statement,
                        )
                elif csv_subtable_match:
                    using_stable_name = _normalize_sql_name(
                        csv_subtable_match.group(2).strip()
                    )
                    using_stable_check = _workflow_obj_check(
                        db_name=db_name, obj_name=using_stable_name, obj_type="table"
                    )
                    if not using_stable_check["exists"]:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="表不存在",
                            errormessage=f"超级表 {using_stable_name} 不存在！",
                            sql=statement,
                        )
                    elif using_stable_check["type"] != "stable":
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="驳回不支持SQL",
                            errormessage=f"USING 对象 {using_stable_name} 不是超级表！",
                            sql=statement,
                        )
                    else:
                        result = _success_result(statement, line)
                elif subtable_match:
                    with_if_not_exists = bool(subtable_match.group(1))
                    subtable_blocks = _parse_subtable_blocks(
                        subtable_match.group(2).strip()
                    )
                    subtable_error = ""
                    if not subtable_blocks:
                        subtable_error = "CREATE TABLE 子表语法不正确！"
                    else:
                        for subtable_name, using_stable_name in subtable_blocks:
                            subtable_check = _workflow_obj_check(
                                db_name=db_name,
                                obj_name=subtable_name,
                                obj_type="table",
                            )
                            using_stable_check = _workflow_obj_check(
                                db_name=db_name,
                                obj_name=using_stable_name,
                                obj_type="table",
                            )
                            if subtable_check["exists"] and not with_if_not_exists:
                                subtable_error = (
                                    f"对象 {subtable_name} 已存在，不允许重复创建！"
                                )
                                break
                            if not subtable_check["exists"]:
                                if not using_stable_check["exists"]:
                                    subtable_error = (
                                        f"超级表 {using_stable_name} 不存在！"
                                    )
                                    break
                                if using_stable_check["type"] != "stable":
                                    subtable_error = (
                                        f"USING 对象 {using_stable_name} 不是超级表！"
                                    )
                                    break
                    if subtable_error:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="驳回不支持SQL",
                            errormessage=subtable_error,
                            sql=statement,
                        )
                    else:
                        result = _success_result(statement, line)
                        for subtable_name, _using_stable_name in subtable_blocks:
                            _mark_table_created(subtable_name, "ctable", db_name)
                elif create_table_match:
                    with_if_not_exists = bool(create_table_match.group(1))
                    table_name = re.sub(
                        r"\s*\.\s*", ".", create_table_match.group(2).strip()
                    )
                    col_defs = create_table_match.group(3).strip()
                    table_options = create_table_match.group(4).strip()
                    table_check = _workflow_obj_check(
                        db_name=db_name, obj_name=table_name, obj_type="table"
                    )
                    if table_check["exists"] and not with_if_not_exists:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="对象已存在",
                            errormessage=f"对象 {table_name} 已存在，不允许重复创建！",
                            sql=statement,
                        )
                    elif col_defs and _is_valid_option_sequence(
                        table_options, create_table_option_patterns
                    ):
                        result = _success_result(statement, line)
                        _mark_table_created(table_name, "table", db_name)
                    else:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="驳回不支持SQL",
                            errormessage="CREATE TABLE 语法不正确！",
                            sql=statement,
                        )
                else:
                    result = ReviewResult(
                        id=line,
                        errlevel=2,
                        stagestatus="驳回不支持SQL",
                        errormessage="CREATE语法不正确！",
                        sql=statement,
                    )
            # alter语句
            elif re.match(r"^alter", statement, re.M | re.IGNORECASE):
                alter_db_match = re.match(
                    rf"^alter\s+database\s+({ident})\s+(.+)$",
                    statement,
                    re.M | re.IGNORECASE | re.S,
                )
                table_match = re.match(
                    rf"^alter\s+table\s+({ident_with_db})\s+(.+)$",
                    statement,
                    re.M | re.IGNORECASE,
                )
                stable_match = re.match(
                    rf"^alter\s+stable\s+({ident_with_db})\s+(.+)$",
                    statement,
                    re.M | re.IGNORECASE,
                )

                if alter_db_match:
                    alter_db_options = alter_db_match.group(2).strip()
                    if _is_valid_option_sequence(
                        alter_db_options, alter_db_option_patterns
                    ):
                        result = ReviewResult(
                            id=line,
                            errlevel=0,
                            stagestatus="Audit completed",
                            errormessage="None",
                            sql=statement,
                            affected_rows=0,
                            execute_time=0,
                        )
                    else:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="驳回不支持SQL",
                            errormessage="ALTER DATABASE 语法不正确！",
                            sql=statement,
                        )
                elif not table_match and not stable_match:
                    result = ReviewResult(
                        id=line,
                        errlevel=2,
                        stagestatus="驳回不支持SQL",
                        errormessage="ALTER语法不正确！",
                        sql=statement,
                    )
                else:
                    is_alter_stable = stable_match is not None
                    alter_match = stable_match if is_alter_stable else table_match
                    table_name = alter_match.group(1)
                    alter_clause = alter_match.group(2).strip()
                    table_check = _workflow_obj_check(
                        db_name=db_name, obj_name=table_name, obj_type="table"
                    )

                    if not table_check["exists"]:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="表不存在",
                            errormessage=f"表 {table_name} 不存在！",
                            sql=statement,
                        )
                    else:
                        table_type = table_check["type"]
                        is_clause_valid = False
                        error_msg = "ALTER语法不符合对象类型约束！"

                        if table_type == "stable":
                            if not is_alter_stable:
                                error_msg = "超级表仅支持 ALTER STABLE 语法！"
                            else:
                                is_clause_valid = any(
                                    r.match(alter_clause) for r in stable_clause_regex
                                )
                                if not is_clause_valid:
                                    error_msg = "ALTER STABLE 语法不正确！"
                        elif table_type == "table":
                            if is_alter_stable:
                                error_msg = "普通表不支持 ALTER STABLE 语法！"
                            else:
                                is_clause_valid = any(
                                    r.match(alter_clause)
                                    for r in normal_table_clause_regex
                                )
                                if not is_clause_valid:
                                    error_msg = "普通表 ALTER TABLE 语法不正确！"
                        elif table_type == "ctable":
                            if is_alter_stable:
                                error_msg = "子表不支持 ALTER STABLE 语法！"
                            else:
                                is_clause_valid = any(
                                    r.match(alter_clause) for r in ctable_clause_regex
                                )
                                if not is_clause_valid:
                                    error_msg = "子表 ALTER TABLE 语法不正确！"

                        if is_clause_valid:
                            result = ReviewResult(
                                id=line,
                                errlevel=0,
                                stagestatus="Audit completed",
                                errormessage="None",
                                sql=statement,
                                affected_rows=0,
                                execute_time=0,
                            )
                        else:
                            result = ReviewResult(
                                id=line,
                                errlevel=2,
                                stagestatus="驳回不支持SQL",
                                errormessage=error_msg,
                                sql=statement,
                            )
            # insert语句
            elif re.match(r"^insert", statement, re.M | re.IGNORECASE):
                insert_sql = statement.strip()
                insert_body_match = re.match(
                    r"^insert\s+into\s+(.+)$", insert_sql, re.I | re.S
                )
                insert_ok = False
                insert_error = "INSERT语法不正确！"
                if insert_body_match:
                    insert_body = insert_body_match.group(1).strip()
                    super_subquery_match = re.match(
                        rf"^({ident_with_db})\s*\(\s*tbname\s*,[\w\W]+\)\s+select\s+[\w\W]+$",
                        insert_body,
                        re.I | re.S,
                    )
                    normal_subquery_match = re.match(
                        rf"^({ident_with_db})(?:\s*\(\s*([^)]*)\s*\))?\s+select\s+[\w\W]+$",
                        insert_body,
                        re.I | re.S,
                    )

                    if super_subquery_match:
                        stb_name = re.sub(
                            r"\s*\.\s*", ".", super_subquery_match.group(1).strip()
                        )
                        stb_check = _workflow_obj_check(
                            db_name=db_name, obj_name=stb_name, obj_type="table"
                        )
                        if not stb_check["exists"]:
                            insert_error = f"超级表 {stb_name} 不存在！"
                        elif stb_check["type"] != "stable":
                            insert_error = (
                                f"{stb_name} 不是超级表，不能使用 tbname 子查询语法！"
                            )
                        else:
                            insert_ok = True
                    elif normal_subquery_match:
                        tb_name = re.sub(
                            r"\s*\.\s*", ".", normal_subquery_match.group(1).strip()
                        )
                        insert_columns = _parse_ident_list(
                            normal_subquery_match.group(2) or ""
                        )
                        tb_check = _workflow_obj_check(
                            db_name=db_name, obj_name=tb_name, obj_type="table"
                        )
                        if not tb_check["exists"]:
                            insert_error = f"表 {tb_name} 不存在！"
                        elif (
                            tb_check["type"] == "stable"
                            and "tbname" not in insert_columns
                        ):
                            insert_error = f"{tb_name} 为超级表，不能直接写入，请指定 tbname 字段！"
                        else:
                            insert_ok = True
                    else:
                        blocks = _parse_insert_blocks(insert_body)
                        if blocks:
                            insert_ok = True
                            for tb_name, using_name, has_tbname_col in blocks:
                                tb_check = _workflow_obj_check(
                                    db_name=db_name, obj_name=tb_name, obj_type="table"
                                )
                                if using_name:
                                    using_check = _workflow_obj_check(
                                        db_name=db_name,
                                        obj_name=using_name,
                                        obj_type="table",
                                    )
                                    if not using_check["exists"]:
                                        insert_ok = False
                                        insert_error = f"超级表 {using_name} 不存在！"
                                        break
                                    if using_check["type"] != "stable":
                                        insert_ok = False
                                        insert_error = (
                                            f"USING 对象 {using_name} 不是超级表！"
                                        )
                                        break
                                    if (
                                        tb_check["exists"]
                                        and tb_check["type"] == "stable"
                                    ):
                                        insert_ok = False
                                        insert_error = f"{tb_name} 为超级表，不能使用 USING 语法写入！"
                                        break
                                else:
                                    if not tb_check["exists"]:
                                        insert_ok = False
                                        insert_error = f"表 {tb_name} 不存在！"
                                        break
                                    if (
                                        tb_check["type"] == "stable"
                                        and not has_tbname_col
                                    ):
                                        insert_ok = False
                                        insert_error = f"{tb_name} 为超级表，不能直接写入，请指定 tbname 字段！"
                                        break
                        else:
                            insert_error = "INSERT语法不正确！"

                if insert_ok:
                    result = ReviewResult(
                        id=line,
                        errlevel=0,
                        stagestatus="Audit completed",
                        errormessage="None",
                        sql=statement,
                        affected_rows=0,
                        execute_time=0,
                    )
                else:
                    result = ReviewResult(
                        id=line,
                        errlevel=2,
                        stagestatus="驳回不支持SQL",
                        errormessage=insert_error,
                        sql=statement,
                    )
            # delete语句
            elif re.match(r"^delete", statement, re.M | re.IGNORECASE):
                delete_match = re.match(
                    rf"^delete\s+from\s+({ident_with_db})(?:\s+where\s+[\w\W]+)?$",
                    statement,
                    re.I | re.S,
                )
                if not delete_match:
                    result = ReviewResult(
                        id=line,
                        errlevel=2,
                        stagestatus="驳回不支持SQL",
                        errormessage="DELETE语法不正确！",
                        sql=statement,
                    )
                else:
                    tb_name = re.sub(r"\s*\.\s*", ".", delete_match.group(1).strip())
                    tb_check = _workflow_obj_check(
                        db_name=db_name, obj_name=tb_name, obj_type="table"
                    )
                    if not tb_check["exists"]:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="表不存在",
                            errormessage=f"表 {tb_name} 不存在！",
                            sql=statement,
                        )
                    else:
                        result = ReviewResult(
                            id=line,
                            errlevel=0,
                            stagestatus="Audit completed",
                            errormessage="None",
                            sql=statement,
                            affected_rows=0,
                            execute_time=0,
                        )
            # drop语句
            elif re.match(r"^drop", statement, re.M | re.IGNORECASE):
                drop_db_match = re.match(
                    rf"^drop\s+database\s+(if\s+exists\s+)?({ident})$",
                    statement,
                    re.I,
                )
                drop_stable_match = re.match(
                    rf"^drop\s+stable\s+(if\s+exists\s+)?({ident_with_db})$",
                    statement,
                    re.I,
                )
                drop_table_match = re.match(
                    r"^drop\s+table\s+(.+)$",
                    statement,
                    re.I | re.S,
                )

                if drop_db_match:
                    with_if_exists = bool(drop_db_match.group(1))
                    db_to_drop = drop_db_match.group(2).strip().strip("`")
                    db_check = _workflow_obj_check(
                        obj_name=db_to_drop, obj_type="database"
                    )
                    if not db_check["exists"] and not with_if_exists:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="对象不存在",
                            errormessage=f"数据库 {db_to_drop} 不存在！",
                            sql=statement,
                        )
                    else:
                        result = ReviewResult(
                            id=line,
                            errlevel=0,
                            stagestatus="Audit completed",
                            errormessage="None",
                            sql=statement,
                            affected_rows=0,
                            execute_time=0,
                        )
                elif drop_stable_match:
                    with_if_exists = bool(drop_stable_match.group(1))
                    stable_name = re.sub(
                        r"\s*\.\s*", ".", drop_stable_match.group(2).strip()
                    )
                    stable_check = _workflow_obj_check(
                        db_name=db_name, obj_name=stable_name, obj_type="table"
                    )
                    if not stable_check["exists"] and not with_if_exists:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="对象不存在",
                            errormessage=f"超级表 {stable_name} 不存在！",
                            sql=statement,
                        )
                    elif stable_check["exists"] and stable_check["type"] != "stable":
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="驳回不支持SQL",
                            errormessage=f"对象 {stable_name} 不是超级表！",
                            sql=statement,
                        )
                    else:
                        result = ReviewResult(
                            id=line,
                            errlevel=0,
                            stagestatus="Audit completed",
                            errormessage="None",
                            sql=statement,
                            affected_rows=0,
                            execute_time=0,
                        )
                elif drop_table_match:
                    raw_list = drop_table_match.group(1).strip()
                    items = [i.strip() for i in raw_list.split(",") if i.strip()]
                    parse_ok = True
                    drop_error = "DROP TABLE 语法不正确！"
                    for item in items:
                        item_match = re.match(
                            rf"^(if\s+exists\s+)?({ident_with_db})$", item, re.I
                        )
                        if not item_match:
                            parse_ok = False
                            break
                        with_if_exists = bool(item_match.group(1))
                        table_name = re.sub(
                            r"\s*\.\s*", ".", item_match.group(2).strip()
                        )
                        table_check = _workflow_obj_check(
                            db_name=db_name, obj_name=table_name, obj_type="table"
                        )
                        if not table_check["exists"] and not with_if_exists:
                            parse_ok = False
                            drop_error = f"表 {table_name} 不存在！"
                            break
                        if table_check["exists"] and table_check["type"] == "stable":
                            parse_ok = False
                            drop_error = (
                                f"对象 {table_name} 为超级表，请使用 DROP STABLE！"
                            )
                            break
                    if parse_ok:
                        result = ReviewResult(
                            id=line,
                            errlevel=0,
                            stagestatus="Audit completed",
                            errormessage="None",
                            sql=statement,
                            affected_rows=0,
                            execute_time=0,
                        )
                    else:
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="驳回不支持SQL",
                            errormessage=drop_error,
                            sql=statement,
                        )
                else:
                    result = ReviewResult(
                        id=line,
                        errlevel=2,
                        stagestatus="驳回不支持SQL",
                        errormessage="DROP语法不正确！",
                        sql=statement,
                    )
            # 其他语句直接返回不支持
            else:
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="驳回不支持SQL",
                    errormessage="不支持该语法！",
                    sql=statement,
                )

            # 没有找出DDL语句的才继续执行此判断
            if check_result.syntax_type == 2:
                if get_syntax_type(statement, parser=False, db_type="mysql") == "DDL":
                    check_result.syntax_type = 1
            check_result.rows += [result]
            line += 1
        # 统计警告和错误数量
        for r in check_result.rows:
            if r.errlevel == 1:
                check_result.warning_count += 1
            if r.errlevel == 2:
                check_result.error_count += 1
        return check_result

    def execute_workflow(self, workflow):
        """执行上线单，返回Review set"""
        sql = workflow.sqlworkflowcontent.sql_content
        execute_result = ReviewSet(full_sql=sql)
        sqls = sqlparse.format(sql, strip_comments=True)
        sql_list = sqlparse.split(sqls)

        line = 1
        for statement in sql_list:
            with FuncTimer() as t:
                result = self.execute(
                    db_name=workflow.db_name, sql=statement, close_conn=True
                )
            if not result.error:
                execute_result.rows.append(
                    ReviewResult(
                        id=line,
                        errlevel=0,
                        stagestatus="Execute Successfully",
                        errormessage="None",
                        sql=statement,
                        affected_rows=result.affected_rows,
                        execute_time=t.cost,
                    )
                )
                line += 1
            else:
                # 追加当前报错语句信息到执行结果中
                execute_result.error = result.error
                execute_result.rows.append(
                    ReviewResult(
                        id=line,
                        errlevel=2,
                        stagestatus="Execute Failed",
                        errormessage=f"异常信息：{result.error}",
                        sql=statement,
                        affected_rows=result.affected_rows,
                        execute_time=t.cost,
                    )
                )
                line += 1
                # 报错语句后面的语句标记为审核通过、未执行，追加到执行结果中
                for statement in sql_list[line - 1 :]:
                    execute_result.rows.append(
                        ReviewResult(
                            id=line,
                            errlevel=0,
                            stagestatus="Audit completed",
                            errormessage=f"前序语句失败, 未执行",
                            sql=statement,
                            affected_rows=0,
                            execute_time=0,
                        )
                    )
                    line += 1
                break
        return execute_result

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
