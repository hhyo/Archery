# archer
基于inception的自动化SQL操作平台

### 主要功能
* 发起inception SQL上线，工单提交
* 工单DBA人工审核、sql执行
* 历史工单展示
* 回滚数据展示
* 主库集群配置
* 用户权限配置，工程师角色（engineer）与审核角色（review_man）:工程师可以发起SQL上线，在通过了inception自动审核之后，需要由人工审核点击确认才能执行SQL
* 历史工单管理

### 安装步骤：
1. 安装python3：
tar -xzvf Python-3.4.1.tar.gz && cd Python-3.4.1 && ./configure --prefix=/path/to/python3 && make && make install
或者rpm、yum、binary等其他安装方式
2. 安装django：
tar -xzvf Django-1.8.17 && cd Django-1.8.17 && python3 setup.py install
3. 给python3安装MySQLdb模块
pip install pymysql
记得确保settings.py里有如下两行：
import pymysql
pymysql.install_as_MySQLdb()

由于python3使用的pymysql模块里并未兼容inception返回的server信息，因此需要编辑/path/to/python3/lib/python3.4/site-packages/pymysql/connections.py：
在if int(self.server_version.split('.', 1)[0]) >= 5: 这一行前面加上下面一句并保存：
self.server_version = '5.6.24-72.2-log'
4. 通过model创建数据库表
python3 manage.py makemigrations
python3 manage.py migrate
5. 记得登录到settings.py里配置的各个mysql里给用户授权
(1)archer数据库授权
(2)远程备份库授权
6. 创建系统root用户（该用户可以使用django admin来管理model）：
cd archer && python3 manage.py createsuperuser
7. 用django内置runserver启动服务：
cd archer && bash debug.sh
如果要用gunicorn启动服务的话，需要配合nginx处理静态资源.
