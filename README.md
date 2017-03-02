# archer
基于inception的自动化SQL操作平台

### 开发语言和推荐环境：
python：3.4<br/>
django：1.8<br/>
mysql : 5.6及以上<br/>
linux : 64位linux操作系统均可

### 主要功能
* 自动审核：<br/>
  发起SQL上线，工单提交，由inception自动审核，审核通过后需要由审核人进行人工审核
* 人工审核：<br/>
  工单DBA人工审核、审核通过自动执行SQL.<br/>
  为什么要有人工审核？<br/>
  这是遵循运维领域线上操作的流程意识，一个工程师要进行线上数据库SQL更新，最好由另外一个工程师来把关.<br/>
  很多时候DBA并不知道SQL的业务含义，所以人工审核最好由其他研发工程师或研发经理来审核. 这是archer的设计理念.
* 历史工单展示
* 回滚数据展示
* 主库集群配置
* 用户权限配置<br/>
  工程师角色（engineer）与审核角色（review_man）:工程师可以发起SQL上线，在通过了inception自动审核之后，需要由人工审核点击确认才能执行SQL
* 历史工单管理
* 可通过django admin进行匹配SQL关键字的工单搜索

### 安装步骤：
0. 克隆代码
1. 安装python3：<br/>
tar -xzvf Python-3.4.1.tar.gz <br/>
cd Python-3.4.1 <br/>
./configure --prefix=/path/to/python3 && make && make install
或者rpm、yum、binary等其他安装方式
2. 安装django：<br/>
tar -xzvf Django-1.8.17 && cd Django-1.8.17 && python3 setup.py install
3. 给python3安装MySQLdb模块<br/>
pip install pymysql<br/>
记得确保settings.py里有如下两行：<br/>
import pymysql<br/>
pymysql.install_as_MySQLdb()<br/>
<br/>
由于python3使用的pymysql模块里并未兼容inception返回的server信息，因此需要编辑/path/to/python3/lib/python3.4/site-packages/pymysql/connections.py：<br/>
在if int(self.server_version.split('.', 1)[0]) >= 5: 这一行前面加上下面一句并保存：<br/>
self.server_version = '5.6.24-72.2-log'<br/>
4. 通过model创建数据库表<br/>
python3 manage.py makemigrations<br/>
python3 manage.py migrate<br/>
5. 记得登录到settings.py里配置的各个mysql里给用户授权<br/>
(1)archer数据库授权<br/>
(2)远程备份库授权<br/>
6. 创建admin系统root用户（该用户可以登录django admin来管理model）：<br/>
cd archer && python3 manage.py createsuperuser<br/>
7. 创建archer系统登录用户（用户名密码自定义，至少创建一个工程师和一个审核人，后续新的用户请用LDAP导入或django admin增加）：<br/>
登录archer数据库，执行：<br/>
use archer; insert into sql_users(username, password, display, role) values('user1', 'pass1', '张三', '工程师');<br/>
use archer; insert into sql_users(username, password, display, role) values('user2', 'pass2', '李四', '审核人');<br/>
8. 启动：用django内置runserver启动服务<br/>
cd archer && bash debug.sh<br/>
<br/>
如果要用gunicorn启动服务的话，可以使用pip install gunicorn安装并用startup.sh启动，但需要配合nginx处理静态资源.
9. 访问页面：使用浏览器（推荐chrome或火狐）访问debug.sh里的地址：http://X.X.X.X:port/<br/>
如果没有登陆的话，会首先来到登录页面，请输入步骤7创建的archer系统登录用户进行登录。
10. 配置主库地址：<br/>
点击首页里的主库地址配置，可能会需要用步骤6创建的root用户登录admin界面进行创建.

### 系统展示截图：
1. 工单展示页：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/allworkflow.png)
<br/>
2. 提交SQL工单：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/submitsql.png)
<br/>
3. SQL自动审核、人工审核、执行结果详情页：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/waitingforme.png)
<br/>
4. 用户登录页：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/login.png)
<br/>
4. 用户、集群、工单管理：<br/>
![image](https://github.com/jly8866/archer/raw/master/screenshots/adminsqlusers.png)
<br/>

### 联系方式：
164473279@qq.com
