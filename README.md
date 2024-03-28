<div align="center">

# <a href="https://archerydms.com/" target="_blank" rel="noopener noreferrer">Archery</a>
<h4> SQL 审核查询平台<h4>

[![Django CI](https://github.com/hhyo/Archery/actions/workflows/django.yml/badge.svg)](https://github.com/hhyo/Archery/actions/workflows/django.yml)
[![Release](https://img.shields.io/github/release/hhyo/archery.svg)](https://github.com/hhyo/archery/releases/)
[![codecov](https://codecov.io/gh/hhyo/archery/branch/master/graph/badge.svg)](https://codecov.io/gh/hhyo/archery)
[![version](https://img.shields.io/pypi/pyversions/django)](https://img.shields.io/pypi/pyversions/django/)
[![version](https://img.shields.io/badge/django-4.1-brightgreen.svg)](https://docs.djangoproject.com/zh-hans/4.1/)
[![Publish Docker image](https://github.com/hhyo/Archery/actions/workflows/docker-image.yml/badge.svg)](https://github.com/hhyo/Archery/actions/workflows/docker-image.yml)
[![docker_pulls](https://img.shields.io/docker/pulls/hhyo/archery.svg)](https://hub.docker.com/r/hhyo/archery/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](http://github.com/hhyo/archery/blob/master/LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[文档](https://archerydms.com/) | [FAQ](https://github.com/hhyo/archery/wiki/FAQ) | [Releases](https://github.com/hhyo/archery/releases/)

![](https://github.com/hhyo/Archery/wiki/images/dashboard.png)

</div>

功能清单
====

| 数据库        | 查询 | 审核 | 执行 | 备份 | 数据字典 | 慢日志 | 会话管理 | 账号管理 | 参数管理 | 数据归档 |
|------------| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MySQL      | √ | √ | √ | √ | √ | √ | √ | √ | √ | √ |
| MsSQL      | √ | × | √ | × | √ | × | × | × | × | × |
| Redis      | √ | × | √ | × | × | × | × | × | × | × |
| PgSQL      | √ | × | √ | × | × | × | × | × | × | × |
| Oracle     | √ | √ | √ | √ | √ | × | √  | × | × | × |
| MongoDB    | √ | √  | √  | × | × | × | √  | √ | × | × |
| Phoenix    | √ | ×  | √  | × | × | × | × | × | × | × |
| ODPS       | √ | ×  | ×  | × | × | × | × | × | × | × |
| ClickHouse | √ | √  | √  | × | × | × | × | × | × | × |
| Cassandra  | √ | ×  | √  | × | × | × | × | × | × | × |
| Doris      | √ | ×  | √  | × | × | × | × | × | × | × |



快速开始
===============
### 系统体验
[在线体验](https://demo.archerydms.com)

| 账号 | 密码 |
| --- | --- |
| archer | archer |

### Docker
参考 https://github.com/hhyo/archery/wiki/docker 

手动安装
===============
[部署说明](https://github.com/hhyo/archery/wiki/manual)

运行测试
===============
```
python manage.py test -v 3
```

依赖清单
===============
### 框架
- [Django](https://github.com/django/django)
- [Bootstrap](https://github.com/twbs/bootstrap)
- [jQuery](https://github.com/jquery/jquery)
### 前端组件
- 菜单栏 [metisMenu](https://github.com/onokumus/metismenu)
- 主题 [sb-admin-2](https://github.com/BlackrockDigital/startbootstrap-sb-admin-2)
- 编辑器 [ace](https://github.com/ajaxorg/ace)
- SQL美化 [sql-formatter](https://github.com/zeroturnaround/sql-formatter)
- 表格  [bootstrap-table](https://github.com/wenzhixin/bootstrap-table)
- 表格编辑  [bootstrap-editable](https://github.com/vitalets/x-editable)
- 下拉菜单 [bootstrap-select](https://github.com/snapappointments/bootstrap-select)
- 文件上传 [bootstrap-fileinput](https://github.com/kartik-v/bootstrap-fileinput)
- 时间选择  [bootstrap-datetimepicker](https://github.com/smalot/bootstrap-datetimepicker)
- 日期选择  [daterangepicker](https://github.com/dangrossman/daterangepicker)
- 开关  [bootstrap-switch](https://github.com/Bttstrp/bootstrap-switch)
- Markdown展示  [marked](https://github.com/markedjs/marked)
### 服务端
- 队列任务 [django-q](https://github.com/Koed00/django-q)
- MySQL Connector [mysqlclient-python](https://github.com/PyMySQL/mysqlclient-python)
- MsSQL Connector [pyodbc](https://github.com/mkleehammer/pyodbc)
- Redis Connector [redis-py](https://github.com/andymccurdy/redis-py)
- PostgreSQL Connector [psycopg2](https://github.com/psycopg/psycopg2)
- Oracle Connector [cx_Oracle](https://github.com/oracle/python-cx_Oracle)
- MongoDB Connector [pymongo](https://github.com/mongodb/mongo-python-driver)
- Phoenix Connector [phoenixdb](https://github.com/lalinsky/python-phoenixdb)
- ODPS Connector [pyodps](https://github.com/aliyun/aliyun-odps-python-sdk)
- ClickHouse Connector [clickhouse-driver](https://github.com/mymarilyn/clickhouse-driver)
- SQL解析/切分/类型判断 [sqlparse](https://github.com/andialbrecht/sqlparse)
- MySQL Binlog解析/回滚 [python-mysql-replication](https://github.com/noplay/python-mysql-replication)
- LDAP [django-auth-ldap](https://github.com/django-auth-ldap/django-auth-ldap)
- 序列化 [simplejson](https://github.com/simplejson/simplejson)
- 时间处理 [python-dateutil](https://github.com/paxan/python-dateutil)
### 功能依赖
- 可视化 [pyecharts](https://github.com/pyecharts/pyecharts)
- MySQL审核/执行/备份 [goInception](https://github.com/hanchuanchuan/goInception)|[inception](https://github.com/hhyo/inception)
- MySQL索引优化 [SQLAdvisor](https://github.com/Meituan-Dianping/SQLAdvisor)
- SQL优化/压缩 [SOAR](https://github.com/XiaoMi/soar)
- My2SQL [my2sql](https://github.com/liuhr/my2sql)
- 表结构同步 [SchemaSync](https://github.com/hhyo/SchemaSync)
- 慢日志解析展示 [pt-query-digest](https://www.percona.com/doc/percona-toolkit/3.0/pt-query-digest.html)|[aquila_v2](https://github.com/thinkdb/aquila_v2)
- 大表DDL [gh-ost](https://github.com/github/gh-ost)|[pt-online-schema-change](https://www.percona.com/doc/percona-toolkit/3.0/pt-online-schema-change.html)
- MyBatis XML解析 [mybatis-mapper2sql](https://github.com/hhyo/mybatis-mapper2sql)
- RDS管理 [aliyun-openapi-python-sdk](https://github.com/aliyun/aliyun-openapi-python-sdk)
- 数据加密 [django-mirage-field](https://github.com/luojilab/django-mirage-field)


贡献代码
===============
可查阅主页的开发计划以及依赖清单，在对应Issues中回复认领，或者直接提交PR，感谢你对Archery的贡献

贡献包括但不限于以下方式：
- [Wiki文档](https://github.com/hhyo/Archery/wiki)（开放编辑）
- Bug修复
- 新功能提交
- 代码优化
- 测试用例完善

交流反馈
===============
- 使用咨询、需求沟通：[Discussions](https://github.com/hhyo/Archery/discussions)
- Bug提交：[Issues](https://github.com/hhyo/archery/issues)

致谢
===============
- [archer](https://github.com/jly8866/archer) Archery 项目是基于 archer 二次开发而来
- [goInception](https://github.com/hanchuanchuan/goInception) 一个集审核、执行、备份及生成回滚语句于一身的MySQL运维工具
- [JetBrains Open Source](https://www.jetbrains.com/zh-cn/opensource/?from=archery) 为项目提供免费的 IDE 授权  
  [<img src="https://resources.jetbrains.com/storage/products/company/brand/logos/jb_beam.png" width="200"/>](https://www.jetbrains.com/opensource/)

