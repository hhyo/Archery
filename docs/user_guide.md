## 使用说明
### 资源组
- 功能说明：资源组是一堆资源对象的集合，与用户关联后用来隔离资源访问权限，可以根据项目组进行划分，目前资源组可关联的对象有用户、实例，不同资源组的对象隔离，组成员仅可以查看组关联对象的数据
- 相关配置：
    1. 在系统管理-资源组管理页面，进行组管理以及组关联对象管理，用户必须关联资源组才能访问对应实例等资源信息
### 权限组
- 功能说明：权限组是使用django自带的权限管理模块，是一堆权限集合，工作流审批依赖权限组，用户可以关联到多个权限组，可以根据职能进行划分，如开发组、项目经理组、DBA组等
- 权限定义：目前定义了如下权限，可按照需求自主配置
    ```python
 	('menu_dashboard', '菜单 Dashboard'),
	('menu_sqlworkflow', '菜单 SQL上线'),
	('menu_query', '菜单 SQL查询'),
	('menu_sqlquery', '菜单 MySQL查询'),
	('menu_queryapplylist', '菜单 查询权限申请'),
	('menu_sqloptimize', '菜单 SQL优化'),
	('menu_sqladvisor', '菜单 优化工具'),
	('menu_slowquery', '菜单 慢查日志'),
	('menu_dbdiagnostic', '菜单 会话管理'),
	('menu_binlog2sql', '菜单 Binlog2SQL'),
	('menu_schemasync', '菜单 SchemaSync'),
	('menu_system', '菜单 系统管理'),
	('menu_instance', '菜单 实例管理'),
	('menu_document', '菜单 相关文档'),
	('menu_themis', '菜单 数据库审核'),
	('sql_submit', '提交SQL上线工单'),
	('sql_review', '审核SQL上线工单'),
	('sql_execute', '执行SQL上线工单'),
	('optimize_sqladvisor', '执行SQLAdvisor'),
	('optimize_sqltuning', '执行SQLTuning'),
	('optimize_soar', '执行SOAR'),
	('query_applypriv', '申请查询权限'),
	('query_mgtpriv', '管理查询权限'),
	('query_review', '审核查询权限'),
	('query_submit', '提交SQL查询'),
	('process_view', '查看会话'),
	('process_kill', '终止会话'),
	('tablespace_view', '查看表空间'),
	('trxandlocks_view', '查看锁信息'),
    ```
- 相关配置：
    1. 注册的用户和LDAP登录的用户会被分配到默认权限组，默认权限组权限可在系统配置中修改
    2. 在系统管理-用户管理中编辑用户可以给用户分配不同的权限组
    3. 在系统管理-其他配置管理-权限组管理页面，进行组的维护
### 工作流
- 功能说明：项目提供简单的多级审批流配置，审批流程和资源组以及审批类型相关，不同资源组和审批类型可以配置不同的审批流程，审批流程配置的是权限组，可避免审批人单点的问题
- 相关配置：
    1. 在系统管理-配置项管理页面，可进行组工单审批流程的配置
    2. 对于SQL上线和SQL查询权限工单，如果用户拥有('sql_review', '审核SQL上线工单')、('sql_execute', '执行SQL上线工单')、('query_review', '审核查询权限')权限，就可以查看到当前用户所在资源组的所有工单
    2. 工单待审核时，关联当前审批权限组、并且关联工单所在资源组的用户，均可查看审核工单（资源组隔离）
    4. 待办列表包含当前用户可审核的所有工单
### 消息通知
- 功能说明：在工单提交、审核、取消、执行的各个阶段都会通过对应的方式通知用户，目前通知类型分为两种，分别是邮件和钉钉，钉钉是关联资源组，该资源组所有的申请、审核通知都会调用钉钉机器人发送，邮件则会发送给具体的用户（配置用户的email信息）
- 相关配置：
    1. 在系统管理-配置项管理中修改相关配置
    2. 在系统管理-资源组管理页面，修改资源组的钉钉webhook信息
- 通知触发场景以及通知对象整理(仅邮件区分通知用户)

| 通知类型 |触发场景 | 通知对象 |附加描述|    
| --- | --- | --- | --- |    
| SQL上线申请/查询权限申请 | 提交申请 | 按照提交工单所选资源组配置的审批流程，发送给审批流程第一级权限组所包含的用户，并且仅发给权限组中关联了该资源组的用户，同时抄送给提交申请选择的通知人|通知对象需要具备两个条件：关联工单所在资源组并且关联了当前审批权限组|    
| SQL上线申请  | 取消申请 | 和提交申请保持一致 ||    
| SQL上线申请/查询权限申请  | 审核通过（非最终审核通过） | 按照提交工单所选资源组配置的审批流程，发送给下一级审批权限组所包含的用户，并且仅发给权限组中关联了该资源组的用户 |通知对象需要具备两个条件：关联该资源组并且关联了下级审批权限组|    
| SQL上线申请/查询权限申请  | 审核通过（最终审核通过） | 仅发送给申请人 ||    
| SQL上线申请/查询权限申请  | 审核不通过 | 仅发送给申请人 ||    
| SQL上线申请  | 执行结束 | 发送给申请人、抄送关联工单所在资源组的DBA(目前权限组固定为DBA) |仅关联了权限组名为【DBA】并且关联工单所在资源组的用户会收到抄送通知|       
| DDL工单通知  | DDL工单正常执行结束 | 发送给系统配置中ddl_notify_auth_group所配置的权限组关联的所有用户 |仅当DDL工单正常执行结束才会通知，执行异常不会通知|    
### SQL审核
- 功能说明：SQL上线和审核功能依靠Inception审核平台，建议使用前先完整阅读Inception的[项目文档](https://inception-document.readthedocs.io/)
- 相关配置：
    1. 在系统管理-配置项管理，有Inception配置项，需要按照配置说明进行配置
### SQL查询
- 功能说明：在线查询基于Inception的语法树打印来判断用户执行的SQL所包含的库和表，从而进行相关的权限校验和数据脱敏，其中脱敏是依据用户配置的脱敏规则和字段，对查询结果进行脱敏处理后返回，脱敏规则采取正则表达式，可自主配置数据脱敏的位置，并且查询日志中会记录权限校验和脱敏情况
- 相关配置：
    1. 在系统管理-配置项管理开启SQL查询，并且打开DATA_MASKING配置
    2. 在系统管理-实例管理中添加从库，即可进行在线查询，账号建议仅开放SELECT权限
    3. 关于QUERY_CHECK配置项，是用于控制是否允许查询Inception不支持的语法，如复杂的嵌套查询等，关闭校验会导致Inception解析失败的查询语句权限校验和脱敏功能失效，请谨慎使用）
    4. 在其他配置管理-全部后台数据中配置脱敏字段和规则
        - 脱敏规则配置参考：

        | 规则类型 | 规则脱敏所用的正则表达式，表达式必须分组，隐藏的组会使用****代替 | 需要隐藏的组 | 规则描述 |
        | --- | --- | --- | --- |
        | 手机号 | (.{3})(.*)(.{4}) | 2 | 保留前三后四|
        | 证件号码 | (.*)(.{4})$ | 2 | 隐藏后四位|
        | 银行卡 | (.*)(.{4})$ | 2 | 隐藏后四位|
        | 邮箱 | (.\*)@(.\*) | 2 | 去除后缀|
### SlowQuery
- 功能说明：采用percona-toolkit的[pt_query_digest](https://www.percona.com/doc/percona-toolkit/LATEST/pt-query-digest.html)收集慢日志，在系统中进行展示，并且支持一键获取优化建议
- 相关配置：
    1. 安装percona-toolkit，以centos为例
        ```
        yum -y install http://www.percona.com/downloads/percona-release/redhat/0.1-3/percona-release-0.1-3.noarch.rpm
        yum -y install percona-toolkit.x86_64
        ```
    2. 使用src/init_sql/mysql_slow_query_review.sql创建慢日志收集表
    3. 将src/script/analysis_slow_query.sh部署到各个mysql实例，注意修改脚本里面的hostname="${mysql_host}:${mysql_port}"与archery实例信息一致
### SQLAdvisor
- 功能说明：利用美团SQLAdvisor对收集的慢日志进行优化，一键获取优化建议，[项目地址](https://github.com/Meituan-Dianping/SQLAdvisor)
- 相关配置：
    1. 安装SQLAdvisor，docker镜像已包含
    2. 在系统管理-配置项管理中修改SQLADVISOR为程序路径，路径需要完整，docker部署的请修改为'/opt/sqladvisor'
### SQLTuning
- 功能说明：协助DBA高效、快速地优化语句，[文章链接](https://dbaplus.cn/blog-77-736-1.html)
### SOAR
- 功能说明：SOAR(SQL Optimizer And Rewriter)是一个对SQL进行优化和改写的自动化工具。 由小米人工智能与云平台的数据库团队开发与维护，[项目地址](https://github.com/XiaoMi/soar)
- 相关配置：
    1. 在系统管理-配置项管理中修改SOAR_PATH为程序路径，路径需要完整，docker部署的请修改为'/opt/soar'
    2. 修改SOAR_TEST_DSN为测试环境连接信息
### Binlog2SQL
- 功能说明：将Binlog2SQL模块可视化，从MySQL binlog解析出你要的SQL。根据不同选项，你可以得到原始SQL、回滚SQL、去除主键的INSERT SQL等，[项目地址](https://github.com/danfengcao/binlog2sql)
### SchemaSync
- 功能说明：对比不同数据库的Schema信息，输出修改语句和回滚语句，SchemaSync不仅限于表结构，它可以处理的对象还有：视图、事件、存储过程、函数、触发器、外键。[项目地址](https://github.com/hhyo/SchemaSync)
- 相关配置：
    1. 安装SCHEMASYNC(依赖Python2)，以centos为例，docker镜像已包含
    ```bash
    virtualenv venv4schemasync  --python=python2 
    source venv4schemasync/bin/activate 
    git clone https://github.com/hhyo/SchemaSync.git 
    git clone https://github.com/hhyo/SchemaObject.git 
    cd SchemaObject && python setup.py install 
    cd ../SchemaSync && python setup.py install 
    yum install -y python-devel \
    pip install mysql-python
    ```
    2. 在系统管理-配置项管理中修改SCHEMASYNC为程序路径，路径需要完整，docker部署的请修改为'/opt/venv4schemasync/bin/schemasync'
### Themis
- 功能说明：整合数据库审核项目Themis，Themis是宜信公司DBA团队开发的一款数据库审核产品。可帮助DBA、开发人员快速发现数据库质量问题，提升工作效率。[项目地址](https://github.com/CreditEaseDBA/Themis)
- 相关配置：
    1. 修改archery配置文件mongodb相关的配置，注意账号权限，docker部署的修改宿主机文件重启容器即可
    3. 将规则文件[rule.json](https://github.com/hhyo/archery/blob/master/src/script/rule.json)导入mongodb，命令参考：      
      `mongoimport -h 127.0.0.1 --port 27017 -d themis -c rule -u root -p 123456 --upsert rule.json --authenticationDatabase admin`
    4. 发布任务即可查看审核结果，其中除对象审核外，都依赖收集的慢日志信息
### 阿里云RDS管理
- 功能说明：调用阿里云SDK对RDS进行管理，支持管理慢日志、进程、表空间，其中进程和表空间需要管理权限的key
- 相关配置：
    1. 在其他配置管理-全部后台数据中，添加阿里云账号的accesskey信息、实例对应关系，即可使用rds管理
### 集成LDAP
- 功能说明：对接LDAP认证，无需添加账号即可使用平台功能，开启LDAP后，会在每次登录时同步LDAP用户信息至审核平台
- 相关配置：
    1. 修改配置文件ENABLE_LDAP=True
    2. 修改相关设置项，设置中仅提供最简配置，具体可参考模块[django-auth-ldap](https://github.com/django-auth-ldap/django-auth-ldap)
