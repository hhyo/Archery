"""Localize known SQLAdvisor log messages while preserving their SQL arguments."""

import re

from django.utils.translation import get_language

# Message formats emitted by the bundled SQLAdvisor executable.
_MESSAGES = [
    (
        "第%d步：开始解析join using条件:%s",
        "Step {0}: Analyze JOIN USING condition: {1}",
    ),
    (
        "第%d步：开始解析join on条件:%s=%s",
        "Step {0}: Analyze JOIN ON condition: {1}={2}",
    ),
    (
        "第%d步：开始选择驱动表,一共有%d个候选驱动表",
        "Step {0}: Select a driving table from {1} candidates",
    ),
    (
        "第%d步：候选驱动表%s的结果集行数为:%d",
        "Step {0}: Candidate driving table {1} has {2} result rows",
    ),
    ("第%d步：选择表%s为驱动表", "Step {0}: Use {1} as the driving table"),
    (
        "第%d步：侯选驱动表个数:%d,但无法确定驱动表",
        "Step {0}: Could not select a driving table from {1} candidates",
    ),
    (
        "第%d步：SQLAdvisor结束！错误日志:%s",
        "Step {0}: SQLAdvisor finished with error: {1}",
    ),
    (
        "第%d步：SQLAdvisor结束！表中没有任何索引",
        "Step {0}: SQLAdvisor finished: the table has no indexes",
    ),
    (
        "第%d步：表%s的行数:%d,limit行数:%d,得到where条件中%s的选择度:%d",
        "Step {0}: Table {1}: {2} rows, limit {3}; selectivity for WHERE condition {4}: {5}",
    ),
    ("第%d步：开始解析字段%s是哪一张表", "Step {0}: Resolve the table for column {1}"),
    ("第%d步：字段%s存在多个表中", "Step {0}: Column {1} exists in multiple tables"),
    ("第%d步：确定字段%s在表%s中", "Step {0}: Column {1} belongs to table {2}"),
    (
        "第%d步：字段%s不存在任何一张表中",
        "Step {0}: Column {1} was not found in any table",
    ),
    ("第%d步：开始解析group by 条件", "Step {0}: Analyze GROUP BY conditions"),
    ("第%d步：开始解析order by 条件", "Step {0}: Analyze ORDER BY conditions"),
    (
        "第%d步：字段%s是主键同时不在order by列表末尾,放弃处理order by条件",
        "Step {0}: Primary-key column {1} is not last in ORDER BY; skip ORDER BY analysis",
    ),
    (
        "第%d步：字段%s是主键并且在列表末尾,忽略不添加",
        "Step {0}: Primary-key column {1} is last in the list; do not add it",
    ),
    (
        "第%d步：表%s 经过运算得到的索引列首列是主键,直接放弃,没有优化建议",
        "Step {0}: Table {1}: the proposed index starts with the primary key; no optimization advice",
    ),
    (
        "第%d步：开始输出表%s索引优化建议:",
        "Step {0}: Index optimization advice for table {1}:",
    ),
    ("第%d步：索引(%s)已存在", "Step {0}: Index ({1}) already exists"),
    (
        "第%d步：表%s 的SQL太逆天,没有优化建议",
        "Step {0}: No optimization advice for table {1}",
    ),
    (
        "第%d步：开始验证表中是否已存在相关索引。表名:%s, 字段名:%s, 在索引中的位置:%d",
        "Step {0}: Check existing indexes: table {1}, column {2}, index position {3}",
    ),
    (
        "第%d步：开始验证 字段%s是不是主键。表名:%s",
        "Step {0}: Check whether column {1} is the primary key of table {2}",
    ),
    (
        "第%d步：字段%s是主键。表名:%s",
        "Step {0}: Column {1} is the primary key of table {2}",
    ),
    (
        "第%d步：字段%s不是主键。表名:%s",
        "Step {0}: Column {1} is not the primary key of table {2}",
    ),
    ("第%d步：表%s 是临时表,不进行处理", "Step {0}: Skip temporary table {1}"),
    ("第%d步：开始解析where中的条件:%s", "Step {0}: Analyze WHERE condition: {1}"),
    (
        "第%d步：条件%s 是like前缀匹配,跳过不分析.",
        "Step {0}: Skip LIKE prefix condition {1}",
    ),
    ("第%d步：开始添加group by 字段", "Step {0}: Add GROUP BY columns"),
    ("第%d步：开始添加order by 字段", "Step {0}: Add ORDER BY columns"),
    ("加载sqlparser模块有错", "Failed to load the SQL parser module"),
    ("setlocale 有错", "Failed to set the locale"),
    (
        "sqlparser 解析出错,返回值lex为空",
        "SQL parser error: the returned lex value is empty",
    ),
    (
        "第%d步: 对SQL解析优化之后得到的SQL:%s",
        "Step {0}: SQL after parsing and optimization: {1}",
    ),
    ("第%d步: SQLAdvisor结束!", "Step {0}: SQLAdvisor finished"),
]


def _pattern(source):
    parts = re.split(r"(%d|%s)", source)
    return re.compile(
        "".join(
            r"(\d+)" if p == "%d" else r"(.*?)" if p == "%s" else re.escape(p)
            for p in parts
        )
    )


_PATTERNS = [(_pattern(source), target) for source, target in _MESSAGES]


def localize_sqladvisor_report(report):
    if get_language() != "en":
        return report
    lines = []
    for line in report.splitlines(keepends=True):
        ending = (
            "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        )
        body = line.rstrip("\r\n")
        prefix, marker, message = body.partition("[Note] ")
        if not marker:
            prefix, message = "", body
        for pattern, target in _PATTERNS:
            match = pattern.fullmatch(message.strip())
            if match:
                body = prefix + marker + target.format(*match.groups())
                break
        lines.append(body + ending)
    return "".join(lines)
