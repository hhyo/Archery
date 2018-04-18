# archer
基于inception的自动化SQL操作平台，支持工单、审核、邮件、OSC等功能，支持MySQL查询、动态脱敏、查询权限管理，自适应手机等小屏设备

### 开发语言和推荐环境
    python：3.4及以上  
    django：1.8.17  
    mysql : 5.6及以上  

### 主要功能
* 自动审核  
  发起SQL上线，工单提交，由inception自动审核
* 人工审核  
  inception自动审核通过的工单，由DBA人工审核、审核通过自动执行SQL   
  inception不支持的语法，如子查询更新，由DBA人工审核，可以选择跳过inception执行  
  为什么要有人工审核？  
  这是遵循运维领域线上操作的流程意识，一个工程师要进行线上数据库SQL更新，最好由另外一个工程师来把关  
  很多时候DBA并不知道SQL的业务含义，所以人工审核最好由其他研发工程师或研发经理来审核. 这是archer的设计理念
* 回滚数据展示  
  工单内可展示回滚语句，支持一键提交回滚工单
* pt-osc执行  
  支持pt-osc执行进度展示，并且可以点击中止pt-osc进程  
* MySQL查询  
  库、表、关键字自动补全  
  查询结果集限制、查询结果导出、表结构展示、多结果集展示  
* MySQL查询权限管理  
  基于inception解析查询语句，查询权限支持限制到表级  
  查询权限申请、审核和管理，支持审核流程配置，多级审核  
* MySQL查询动态脱敏   
  基于inception解析查询语句，配合脱敏字段配置、脱敏规则(正则表达式)实现敏感数据动态脱敏  
* 慢日志管理  
  基于percona-toolkit的pt_query_digest分析和存储慢日志，并在web端展现  
* 邮件通知  
  可配置邮件提醒，对上线申请、审核结果进行通知

### 设计规范
* 合理的数据库设计和规范很有必要，尤其是MySQL数据库，内核没有oracle、db2、SQL Server等数据库这么强大，需要合理设计，扬长避短。互联网业界有成熟的MySQL设计规范，特此撰写如下。请读者在公司上线使用archer系统之前由专业DBA给所有后端开发人员培训一下此规范，做到知其然且知其所以然。  
下载链接：  https://github.com/hhyo/archer/blob/master/src/docs/mysql_db_design_guide.docx

### 主要配置文件
* archer/archer/settings.py  

### 采取docker部署
* docker镜像，参考wiki：
    * inception镜像: https://dev.aliyun.com/detail.html?spm=5176.1972343.2.12.7b475aaaLiCfMf&repoId=142093
    * archer镜像: https://dev.aliyun.com/detail.html?spm=5176.1972343.2.38.XtXtLh&repoId=142147  
    archer镜像分为两个版本，latest是对应github分支，lihuanhuan是对应master分支，两个分支功能不同，请自行选择

### 一键安装脚本
* 可快速安装好archer环境，但inception还需自行安装  
[centos7_install](https://github.com/hhyo/archer/blob/master/src/script/centos7_install.sh)

### 手动安装步骤
1. 环境准备：  
(1)克隆代码到本地  
`git clone git@github.com:hhyo/archer.git`  
(2)安装inception，[项目地址](http://mysql-inception.github.io/inception-document/install/)  
2. 安装python3，版本号>=3.4：(由于需要修改官方模块，请使用virtualenv或venv等单独隔离环境！)  
3. 安装所需相关模块：  
`pip3 install -r requirements.txt -i https://mirrors.ustc.edu.cn/pypi/web/simple/`  
centos如果安装ladp报错需要执行yum install openldap-devel，其他系统请自行查找解决方案，如果不需要集成ladp也可以不安装  
4. MySQLdb模块兼容inception版本信息:  
使用src/docker/pymysql目录下的文件替换/path/to/python3/lib/python3.4/site-packages/pymysql/目录下的文件

### 启动前准备
1. 创建archer本身的数据库表：  
(1)修改archer/archer/settings.py所有的地址信息，包括DATABASES和INCEPTION_XXX部分  
(2)通过model创建archer本身的数据库表
    ```
    python3 manage.py makemigrations sql  
    python3 manage.py migrate 
    ```
2. 创建admin系统root用户（该用户可以登录django admin来管理model）：  
    `python3 manage.py createsuperuser`  
3. 启动，有两种方式：  
(1)用django内置runserver启动服务，仅开发环境使用，不要在生产环境使用   
    `bash debug.sh`  
(2)用gunicorn+nginx启动服务  
    nginx配置示例  
    ```
    server{
            listen 9123; #监听的端口
            server_name archer;
            client_header_timeout 1200; #超时时间与gunicorn超时时间设置一致
            client_body_timeout 1200;
            proxy_read_timeout 1200;
    
            location / {
              proxy_pass http://127.0.0.1:8000;
              proxy_set_header Host $host;
              proxy_set_header X-Real-IP $remote_addr;
              proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
              proxy_set_header X-Forwarded-Proto $scheme;
            }
    
            location /static {
              alias /archer/static; #此处指向settings.py配置项STATIC_ROOT目录的绝对路径，用于ngnix收集静态资源
            }
    
            error_page 404 /404.html;
                location = /40x.html {
            }
    
            error_page 500 502 503 504 /50x.html;
                location = /50x.html {
            }
        } 
    ```
    启动  
    `bash startup.sh`
4. 正式访问：  
    使用上面创建的管理员账号登录`http://X.X.X.X:port/`   
    
### 其他功能集成
#### 慢日志管理
1. 安装percona-toolkit（版本>3.0），以centos为例   
    yum -y install http://www.percona.com/downloads/percona-release/redhat/0.1-3/percona-release-0.1-3.noarch.rpm 
    yum -y install percona-toolkit.x86_64 
2. 使用src/script/mysql_slow_query_review.sql创建慢日志收集表到archer数据库
3. 将src/script/analysis_slow_query.sh部署到各个监控机器，注意修改配置信息
4. 如果有阿里云RDS实例，可以在后台数据管理添加关联关系  

#### 集成SQLAdvisor  
1. 安装SQLAdvisor，[项目地址](https://github.com/Meituan-Dianping/SQLAdvisor)
2. 修改配置文件SQLADVISOR为程序路径，路径需要完整，如'/opt/SQLAdvisor/sqladvisor/sqladvisor'

#### admin后台加固，防暴力破解
1. patch目录下，名称为：django_1.8.17_admin_secure_archer.patch
2. 使用命令：  
`patch  python/site-packages/django/contrib/auth/views.py django_1.8.17_admin_secure_archer.patch`

#### 集成ldap
1. settings中ENABLE_LDAP改为True,可以启用ldap账号登陆  
2. 如果使用了ldaps，并且是自签名证书，需要打开settings中AUTH_LDAP_GLOBAL_OPTIONS的注释  
3. settings中以AUTH_LDAP开头的配置，需要根据自己的ldap对应修改  

#### 集成阿里云rds管理  
1. 修改配置文件ENABLE_ALIYUN=True  
2. 在【后台数据管理】-【阿里云认证信息】页面，添加阿里云账号的accesskey信息，重新启动服务  
3. 在【后台数据管理】-【阿里云rds配置】页面，添加实例信息，即可实现对阿里云rds的进程管理、慢日志管理    

### 部分功能使用说明
1. 用户角色配置  
  在【后台数据管理】-【用户配置】页面管理用户，或者使用LADP导入  
  工程师角色（engineer）与审核角色（review_man），工程师可以发起SQL上线，审核人进行审核，超级管理员可以登录admin界面进行管理  
2. 配置主库地址  
  在【后台数据管理】-【主库地址】页面管理主库  
  主库地址用户SQL上线，DDL、DML、慢日志查看、SQL优化等功能
3. 配置从库地址    
  在【后台数据管理】-【从库地址】页面管理从库  
  从库地址用户SQL查询功能  
4. 配置查询权限审核流程  
  在【后台数据管理】-【工作流配置】页面管理审核流程   

### 系统展示截图：
1. 工单展示页  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/allworkflow.png)  
2. 自助审核SQL  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/autoreview.png)  
3. 提交SQL工单  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/submitsql.png)  
4. SQL自动审核、人工审核、执行结果详情页：  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/waitingforme.png)  
5. 用户登录页  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/login.png)
6. 工单统计图表  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/charts.png)  
7. pt-osc进度条，以及中止pt-osc进程按钮  
![image](https://github.com/hhyo/archer/blob/master/src//screenshots/osc_progress.png)  
8. SQL在线查询、自动补全  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/query.png)  
9. 动态脱敏  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/datamasking.png)  
10. SQL在线查询日志  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/querylog.png)  
11. SQL在线查询权限申请  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/applyforprivileges.png)  
12. SQL慢查日志统计  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/slowquery.png)  
13. SQL慢查日志明细、一键优化  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/slowquerylog.png)   
14. SQLAdvisor  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/sqladvisor.png)  
15. 阿里云RDS进程管理、表空间查询  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/process.png) 
16. 后台数据管理  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/admin.png)  
17. 权限审核配置  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/workflowconfig.png)  
18. 脱敏规则配置  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/datamaskingrules.png)  
19. 脱敏字段配置  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/datamaskingcolumns.png)  

### 联系方式：
QQ群：524233225

### 部分小问题解决办法：
1. 报错：  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/bugs/bug1.png)&nbsp;
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/bugs/bug2.png)  
原因：python3的pymysql模块会向inception发送SHOW WARNINGS语句，导致inception返回一个"Must start as begin statement"错误被archer捕捉到报在日志里.  
解决：如果实在忍受不了，请修改/path/to/python3/lib/python3.4/site-packages/pymysql/cursors.py:338行，将self._show_warnings()这一句注释掉，换成pass，如下：  
![image](https://github.com/hhyo/archer/blob/master/src/screenshots/bugs/bug3.png)  
但是此方法有副作用，会导致所有调用该pymysql模块的程序不能show warnings，因此强烈推荐使用virtualenv或venv环境！
