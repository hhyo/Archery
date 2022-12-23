### 1. SQLAdvisor安装

#### 1.1 拉取最新代码
```
git clone https://github.com/Meituan-Dianping/SQLAdvisor.git
```

#### 1.2 安装依赖项

```
 1. yum | apt-get  install cmake libaio-devel libffi-devel glib2 glib2-devel
 2. yum | apt-get  install --enablerepo=Percona56 Percona-Server-shared-56
```
**注意**


1. 跟据glib安装的路径，修改SQLAdvisor/sqladvisor/CMakeLists.txt中的两处include_directories针对glib设置的path。glib yum 安装默认不需要修改路径
2. 编译sqladvisor时依赖perconaserverclient_r, 因此需要安装Percona-Server-shared-56。有可能需要配置软链接例如:1. cd /usr/lib64/ 2. ln -s libperconaserverclient_r.so.18 libperconaserverclient_r.so
3. 有可能需要配置percona56 yum源: yum install http://www.percona.com/downloads/percona-release/redhat/0.1-3/percona-release-0.1-3.noarch.rpm


#### 1.3 编译依赖项sqlparser

```
1. cmake -DBUILD_CONFIG=mysql_release -DCMAKE_BUILD_TYPE=debug -DCMAKE_INSTALL_PREFIX=/usr/local/sqlparser ./
2. make && make install
```

**注意**

1. DCMAKE_INSTALL_PREFIX为sqlparser库文件和头文件的安装目录，其中lib目录包含库文件libsqlparser.so，include目录包含所需的所有头文件。
2. DCMAKE_INSTALL_PREFIX值尽量不要修改，后面安装依赖这个目录。

#### 1.4 安装SQLAdvisor源码
```
1. cd SQLAdvisor/sqladvisor/
2. cmake -DCMAKE_BUILD_TYPE=debug ./
3. make
4. 在本路径下生成一个sqladvisor可执行文件，这即是我们想要的。
```

### 2. SQLAdvisor使用
#### 2.1 --help输出
```
./sqladvisor --help
Usage:
  sqladvisor [OPTION...] sqladvisor

SQL Advisor Summary

Help Options:
  -?, --help              Show help options

Application Options:
  -f, --defaults-file     sqls file
  -u, --username          username
  -p, --password          password
  -P, --port              port
  -h, --host              host
  -d, --dbname            database name
  -q, --sqls              sqls
  -v, --verbose           1:output logs 0:output nothing
```
#### 2.2 命令行传参调用
```
./sqladvisor -h xx  -P xx  -u xx -p 'xx' -d xx -q "sql" -v 1
```
#####注意：命令行传参时，参数名与值需要用空格隔开

#### 2.3 配置文件传参调用

```
$> cat sql.cnf
[sqladvisor]
username=xx
password=xx
host=xx
port=xx
dbname=xx
sqls=sql1;sql2;sql3....

cmd: ./sqladvisor -f sql.cnf  -v 1
```
