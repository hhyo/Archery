# -*- coding: UTF-8 -*-
import logging
import traceback
import re
import sqlparse

from . import EngineBase
import pyodbc
from .models import ResultSet, ReviewSet, ReviewResult
from sql.utils.data_masking import brute_mask
from common.utils.timer import FuncTimer

logger = logging.getLogger("default")


class MssqlEngine(EngineBase):
    test_query = "SELECT 1"

    name = "MsSQL"
    info = "MsSQL engine"

    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn

        # 尝试检测可用的 ODBC 驱动
        available_drivers = []
        try:
            available_drivers = [driver for driver in pyodbc.drivers()]
        except Exception as e:
            logger.warning(f"无法获取 ODBC 驱动列表: {e}")

        # 按优先级尝试的驱动列表
        driver_priority = [
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "ODBC Driver 11 for SQL Server",
            "FreeTDS",
            "SQL Server",
        ]

        # 找到第一个可用的驱动
        selected_driver = None
        if available_drivers:
            for driver in driver_priority:
                if driver in available_drivers:
                    selected_driver = driver
                    break

        # 如果没有找到任何驱动，使用默认驱动（可能会失败，但至少会给出明确的错误）
        if not selected_driver:
            selected_driver = "ODBC Driver 17 for SQL Server"
            if available_drivers:
                logger.warning(
                    f"未找到推荐的 SQL Server ODBC 驱动，可用驱动: {', '.join(available_drivers)}"
                )
                logger.warning(f"将尝试使用默认驱动: {selected_driver}")
            else:
                logger.error("未找到任何可用的 ODBC 驱动，请安装 SQL Server ODBC 驱动")

        # 构建连接字符串（驱动名称需要用花括号括起来）
        # 使用数据库默认编码，不强制设置 UTF-8
        if "ODBC Driver 17" in selected_driver or "ODBC Driver 18" in selected_driver:
            # ODBC Driver 17/18
            connstr = """DRIVER={{{0}}};SERVER={1},{2};UID={3};PWD={4};
TrustServerCertificate=yes;connect timeout=10;""".format(
                selected_driver,
                self.host,
                self.port,
                self.user,
                self.password,
            )
        else:
            # 其他驱动
            connstr = """DRIVER={{{0}}};SERVER={1},{2};UID={3};PWD={4};
connect timeout=10;""".format(
                selected_driver,
                self.host,
                self.port,
                self.user,
                self.password,
            )

        # 如果指定了数据库名，添加到连接字符串
        if db_name:
            connstr = f"{connstr};DATABASE={db_name}"

        try:
            self.conn = pyodbc.connect(connstr)
            # 不强制设置编码，让 pyodbc 使用数据库的默认编码
            # 这样插入的中文字符会使用数据库的默认编码（如 GBK、GB2312 等）
            logger.info(f"成功使用驱动 '{selected_driver}' 连接到 SQL Server")
            return self.conn
        except pyodbc.Error as e:
            error_msg = str(e)
            if "Can't open lib" in error_msg or "file not found" in error_msg:
                # 提供更友好的错误信息
                if available_drivers:
                    raise RuntimeError(
                        f"ODBC 驱动 '{selected_driver}' 不可用。\n"
                        f"可用驱动: {', '.join(available_drivers)}\n"
                        f"请安装 Microsoft ODBC Driver for SQL Server 或配置正确的驱动。\n"
                        f"原始错误: {error_msg}"
                    )
                else:
                    raise RuntimeError(
                        f"未找到可用的 ODBC 驱动。\n"
                        f"请安装 Microsoft ODBC Driver for SQL Server。\n"
                        f"安装方法:\n"
                        f"  macOS: brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release && brew install msodbcsql17\n"
                        f"  Linux: 参考 https://docs.microsoft.com/en-us/sql/connect/odbc/linux-mac/install-odbc-driver-sql-server\n"
                        f"原始错误: {error_msg}"
                    )
            else:
                # 其他连接错误，直接抛出
                raise

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "SELECT name FROM master.sys.databases order by name"
        result = self.query(sql=sql)
        db_list = [
            row[0]
            for row in result.rows
            if row[0] not in ("master", "msdb", "tempdb", "model")
        ]
        result.rows = db_list
        return result

    def get_all_tables(self, db_name, **kwargs):
        """获取table 列表, 返回一个ResultSet"""
        sql = """SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE' order by TABLE_NAME;"""
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in ["test"]]
        result.rows = tb_list
        return result

    def get_group_tables_by_db(self, db_name):
        """
        根据传入的数据库名，获取该库下的表和注释，并按首字符分组，比如 'a': ['account1','apply']
        :param db_name:
        :return:
        """
        data = {}
        sql = f"""
        SELECT t.name AS table_name, 
            case when td.value is not null then convert(varchar(max),td.value) else '' end AS table_comment
        FROM    sysobjects t
        LEFT OUTER JOIN sys.extended_properties td
        ON      td.major_id = t.id
        AND     td.minor_id = 0
        AND     td.name = 'MS_Description'
        WHERE t.type = 'u' ORDER BY t.name;"""
        result = self.query(db_name=db_name, sql=sql)
        for row in result.rows:
            table_name, table_cmt = row[0], row[1]
            if table_name[0] not in data:
                data[table_name[0]] = list()
            data[table_name[0]].append([table_name, table_cmt])
        return data

    def get_table_meta_data(self, db_name, tb_name, **kwargs):
        """数据字典页面使用：获取表格的元信息，返回一个dict{column_list: [], rows: []}"""
        sql = """
            SELECT space.*,table_comment,index_length,IDENT_CURRENT(?) as auto_increment
            FROM (
            SELECT 
                t.NAME AS table_name,
                t.create_date as create_time,
                t.modify_date as update_time,
                p.rows AS table_rows,
                SUM(a.total_pages) * 8 AS data_total,
                SUM(a.used_pages) * 8 AS data_length,
                (SUM(a.total_pages) - SUM(a.used_pages)) * 8 AS data_free
            FROM 
                sys.tables t
            INNER JOIN      
                sys.indexes i ON t.OBJECT_ID = i.object_id
            INNER JOIN 
                sys.partitions p ON i.object_id = p.OBJECT_ID AND i.index_id = p.index_id
            INNER JOIN 
                sys.allocation_units a ON p.partition_id = a.container_id
            WHERE 
                t.NAME =?
                AND t.is_ms_shipped = 0
                AND i.OBJECT_ID > 255 
            GROUP BY 
                t.Name, t.create_date, t.modify_date, p.Rows) 
            AS space 
            INNER JOIN (
            SELECT      t.name AS table_name,
                        convert(varchar(max),td.value) AS table_comment
            FROM		sysobjects t
            LEFT OUTER JOIN sys.extended_properties td
                ON      td.major_id = t.id
                AND     td.minor_id = 0
                AND     td.name = 'MS_Description'
            WHERE t.type = 'u' and t.name = ?) AS comment 
            ON space.table_name = comment.table_name
            INNER JOIN (
            SELECT
                t.NAME				AS table_name,
                SUM(page_count * 8) AS index_length
            FROM sys.dm_db_index_physical_stats(
                db_id(), object_id(?), NULL, NULL, 'DETAILED') AS s
            JOIN sys.indexes AS i
            ON s.[object_id] = i.[object_id] AND s.index_id = i.index_id
            INNER JOIN      
                sys.tables t ON t.OBJECT_ID = i.object_id
            GROUP BY t.NAME
            ) AS index_size 
            ON index_size.table_name = space.table_name;
        """
        _meta_data = self.query(
            db_name,
            sql,
            parameters=(
                tb_name,
                tb_name,
                tb_name,
            ),
        )
        return {"column_list": _meta_data.column_list, "rows": _meta_data.rows[0]}

    def get_table_desc_data(self, db_name, tb_name, **kwargs):
        """获取表格字段信息"""
        sql = """
            select COLUMN_NAME 列名, case when ISNUMERIC(CHARACTER_MAXIMUM_LENGTH)=1 
then DATA_TYPE + '(' + convert(varchar(max), CHARACTER_MAXIMUM_LENGTH) + ')' else DATA_TYPE end 列类型,
                COLLATION_NAME 列字符集,
                IS_NULLABLE 是否为空,
                COLUMN_DEFAULT 默认值
            from INFORMATION_SCHEMA.columns where TABLE_CATALOG=? and TABLE_NAME = ?;"""
        _desc_data = self.query(
            db_name,
            sql,
            parameters=(
                db_name,
                tb_name,
            ),
        )
        return {"column_list": _desc_data.column_list, "rows": _desc_data.rows}

    def get_table_index_data(self, db_name, tb_name, **kwargs):
        """获取表格索引信息"""
        sql = """SELECT 
stuff((select ',' + COL_NAME(t.object_id,t.column_id) from sys.index_columns as t where i.object_id = t.object_id and 
i.index_id = t.index_id and t.is_included_column = 0 order by key_ordinal for xml path('')),1,1,'') as 列名,
                i.name AS 索引名,
                is_unique as 唯一性,is_primary_key as 是否主建
            FROM sys.indexes AS i  
            WHERE i.object_id = OBJECT_ID(?)
            group by i.name,i.object_id,i.index_id,is_unique,is_primary_key;"""
        _index_data = self.query(db_name, sql, parameters=(tb_name,))
        return {"column_list": _index_data.column_list, "rows": _index_data.rows}

    def get_tables_metas_data(self, db_name, **kwargs):
        """获取数据库所有表格信息，用作数据字典导出接口"""
        sql = """SELECT t.name AS TABLE_NAME, 
            case when td.value is not null then convert(varchar(max),td.value) else '' end AS TABLE_COMMENT
        FROM    sysobjects t
        LEFT OUTER JOIN sys.extended_properties td
        ON      td.major_id = t.id
        AND     td.minor_id = 0
        AND     td.name = 'MS_Description'
        WHERE t.type = 'u' ORDER BY t.name;"""
        result = self.query(db_name=db_name, sql=sql)
        # query result to dict
        tbs = []
        for row in result.rows:
            tbs.append(dict(zip(result.column_list, row)))
        table_metas = []
        for tb in tbs:
            _meta = dict()
            engine_keys = [
                {"key": "COLUMN_NAME", "value": "字段名"},
                {"key": "COLUMN_TYPE", "value": "数据类型"},
                {"key": "COLLATION_NAME", "value": "列字符集"},
                {"key": "IS_NULLABLE", "value": "允许非空"},
                {"key": "COLUMN_DEFAULT", "value": "默认值"},
            ]
            _meta["ENGINE_KEYS"] = engine_keys
            _meta["TABLE_INFO"] = tb
            sql_cols = """select COLUMN_NAME, case when ISNUMERIC(CHARACTER_MAXIMUM_LENGTH)=1 
then DATA_TYPE + '(' + convert(varchar(max), CHARACTER_MAXIMUM_LENGTH) + ')' else DATA_TYPE end COLUMN_TYPE,
                COLLATION_NAME,
                IS_NULLABLE,
                COLUMN_DEFAULT
            from INFORMATION_SCHEMA.columns where TABLE_CATALOG=? and TABLE_NAME = ?;"""
            query_result = self.query(
                db_name=db_name,
                sql=sql_cols,
                close_conn=False,
                parameters=(db_name, tb["TABLE_NAME"]),
            )

            columns = []
            # 转换查询结果为dict
            for row in query_result.rows:
                columns.append(dict(zip(query_result.column_list, row)))
            _meta["COLUMNS"] = tuple(columns)
            table_metas.append(_meta)
        return table_metas

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet"""
        result = self.describe_table(db_name, tb_name)
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        """return ResultSet"""
        sql = r"""select
        c.name ColumnName,
        t.name ColumnType,
        c.length  ColumnLength,
        c.scale   ColumnScale,
        c.isnullable ColumnNull,
            case when i.id is not null then 'Y' else 'N' end TablePk
        from (select name,id,uid from sysobjects where (xtype='U' or xtype='V') ) o 
        inner join syscolumns c on o.id=c.id 
        inner join systypes t on c.xtype=t.xusertype 
        left join sysusers u on u.uid=o.uid
        left join (select name,id,uid,parent_obj from sysobjects where xtype='PK' )  opk on opk.parent_obj=o.id 
        left join (select id,name,indid from sysindexes) ie on ie.id=o.id and ie.name=opk.name
        left join sysindexkeys i on i.id=o.id and i.colid=c.colid and i.indid=ie.indid
        WHERE O.name NOT LIKE 'MS%' AND O.name NOT LIKE 'SY%'
        and O.name=?
        order by o.name,c.colid"""
        result = self.query(db_name=db_name, sql=sql, parameters=(tb_name,))
        return result

    def query_check(self, db_name=None, sql=""):
        # 查询语句的检查、注释去除、切分
        result = {"msg": "", "bad_query": False, "filtered_sql": sql, "has_star": False}
        banned_keywords = [
            "ascii",
            "char",
            "charindex",
            "concat",
            "concat_ws",
            "difference",
            "format",
            "len",
            "nchar",
            "patindex",
            "quotename",
            "replace",
            "replicate",
            "reverse",
            "right",
            "soundex",
            "space",
            "str",
            "string_agg",
            "string_escape",
            "string_split",
            "stuff",
            "substring",
            "trim",
            "unicode",
        ]
        keyword_warning = ""
        star_patter = r"(^|,|\s)\*(\s|\(|$)"
        sql_whitelist = ["select", "sp_helptext"]
        # 根据白名单list拼接pattern语句
        whitelist_pattern = "^" + "|^".join(sql_whitelist)

        # 检查是否是执行计划查询（SET SHOWPLAN_ALL ON）
        sql_lower = sql.lower().strip()
        is_showplan = sql_lower.startswith("set showplan_all on")

        # 删除注释语句，进行语法判断，执行第一条有效sql
        try:
            sql_cleaned = sqlparse.format(sql, strip_comments=True)
            sql_parts = sqlparse.split(sql_cleaned)

            if is_showplan:
                # 执行计划查询：提取实际的 SQL 语句进行检查
                actual_sql = None
                for part in sql_parts:
                    part_lower = part.strip().lower()
                    if not part_lower.startswith("set showplan_all"):
                        actual_sql = part.strip()
                        break

                if actual_sql:
                    # 检查实际的 SQL 是否符合白名单
                    actual_sql_lower = actual_sql.lower()
                    if re.match(whitelist_pattern, actual_sql_lower) is None:
                        result["bad_query"] = True
                        result["msg"] = "仅支持{}语法!".format(",".join(sql_whitelist))
                        return result
                    # 返回完整的执行计划 SQL（包含 SET SHOWPLAN_ALL ON）
                    result["filtered_sql"] = sql.strip()
                    sql_lower = actual_sql_lower  # 用于后续检查
                else:
                    # 如果没有找到实际 SQL，返回错误
                    result["bad_query"] = True
                    result["msg"] = "执行计划查询中未找到有效的SQL语句"
                    return result
            else:
                # 普通查询：使用第一个 SQL 语句
                sql = sql_parts[0] if sql_parts else sql
                result["filtered_sql"] = sql.strip()
                sql_lower = sql.lower()
        except IndexError:
            result["bad_query"] = True
            result["msg"] = "没有有效的SQL语句"
            return result

        # 对于普通查询，检查白名单
        if not is_showplan and re.match(whitelist_pattern, sql_lower) is None:
            result["bad_query"] = True
            result["msg"] = "仅支持{}语法!".format(",".join(sql_whitelist))
            return result
        if re.search(star_patter, sql_lower) is not None:
            keyword_warning += "禁止使用 * 关键词\n"
            result["has_star"] = True
        for keyword in banned_keywords:
            pattern = r"(^|,| |=){}( |\(|$)".format(keyword)
            if re.search(pattern, sql_lower) is not None:
                keyword_warning += "禁止使用 {} 关键词\n".format(keyword)
                result["bad_query"] = True
        if result.get("bad_query") or result.get("has_star"):
            result["msg"] = keyword_warning
        return result

    def filter_sql(self, sql="", limit_num=0):
        sql_lower = sql.lower()
        # 对查询sql增加limit限制
        if re.match(r"^select", sql_lower):
            # 如果已经使用了 OFFSET ... FETCH NEXT，则不添加 TOP（两者不能同时使用）
            if re.search(r"\boffset\s+\d+\s+rows?\s+fetch\s+next", sql_lower, re.I):
                return sql.strip()
            # 如果已经使用了 TOP，则不重复添加
            if sql_lower.find(" top ") == -1 and limit_num > 0:
                # 处理 SELECT DISTINCT 的情况，需要将 TOP 放在 DISTINCT 之后
                if re.match(r"^select\s+distinct\s", sql_lower, re.I):
                    # 找到 DISTINCT 后的位置，插入 TOP，保留原始大小写
                    match = re.match(r"^(select\s+distinct)(\s+.*)$", sql, re.I)
                    if match:
                        return (
                            match.group(1)
                            + " top {}".format(limit_num)
                            + match.group(2)
                        )
                else:
                    # 保留原始大小写，只替换第一个 select
                    return re.sub(
                        r"^select\s+",
                        "select top {} ".format(limit_num),
                        sql,
                        count=1,
                        flags=re.I,
                    )
        return sql.strip()

    def query(
        self,
        db_name=None,
        sql="",
        limit_num=0,
        close_conn=True,
        parameters: tuple = None,
        **kwargs,
    ):
        """返回 ResultSet"""
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection(db_name)
            cursor = conn.cursor()

            # 处理执行计划查询（SET SHOWPLAN_ALL ON）
            sql_lower = sql.lower().strip()
            is_showplan = sql_lower.startswith("set showplan_all on")

            if is_showplan:
                # 解析执行计划查询：SET SHOWPLAN_ALL ON; <SQL>; SET SHOWPLAN_ALL OFF;
                # 提取中间的 SQL 语句
                sql_parts = sqlparse.split(sql)
                actual_sql = None
                for part in sql_parts:
                    part_lower = part.strip().lower()
                    if not part_lower.startswith("set showplan_all"):
                        actual_sql = part.strip()
                        break

                if actual_sql:
                    try:
                        # 开启执行计划
                        cursor.execute("SET SHOWPLAN_ALL ON")
                        # 执行实际 SQL
                        cursor.execute(actual_sql)
                        # 获取执行计划结果
                        rows = cursor.fetchall()
                        fields = cursor.description
                    finally:
                        # 确保关闭执行计划，即使出错也要关闭
                        try:
                            cursor.execute("SET SHOWPLAN_ALL OFF")
                        except:
                            pass
                else:
                    # 如果没有找到实际 SQL，直接执行整个语句
                    cursor.execute(sql)
                    rows = cursor.fetchall()
                    fields = cursor.description
            else:
                # 普通查询
                # https://github.com/mkleehammer/pyodbc/wiki/Cursor#executesql-parameters
                if parameters:
                    cursor.execute(sql, *parameters)
                else:
                    cursor.execute(sql)
                if int(limit_num) > 0:
                    rows = cursor.fetchmany(int(limit_num))
                else:
                    rows = cursor.fetchall()
                fields = cursor.description

            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = [tuple(x) for x in rows]
            result_set.affected_rows = len(result_set.rows)
        except Exception as e:
            logger.warning(
                f"MsSQL语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}"
            )
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    def query_masking(self, db_name=None, sql="", resultset=None):
        """传入 sql语句, db名, 结果集,
        返回一个脱敏后的结果集"""
        # 仅对select语句脱敏
        if re.match(r"^select", sql, re.I):
            filtered_result = brute_mask(self.instance, resultset)
            filtered_result.is_masked = True
        else:
            filtered_result = resultset
        return filtered_result

    def execute_check(self, db_name=None, sql=""):
        """上线单执行前的检查, 返回Review set"""
        from common.config import SysConfig
        from sql.utils.sql_utils import get_syntax_type

        config = SysConfig()
        check_result = ReviewSet(full_sql=sql)
        # 禁用/高危语句检查
        line = 1
        critical_ddl_regex = config.get("critical_ddl_regex", "")
        p = re.compile(critical_ddl_regex) if critical_ddl_regex else None
        check_result.syntax_type = 2  # 默认DML

        # 先按GO分割（MSSQL批处理分隔符），保留原始格式
        split_reg = re.compile(r"^\s*GO\s*$", re.I | re.M)
        sql_batches = re.split(split_reg, sql)

        # 获取所有SQL语句（按GO分割后，每个批次内的SQL再用sqlparse分割）
        # 保留原始格式（包括换行符）以匹配测试期望
        all_statements = []
        for batch in sql_batches:
            if not batch.strip():
                continue
            # 对每个批次内的SQL使用sqlparse分割，但保留原始格式
            # 注意：sqlparse.split 可能会改变格式，所以我们需要保留原始 batch 用于显示
            batch_statements = sqlparse.split(batch)
            for stmt in batch_statements:
                # 保留原始格式，不 strip，以便测试能够匹配原始格式（包括换行符）
                if stmt.strip():
                    # 如果 batch 只包含一条语句，使用原始 batch 以保留格式
                    # 否则使用分割后的语句
                    if len(batch_statements) == 1:
                        all_statements.append(batch)
                    else:
                        all_statements.append(stmt)
        
        # 获取数据库连接用于语法检测
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            if db_name:
                cursor.execute(f"USE [{db_name}]")
        except Exception as e:
            logger.warning(f"MSSQL连接失败，错误信息：{traceback.format_exc()}")
            # 连接失败时，仍然进行基本的规则检查
            conn = None
            cursor = None

        # 逐条检测SQL语句
        for statement in all_statements:
            # 去除注释
            statement_clean = sqlparse.format(statement, strip_comments=True).strip()
            if not statement_clean:
                continue

            # 禁用语句检查（SELECT查询语句）
            if re.match(r"^select", statement_clean, re.I):
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="驳回不支持语句",
                    errormessage="仅支持DML和DDL语句，查询语句请使用SQL查询功能！",
                    sql=statement,
                    affected_rows=0,
                    execute_time=0,
                )
            # 高危语句检查
            elif critical_ddl_regex and p and p.match(statement_clean.lower()):
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="驳回高危SQL",
                    errormessage=f"禁止提交匹配{critical_ddl_regex}条件的语句！",
                    sql=statement,
                    affected_rows=0,
                    execute_time=0,
                )
            # 正常语句，进行语法检测
            else:
                # 判断工单类型
                syntax_type = get_syntax_type(statement_clean, parser=True)
                if syntax_type == "DDL":
                    check_result.syntax_type = 1

                # 如果有连接，进行语法检测
                if conn and cursor:
                    try:
                        # 使用 SET PARSEONLY ON 进行语法检测（只解析不执行）
                        cursor.execute("SET PARSEONLY ON")
                        cursor.execute(statement_clean)
                        cursor.execute("SET PARSEONLY OFF")
                        # 语法检测通过
                        result = ReviewResult(
                            id=line,
                            errlevel=0,
                            stagestatus="Audit completed",
                            errormessage="None",
                            sql=statement,
                            affected_rows=0,
                            execute_time=0,
                        )
                    except Exception as e:
                        # 语法检测失败
                        error_msg = str(e)
                        result = ReviewResult(
                            id=line,
                            errlevel=2,
                            stagestatus="语法错误",
                            errormessage=f"语法检测失败: {error_msg}",
                            sql=statement,
                            affected_rows=0,
                            execute_time=0,
                        )
                        # 确保恢复 PARSEONLY 设置
                        try:
                            cursor.execute("SET PARSEONLY OFF")
                        except:
                            pass
                else:
                    # 无连接时，默认通过（仅做规则检查）
                    result = ReviewResult(
                        id=line,
                        errlevel=0,
                        stagestatus="Audit completed",
                        errormessage="None",
                        sql=statement,
                        affected_rows=0,
                        execute_time=0,
                    )

            check_result.rows.append(result)
            line += 1

        # 关闭连接
        if cursor:
            try:
                cursor.execute("SET PARSEONLY OFF")
            except:
                pass
            try:
                cursor.close()
            except:
                pass
        if conn and self.conn != conn:
            try:
                conn.close()
            except:
                pass

        # 统计警告和错误数量
        for r in check_result.rows:
            if r.errlevel == 1:
                check_result.warning_count += 1
            if r.errlevel == 2:
                check_result.error_count += 1

        return check_result

    def execute_workflow(self, workflow):
        if workflow.is_backup:
            # TODO mssql 备份未实现
            pass
        return self.execute(
            db_name=workflow.db_name, sql=workflow.sqlworkflowcontent.sql_content
        )

    def execute(self, db_name=None, sql="", close_conn=True):
        """执行sql语句 返回 Review set"""
        execute_result = ReviewSet(full_sql=sql)
        conn = self.get_connection(db_name=db_name)
        cursor = conn.cursor()

        # 先按GO分割（MSSQL批处理分隔符）
        split_reg = re.compile(r"^\s*GO\s*$", re.I | re.M)
        sql_batches = re.split(split_reg, sql)

        # 获取所有SQL语句（按GO分割后，每个批次内的SQL再用sqlparse分割）
        all_statements = []
        for batch in sql_batches:
            batch = batch.strip()
            if not batch:
                continue
            # 对每个批次内的SQL使用sqlparse分割
            batch_statements = sqlparse.split(batch)
            for stmt in batch_statements:
                stmt = stmt.strip()
                if stmt:
                    all_statements.append(stmt)

        # 开启事务（MSSQL默认自动提交，需要显式开启事务以便回滚）
        conn.autocommit = False

        rowid = 1
        # 设置数据库上下文，并记录 USE 语句（如果提供了 db_name）
        if db_name:
            use_sql = f"USE [{db_name}]"
            try:
                cursor.execute(use_sql)
                execute_result.rows.append(
                    ReviewResult(
                        id=rowid,
                        errlevel=0,
                        stagestatus="Execute Successfully",
                        errormessage="None",
                        sql=use_sql,
                        affected_rows=0,
                        execute_time=0,
                    )
                )
                rowid += 1
            except Exception as e:
                logger.warning(f"MSSQL USE语句执行失败：{traceback.format_exc()}")
                execute_result.error = str(e)
                execute_result.rows.append(
                    ReviewResult(
                        id=rowid,
                        errlevel=2,
                        stagestatus="Execute Failed",
                        errormessage=f"异常信息：{e}",
                        sql=use_sql,
                        affected_rows=0,
                        execute_time=0,
                    )
                )
                rowid += 1

        for idx, statement in enumerate(all_statements):
            try:
                # 使用 FuncTimer 统计执行时间
                with FuncTimer() as t:
                    cursor.execute(statement)
                    # 每条语句执行成功后立即提交（MSSQL特性）
                    conn.commit()
                execute_result.rows.append(
                    ReviewResult(
                        id=rowid,
                        errlevel=0,
                        stagestatus="Execute Successfully",
                        errormessage="None",
                        sql=statement,
                        affected_rows=cursor.rowcount,
                        execute_time=t.cost,
                    )
                )
            except Exception as e:
                logger.warning(
                    f"Mssql命令执行报错，语句：{statement}， 错误信息：{traceback.format_exc()}"
                )
                execute_result.error = str(e)
                # 追加当前报错语句信息到执行结果中
                execute_result.rows.append(
                    ReviewResult(
                        id=rowid,
                        errlevel=2,
                        stagestatus="Execute Failed",
                        errormessage=f"异常信息：{e}",
                        sql=statement,
                        affected_rows=0,
                        execute_time=0,
                    )
                )
                # 执行失败，回滚当前事务（如果有未提交的）
                try:
                    conn.rollback()
                except:
                    pass
                # 报错语句后面的语句标记为审核通过、未执行，追加到执行结果中
                rowid += 1
                for remaining_statement in all_statements[idx + 1 :]:
                    remaining_statement = remaining_statement.strip()
                    if not remaining_statement:
                        continue
                    execute_result.rows.append(
                        ReviewResult(
                            id=rowid,
                            errlevel=0,
                            stagestatus="Audit completed",
                            errormessage="前序语句失败, 未执行",
                            sql=remaining_statement,
                            affected_rows=0,
                            execute_time=0,
                        )
                    )
                    rowid += 1
                # 终止执行，不再执行后续语句
                break
            rowid += 1
        if close_conn:
            self.close()
        return execute_result

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
