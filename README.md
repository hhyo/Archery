# archer
基于inception的自动化SQL操作平台

### 开发语言和推荐环境：
python：3.4<br/>
django：1.8.17<br/>
mysql : 5.6及以上<br/>
linux : 64位linux操作系统均可

### 主要功能：
* 自动审核：<br/>
  发起SQL上线，工单提交，由inception自动审核，审核通过后需要由审核人进行人工审核
* 人工审核：<br/>
  工单DBA人工审核、审核通过自动执行SQL.<br/>
  为什么要有人工审核？<br/>
  这是遵循运维领域线上操作的流程意识，一个工程师要进行线上数据库SQL更新，最好由另外一个工程师来把关.<br/>
  很多时候DBA并不知道SQL的业务含义，所以人工审核最好由其他研发工程师或研发经理来审核. 这是archer的设计理念.
* 回滚数据展示
* 主库集群配置
* 用户权限配置<br/>
  工程师角色（engineer）与审核角色（review_man）:工程师可以发起SQL上线，在通过了inception自动审核之后，需要由人工审核点击确认才能执行SQL.<br/>
  还有一个特殊的超级管理员即可以上线、审核，又可以登录admin界面进行管理.
* 历史工单管理，查看、修改、删除
* 可通过django admin进行匹配SQL关键字的工单搜索
* 发起SQL上线，可配置的邮件提醒审核人进行审核
* 在发起SQL上线前，自助SQL审核，给出建议
* 审核通过正在执行中的工单，如果是由pt-OSC执行的SQL会显示执行进度，并且可以点击中止pt-OSC进程<br/>

### 设计规范：
* 合理的数据库设计和规范很有必要，尤其是MySQL数据库，内核没有oracle、db2、SQL Server等数据库这么强大，需要合理设计，扬长避短。互联网业界有成熟的MySQL设计规范，特此撰写如下。请读者在公司上线使用archer系统之前由专业DBA给所有后端开发人员培训一下此规范，做到知其然且知其所以然。<br/>
下载链接：  https://github.com/jly8866/archer/raw/master/docs/mysql_db_design_guide.docx

### 主要配置文件：
* archer/archer/settings.py<br/>

### 安装步骤：
1. 环境准备：<br/>
(1)克隆代码到本地: git clone https://github.com/jly8866/archer.git  或  下载zip包<br/>
(2)安装mysql 5.6实例，请注意保证mysql数据库默认字符集为utf8或utf8mb4<br/>
(3)安装inception<br/>
2. 安装python3：(强烈建议使用virtualenv或venv等单独隔离环境！)<br/>
tar -xzvf Python-3.4.1.tar.gz <br/>
cd Python-3.4.1 <br/>
./configure --prefix=/path/to/python3 && make && make install
或者rpm、yum、binary等其他安装方式
3. 安装所需相关模块：<br/>
(1)django：<br/>
tar -xzvf Django-1.8.17 && cd Django-1.8.17 && python3 setup.py install<br/>
或者pip3 install Django==1.8.17<br/>
(2)Crypto:<br/>
pip3 install Crypto<br/>
pip3 install pycrypto
4. 给python3安装MySQLdb模块:<br/>
pip3 install pymysql<br/>
记得确保settings.py里有如下两行：<br/>
import pymysql<br/>
pymysql.install_as_MySQLdb()<br/>
由于python3使用的pymysql模块里并未兼容inception返回的server信息，因此需要编辑/path/to/python3/lib/python3.4/site-packages/pymysql/connections.py：<br/>
在if int(self.server_version.split('.', 1)[0]) >= 5: 这一行之前加上以下这一句并保存，记得别用tab键用4个空格缩进：<br/>
self.server_version = '5.6.24-72.2-log'<br/>
最后看起来像这样：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/pymysql.png)<br/>
5. 创建archer本身的数据库表：<br/>
(1)修改archer/archer/settings.py所有的地址信息,包括DATABASES和INCEPTION_XXX部分<br/>
(2)通过model创建archer本身的数据库表, 记得先去archer数据库里CREATE DATABASE<br/>
python3 manage.py makemigrations或python3 manage.py makemigrations sql<br/>
python3 manage.py migrate<br/>
执行完记得去archer数据库里看表是否被创建了出来<br/>
6. mysql授权:<br/>
记得登录到archer/archer/settings.py里配置的各个mysql里给用户授权<br/>
(1)archer数据库授权<br/>
(2)远程备份库授权<br/>
7. 创建admin系统root用户（该用户可以登录django admin来管理model）：<br/>
cd archer && python3 manage.py createsuperuser<br/>
8. 启动，有两种方式：<br/>
(1)用django内置runserver启动服务,需要修改debug.sh里的ip和port<br/>
    cd archer && bash debug.sh<br/>
(2)用gunicorn启动服务，可以使用pip3 install gunicorn安装并用startup.sh启动，但需要配合nginx处理静态资源. (nginx安装这里不做示范)<br/>
    * gunicorn的安装配置示例:
        * pip3 install gunicorn
	    * cat startup.sh
            * ![image](https://github.com/jly8866/archer/raw/master/screenshots/startup.png)<br/>
    * nginx配置示例：
        * cat nginx.conf
            * ![image](https://github.com/jly8866/archer/raw/master/screenshots/nginx.png)<br/>
9. 创建archer系统登录用户：<br/>
使用浏览器（推荐chrome或火狐）访问debug.sh里的地址：http://X.X.X.X:port/admin/sql/users/ ，如果未登录需要用到步骤7创建的admin系统用户来登录。<br/>
点击右侧Add users，用户名密码自定义，至少创建一个工程师和一个审核人（步骤7创建的用户也可以登录）后续新的工程师和审核人用户请用LDAP导入sql_users表或django admin增加<br/>
10. 配置主库地址：<br/>
使用浏览器访问http://X.X.X.X:port/admin/sql/master_config/ ，点击右侧Add master_config<br/>
这一步是为了告诉archer你要用inception去哪些mysql主库里执行SQL，所用到的用户名密码、端口等。<br/>
11. 正式访问：<br/>
以上步骤完毕，就可以使用步骤9创建的用户登录archer系统啦, 首页地址 http://X.X.X.X:port/<br/>

### 已经制作好的docker镜像：
* 如果不想自己安装上述，可以直接使用做好的docker镜像，安装步骤：
    1. docker run -p 80:80 -d docker.gaoxiaobang.com/prod/archer    (需要确保docker宿主机80端口能够使用)
    2. 浏览器直接访问http://宿主机ip:80/ 即可, 初始用户名密码为root/root
* docker镜像制作感谢@浩气冲天 协助

### 系统展示截图：
1. 工单展示页：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/allworkflow.png)<br/>
2. 自助审核SQL：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/autoreview.png)<br/>
3. 提交SQL工单：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/submitsql.png)<br/>
4. SQL自动审核、人工审核、执行结果详情页：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/waitingforme.png)<br/>
5. 用户登录页：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/login.png)<br/>
6. 用户、集群、工单管理：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/adminsqlusers.png)<br/>
7. 工单统计图表：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/charts.png)<br/><br/>
8.pt-osc进度条，以及中止pt-osc进程按钮：<br/>
![image](https://raw.githubusercontent.com/johnliu2008/archer/master/screenshots/osc_progress.png)<br/>

### 联系方式：
QQ群：524233225

### 部分小问题解决办法：
1. 报错：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/bugs/bug1.png)&nbsp;
![image](https://github.com/jly8866/archer/raw/master/screenshots/bugs/bug2.png)<br/>
原因：python3的pymysql模块会向inception发送SHOW WARNINGS语句，导致inception返回一个"Must start as begin statement"错误被archer捕捉到报在日志里.<br/>
解决：如果实在忍受不了，请修改/path/to/python3/lib/python3.4/site-packages/pymysql/cursors.py:338行，将self._show_warnings()这一句注释掉，换成pass，如下：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/bugs/bug3.png)<br/>
但是此方法有副作用，会导致所有调用该pymysql模块的程序不能show warnings，因此强烈推荐使用virtualenv或venv环境！
