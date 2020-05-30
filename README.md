<div align="center">

# <a href="https://archerydms.com/" target="_blank" rel="noopener noreferrer">Archery</a>

[![star](https://gitee.com/rtttte/Archery/badge/star.svg?theme=gvp)](https://gitee.com/rtttte/Archery)
[![Build Status](https://travis-ci.org/hhyo/Archery.svg?branch=master)](https://travis-ci.org/hhyo/Archery)
[![Release](https://img.shields.io/github/release/hhyo/archery.svg)](https://github.com/hhyo/archery/releases/)
[![codecov](https://codecov.io/gh/hhyo/archery/branch/master/graph/badge.svg)](https://codecov.io/gh/hhyo/archery)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/94e8587e507f4565a1ea5ea21fd94c32)](https://app.codacy.com/app/hhyo/Archery?utm_source=github.com&utm_medium=referral&utm_content=hhyo/Archery&utm_campaign=Badge_Grade_Dashboard)
[![version](https://img.shields.io/badge/python-3.6.5-blue.svg)](https://www.python.org/downloads/release/python-365/)
[![version](https://img.shields.io/badge/django-2.2-brightgreen.svg)](https://docs.djangoproject.com/zh-hans/2.2/)
[![docker_pulls](https://img.shields.io/docker/pulls/hhyo/archery.svg)](https://hub.docker.com/r/hhyo/archery/)
[![HitCount](http://hits.dwyl.io/hhyo/hhyo/Archery.svg)](http://hits.dwyl.io/hhyo/hhyo/Archery)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](http://github.com/hhyo/archery/blob/master/LICENSE)
[![996.icu](https://img.shields.io/badge/link-996.icu-red.svg)](https://996.icu)

[文档](https://archerydms.com/) | [FAQ](https://github.com/hhyo/archery/wiki/FAQ) | [Releases](https://github.com/hhyo/archery/releases/)

![](https://images.gitee.com/uploads/images/2019/1110/202317_32bd4a1c_1038040.png)

</div>


介绍
============
Archery是[archer](https://github.com/jly8866/archer)的分支项目，定位于SQL审核查询平台，旨在提升DBA的工作效率，支持主流数据库的SQL上线和查询，同时支持丰富的MySQL运维功能，所有功能都兼容手机端操作

功能清单
====

|  | 查询 | 审核 | 执行 | 备份 | 数据字典 | 慢日志 | 会话管理 | 账号管理 | 参数管理 | 数据归档 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MySQL | √ | √ | √ | √ | √ | √ | √ | √ | √ | √ |
| MsSQL | √ | × | √ | × | × | × | × | × | × | × |
| Redis | √ | × | √ | × | × | × | × | × | × | × |
| PgSQL | √ | × | √ | × | × | × | × | × | × | × |
| Oracle | √ | × | √ | ✔️ | × | × | × | × | × | × |
| MongoDB | √ | × | × | × | × | × | × | × | × | × |

  

快速开始
===============
### 系统体验
[在线体验](https://demo.archerydms.com)
  
| 账号 | 密码 |
| --- | --- |
| archer | archer |

### Docker
#### 准备运行配置
具体可参考：https://github.com/hhyo/Archery/tree/master/src/docker-compose    

#### 启动
下载 [Releases](https://github.com/hhyo/archery/releases/)文件，解压后进入docker-compose文件夹

```bash
#启动
docker-compose -f docker-compose.yml up -d

#表结构初始化
docker exec -ti archery /bin/bash
cd /opt/archery
source /opt/venv4archery/bin/activate
python3 manage.py makemigrations sql  
python3 manage.py migrate

#数据初始化
python3 manage.py dbshell<sql/fixtures/auth_group.sql
python3 manage.py dbshell<src/init_sql/mysql_slow_query_review.sql

#创建管理用户
python3 manage.py createsuperuser

#重启服务
docker restart archery

#日志查看和问题排查
docker logs archery -f --tail=10
logs/archery.log
```

#### 访问
http://127.0.0.1:9123/

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
- Binlog2SQL [binlog2sql](https://github.com/danfengcao/binlog2sql)
- 表结构同步 [SchemaSync](https://github.com/hhyo/SchemaSync)
- 慢日志解析展示 [pt-query-digest](https://www.percona.com/doc/percona-toolkit/3.0/pt-query-digest.html)|[aquila_v2](https://github.com/thinkdb/aquila_v2)
- 大表DDL [gh-ost](https://github.com/github/gh-ost)|[pt-online-schema-change](https://www.percona.com/doc/percona-toolkit/3.0/pt-online-schema-change.html)
- MyBatis XML解析 [mybatis-mapper2sql](https://github.com/hhyo/mybatis-mapper2sql)
- RDS管理 [aliyun-openapi-python-sdk](https://github.com/aliyun/aliyun-openapi-python-sdk)
- 数据加密 [django-mirage-field](https://github.com/luojilab/django-mirage-field)

贡献者
===============
[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/0)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/0)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/1)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/1)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/2)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/2)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/3)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/3)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/4)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/4)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/5)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/5)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/6)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/6)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/7)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/7)

贡献代码
===============
可查阅主页的开发计划以及依赖清单，在对应issues中回复认领，或者直接提交PR，感谢你对Archery的贡献  
贡献包括但不限于以下方式：
- Wiki文档（开放编辑）
- Bug修复
- 新功能提交
- 代码优化
- 测试用例完善

问题反馈
===============
[Issues](https://github.com/hhyo/archery/issues)是本项目唯一的沟通渠道，如果在使用过程中遇到问题，请先查阅文档，如果仍无法解决，请查看相关日志，保存截图信息，给我们提交[Issue](https://github.com/hhyo/archery/issues)，请按照模板提供相关信息，否则会被直接关闭，感谢理解
