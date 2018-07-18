# 说明
项目基于archer，调整部分自需功能，不定期更新，[查看开发计划](https://github.com/hhyo/archer/projects/1)  
master分支是最新代码，但是不保证功能稳定，建议使用最新release包

## 目录
* [系统体验](#系统体验)
* [功能说明](#功能说明)
* [部署](#部署)
    * [docker部署](#采取docker部署)
    * [手动安装](#部署)
* [使用说明](#使用说明)
    * [SQL审核](#sql审核)
    * [在线查询](#在线查询)
    * [慢日志管理](#慢日志管理)
    * [SQL优化](#sqladvisor优化工具)
    * [阿里云RDS管理](#阿里云rds管理)
* [部分问题解决办法](#部分问题解决办法)
    * [错误日志地址](#错误日志地址)
    * [页面样式显示异常](#页面样式显示异常)
    * [SQL上线相关](#sql上线相关)
    * [检测SQL报错的几种情况](#检测sql报错的几种情况)
    * [无法生成回滚语句](#无法生成回滚语句)
    * [脱敏查询规则未生效](#脱敏查询规则未生效)
    * [慢日志不显示](#慢日志不显示)

## 系统体验
[在线体验](http://52.221.195.102) 
  
|  角色 | 账号 | 密码 |
| --- | --- | --- |
|  管理员| archer | archer |
|  工程师| engineer | archer |
|  DBA| dba | archer |


## 功能说明
1. 组管理  
   支持自定义组，组成员之间审批流程隔离、主库配置隔离、钉钉通知隔离  
2. 审批流程改造  
   SQL上线审核、查询权限审核接入工作流，审批流程支持多级，自主配置  
3. 跳过inception执行工单  
   对于inception不支持的语法，如子查询更新，可以跳过inception直接执行，但无法生成回滚语句   
4. 快速上线其他实例  
   在工单详情可快速提交相同SQL内容到其他实例，可适用于test>beta>ga等多套环境维护的需求  
5. 数据库会话管理   
   管理主库实例的连接会话，可以批量KIll PROCESS  
6. SQL优化增加SQLTuning方式  
   [查看介绍](http://dbaplus.cn/blog-77-736-1.html)  
7. 配置项动态化  
   除数据库依赖外大多数配置项都转移到数据库中，可动态变更，避免重启服务  
8. SQL工单类型区分  
   自动判断DML&DDL，并且支持统计  
9. SQL工单自动审批  
   支持正则判断工单是否需要人工审批，开启自动审批后，不在正则范围内的SQL语句无需审批，系统自动审核  
10. 工单通知人  
   发起SQL上线时可以选择通知对象，将会在申请时邮件抄送给对方  
11. 菜单栏调整  
   多级菜单展示
12. 平台数据多维度报表展示  

   
## 部署
### 基础环境依赖
Python>=3.4    
Django>=2.0.0    
[Inception审核工具](https://github.com/mysql-inception/inception)    

### 安装
```
#基础环境
virtualenv venv4archer --python=python3
source /opt/venv4archer/bin/activate

#下载release包，安装依赖
pip3 install -r requirements.txt -i https://mirrors.ustc.edu.cn/pypi/web/simple/ 

#修改archer/settings.py文件DATABASES配置项，数据库字符集utf8，如果使用mysql5.7，sql_mode需要删除ONLY_FULL_GROUP_BY

#数据库初始化
https://github.com/hhyo/archer/tree/master/src/init_sql

#创建管理用户
python3 manage.py createsuperuser

#修改venv4archer/lib/python3.6/site-packages/MySQLdb/connections.py
def show_warnings(self):
    """Return detailed information about warnings as a
    sequence of tuples of (Level, Code, Message). This
    is only supported in MySQL-4.1 and up. If your server
    is an earlier version, an empty sequence is returned."""
    if self._server_version[0] is None: return () #增加一行，解决语法SQL语法错误时弹出的报错信息
    if self._server_version < (4,1): return ()
    self.query("SHOW WARNINGS")
    r = self.store_result()
    warnings = r.fetch_row(0)
    return warnings
```
### 启动
```
#启动
python3 manage.py runserver 0.0.0.0:9123  --insecure   
#访问
http://127.0.0.1:9123/
在【系统管理】-【配置项管理】修改相关配置项，配置组、用户、实例等信息
```

### 采取docker部署
```bash
#使用初始化脚本初始化数据库
https://github.com/hhyo/archer/tree/master/src/script/init_sql
#准备settings.py文件，修改相关配置项
#启动，tag对应release版本，如1.1.6
docker run --name archer -v /local_path/settings.py:/opt/archer/archer/settings.py  -e NGINX_PORT=9123 -p 9123:9123 -dti registry.cn-hangzhou.aliyuncs.com/lihuanhuan/archer:tag
```
inception镜像: https://dev.aliyun.com/detail.html?spm=5176.1972343.2.12.7b475aaaLiCfMf&repoId=142093

## 使用说明
### SQL审核
- 功能说明：SQL上线和审核功能依靠Inception审核平台，建议使用前先阅读Inception的[项目文档](http://mysql-inception.github.io/inception-document/)
- 相关配置：
    1. 在系统管理-配置项管理，有Inception配置项，需要按照配置说明进行配置
### 在线查询
- 功能说明：在线查询基于Inception的语法树打印来判断用户执行的SQL所包含的库和表，从而进行相关的权限校验和数据脱敏，其中脱敏是依据用户配置的脱敏规则和字段，对查询结果进行脱敏处理后返回，脱敏规则采取正则表达式，可自主配置数据脱敏的位置
- 相关配置：
    1. 在系统管理-配置项管理开启SQL查询，并且打开DATA_MASKING配置
    2. 在其他配置管理-全部后台数据中配置从库地址，用户在线查询
    3. 关于QUERY_CHECK配置项，是用于控制是否允许查询Inception不支持的语法，如复杂的嵌套查询等，关闭校验会导致Inception解析失败的查询语句权限校验和脱敏功能失效，请谨慎使用）
    4. 在其他配置管理-全部后台数据中配置脱敏字段和规则
        - 脱敏规则配置参考：

        | 规则类型 | 规则脱敏所用的正则表达式，表达式必须分组，隐藏的组会使用****代替 | 需要隐藏的组 | 规则描述 |
        | --- | --- | --- | --- |
        | 手机号 | (.{3})(.*)(.{4}) | 2 | 保留前三后四|
        | 证件号码 | (.*)(.{4})$ | 2 | 隐藏后四位|
        | 银行卡 | (.*)(.{4})$ | 2 | 隐藏后四位|
        | 邮箱 | (.*)@(.*) | 2 | 去除后缀|
### 慢日志管理
- 功能说明：采用percona-toolkit的[pt_query_digest](https://www.percona.com/doc/percona-toolkit/LATEST/pt-query-digest.html)收集慢日志，在系统中进行展示，并且支持一键获取优化建议
- 相关配置：
    1. 安装percona-toolkit（版本=3.0.6），以centos为例
        ```
        yum -y install http://www.percona.com/downloads/percona-release/redhat/0.1-3/percona-release-0.1-3.noarch.rpm
        yum -y install percona-toolkit.x86_64
        ```
    2. 使用src/init_sql/mysql_slow_query_review.sql创建慢日志收集表
    3. 将src/script/analysis_slow_query.sh部署到各个监控机器，注意修改脚本里面的 `hostname="${mysql_host}:${mysql_port}" `与archer主库配置信息一致
### SQLAdvisor优化工具
- 功能说明：利用美团SQLAdvisor对收集的慢日志进行优化，一键获取优化建议
- 相关配置：
    1. 安装SQLAdvisor，安装方法见[项目地址](https://github.com/Meituan-Dianping/SQLAdvisor)
    2. 修改配置文件SQLADVISOR为程序路径，路径需要完整，如'/opt/SQLAdvisor/sqladvisor/sqladvisor'
### 阿里云RDS管理
- 功能说明：调用阿里云SDK对RDS进行管理，支持管理慢日志、进程、表空间，其中进程和表空间需要管理权限的key
- 相关配置：
    1. 在系统管理-配置项管理开启RDS管理，安装以下模块
        ```
        pip3 install aliyun-python-sdk-core==2.3.5
        pip3 install aliyun-python-sdk-core-v3==2.5.3
        pip3 install aliyun-python-sdk-rds==2.1.1
        ```
    2. 在其他配置管理-全部后台数据中，添加阿里云账号的accesskey信息、实例对应关系，重新启动服务
### 集成LDAP
- 功能说明：对接LDAP认证，无需添加账号即可使用平台功能，开启LDAP后，会在每次登录时同步LDAP用户信息至审核平台
- 相关配置：
    1. 修改配置文件ENABLE_LDAP=True，安装相关模块，以centos为例
        ```
        yum install openldap-devel
        pip install django-auth-ldap==1.6.1
        ```
    2. 修改相关设置项，设置中仅提供最简配置，具体可参考模块[django-auth-ldap](https://github.com/django-auth-ldap/django-auth-ldap)
## 部分问题解决办法
### 错误日志地址
```
/tmp/archer.log
```

### 页面样式显示异常
- 如果是runserver/debug.sh启动
    1. 因为settings里面关闭了debug，即DEBUG = False，需要在启动命令后面增加 --insecure
- 如果是nginx+gunicorn/startup.sh启动
    1. 是因为nginx的静态资源配置不正确，无法加载样式

        ```
        location /static {
                      alias /archer/static; #此处指向settings.py配置项STATIC_ROOT目录的绝对路径，用于nginx收集静态资源，一般默认为archer按照目录下的static目录
                    }
        ```
### 无法登录（确认用户名和密码正确）
- 检查用户is_active字段是否为1
### SQL上线相关
- 实例不显示数据库
    1. archer会默认过滤一些系统和测试数据库，过滤列表为`'information_schema', 'performance_schema', 'mysql', 'test', 'sys'`
### 检测SQL报错的几种情况
#### The backup dbname is too long
- 主库配置的连接信息过长，Inception生成备份时需要依靠连接信息创建备份数据库，可使用ip或者cname别名缩短连接名信息
#### invalid source infomation
- inception用来审核的账号，密码不能包含*
#### Incorrect database name ''**
- inception检查不支持子查询
#### Invalid remote backup information**
- inception无法连接备份库
### 无法生成回滚语句
- 检查配置文件里面inception相关配置
- 检查inception审核用户和备份用户权限，权限参考
    ```
    — inception备份用户
    GRANT SELECT, INSERT, CREATE ON *.* TO 'inception_bak'
    — inception审核用户（主库配置用户，如果要使用会话管理需要赋予SUPER权限，如果需要使用OSC，请额外配置权限）
    GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER,REPLICATION CLIENT,REPLICATION SLAVE ON *.* TO 'inception'
    — archer在线查询用户（从库配置用户）
    GRANT SELECT ON *.* TO 'archer_read'
    ```
- 检查binlog格式，需要为ROW，binlog_row_image为FULL
- 检查DML的表是否存在主键
- 检查语句是否有影响数据
### 脱敏查询规则未生效
- 检查是否开启了脱敏配置
- 检查脱敏字段是否命中（是否区分大小写，实例名称和从库名称是否一致）
- 检查脱敏规则的正则表达式是否可以匹配到数据，无法匹配的会返回原结果
- 检查是否关闭了CHECK_QUERY参数，导致inception无法解析的语句未脱敏直接返回结果
### 慢日志不显示
- 检查pt工具的版本，建议大于3.0，3.0以下的表信息不一致
- 检查脚本内的配置，hostname和主库配置表中的内容是否保持一致
- 检查慢日志收集表mysql_slow_query_review_history是否存在记录，并且hostname_max是否和主库配置的host:port一致
## 联系方式
QQ群524233225
