<div align="center">

# <a href="http://139.199.0.191/" target="_blank" rel="noopener noreferrer">Archery</a> 

[![Gitter](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/dba-archery/community)
[![Build Status](https://travis-ci.org/hhyo/archery.svg?branch=master)](https://travis-ci.org/hhyo/archery)
[![Release](https://img.shields.io/github/release/hhyo/archery.svg)](https://github.com/hhyo/archery/releases/)
[![codecov](https://codecov.io/gh/hhyo/archery/branch/master/graph/badge.svg)](https://codecov.io/gh/hhyo/archery)
[![version](https://img.shields.io/badge/python-3.6.5-blue.svg)](https://www.python.org/downloads/release/python-365/)
[![version](https://img.shields.io/badge/django-2.0-brightgreen.svg)](https://docs.djangoproject.com/zh-hans/2.0/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](http://github.com/hhyo/archery/blob/master/LICENSE)

[文档](https://github.com/hhyo/archery/wiki) | [FAQ](https://github.com/hhyo/archery/wiki/FAQ) | [Releases](https://github.com/hhyo/archery/releases/)

</div>


介绍
============
archery是[archer](https://github.com/jly8866/archer)的一个分支项目，对部分模块进行了优化，新增数据库审核、binlog解析、表结构同步、实例用户管理等功能。同时针对多类型数据库(MsSQL/PostgreSQL/Redis)的支持也在不断完善中。不定期更新，请通过[Issues](https://github.com/hhyo/archery/issues)沟通反馈

开发计划
==============
https://github.com/hhyo/archery/projects   

快速开始
===============
### 系统体验
[在线体验](http://139.199.0.191/) 
  
| 账号 | 密码 |
| --- | --- |
| archer | archer |

### Docker
archery镜像：https://hub.docker.com/r/hhyo/archery    
inception镜像: https://hub.docker.com/r/hhyo/inception
#### 准备运行配置
具体可参考：https://github.com/hhyo/archery/raw/master/src/docker/install.zip

#### 启动

```bash
#启动
docker-compose -f docker-compose.yml up -d

#表结构初始化
docker exec -ti archery /bin/bash
cd /opt/archery
source /opt/venv4archery/bin/activate
python3 manage.py makemigrations sql  
python3 manage.py migrate 

#编译翻译文件
python3 manage.py compilemessages

#创建管理用户
python3 manage.py createsuperuser

#日志查看和问题排查
docker logs archery
/downloads/log/archery.log
```

#### 访问
http://127.0.0.1:9123/

手动安装
===============
[部署说明](https://github.com/hhyo/archery/wiki/%E9%83%A8%E7%BD%B2)

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
- 下拉菜单 [bootstrap-select](https://github.com/snapappointments/bootstrap-select)
- 文件上传 [bootstrap-fileinput](https://github.com/kartik-v/bootstrap-fileinput)
- 时间选择  [bootstrap-datetimepicker](https://github.com/Eonasdan/bootstrap-datetimepicker)
- 日期选择  [daterangepicker](https://github.com/dangrossman/daterangepicker)
- 开关  [bootstrap-switch](https://github.com/Bttstrp/bootstrap-switch)
- Markdown展示  [marked](https://github.com/markedjs/marked)
### 服务端
- 队列任务 [django-q](https://github.com/Koed00/django-q)
- SQL解析/切分/类型判断 [sqlparse](https://github.com/andialbrecht/sqlparse)
- Binlog解析/回滚 [python-mysql-replication](https://github.com/noplay/python-mysql-replication)
- LDAP [django-auth-ldap](https://github.com/django-auth-ldap/django-auth-ldap)
- 序列化 [simplejson](https://github.com/simplejson/simplejson)
### 功能依赖
- 可视化 [pyecharts](https://github.com/pyecharts/pyecharts)
- MySQL审核/语法树解析 [inception](https://github.com/hhyo/inception)
- 数据库审核 [Themis](https://github.com/CreditEaseDBA/Themis)
- MySQL索引优化 [SQLAdvisor](https://github.com/Meituan-Dianping/SQLAdvisor)
- SQL优化/压缩 [SOAR](https://github.com/XiaoMi/soar)
- Binlog2SQL [binlog2sql](https://github.com/danfengcao/binlog2sql)
- 表结构同步 [SchemaSync](https://github.com/hhyo/SchemaSync)
- 慢日志解析展示 [pt-query-digest](https://www.percona.com/doc/percona-toolkit/3.0/pt-query-digest.html)|[aquila_v2](https://github.com/thinkdb/aquila_v2)
- 大表DDL [gh-ost](https://github.com/github/gh-ost)|[pt-online-schema-change](https://www.percona.com/doc/percona-toolkit/3.0/pt-online-schema-change.html)
- MyBatis XML解析 [mybatis-mapper2sql](https://github.com/hhyo/mybatis-mapper2sql)
- RDS管理 [aliyun-openapi-python-sdk](https://github.com/aliyun/aliyun-openapi-python-sdk)

贡献者
===============
[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/0)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/0)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/1)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/1)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/2)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/2)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/3)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/3)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/4)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/4)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/5)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/5)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/6)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/6)[![](https://sourcerer.io/fame/hhyo/hhyo/archery/images/7)](https://sourcerer.io/fame/hhyo/hhyo/archery/links/7)
