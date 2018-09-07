[![Build Status](https://travis-ci.org/hhyo/archer.svg?branch=master)](https://travis-ci.org/hhyo/archer)

介绍
============
项目基于archer，不定期更新，有问题请提交issues，[查看开发计划](https://github.com/hhyo/archer/projects/1)  
- [文档](https://github.com/hhyo/archer/wiki)
- [release版本](https://github.com/hhyo/archer/releases/)

快速开始
===============
### 系统体验
[在线体验](http://13.251.244.118/) 
  
|  权限组 | 账号 | 密码 |
| --- | --- | --- |
|  管理员| archer | archer |
|  工程师| engineer | archer |
|  DBA| dba | archer |

### Docker

```bash
#使用初始化脚本初始化数据库
https://github.com/hhyo/archer/tree/master/src/script/init_sql

#新建Docker网络(inception直接通过容器名连接)
docker network create -d bridge archer-net

#准备inc.cnf文件，启动inception
docker run --name inception --network archer-net -v /your_path/inc.cnf:/etc/inc.cnf  -p 6669:6669 -dti registry.cn-hangzhou.aliyuncs.com/lihuanhuan/inception

#准备settings.py文件，启动archer，tag对应release版本，如1.3.0
docker run --name archer --network archer-net -v /your_path/:/opt/archer/downloads -v /your_path/settings.py:/opt/archer/archer/settings.py  -e NGINX_PORT=9123 -p 9123:9123 -dti registry.cn-hangzhou.aliyuncs.com/lihuanhuan/archer:tag

#启动日志查看和问题排查
docker exec -ti archer /bin/bash
cat /tmp/archer.log
cat /tmp/archer.err
```
archer镜像：https://dev.aliyun.com/detail.html?spm=5176.1972343.2.14.58c75aaaaSPjnX&repoId=142147  
inception镜像: https://dev.aliyun.com/detail.html?spm=5176.1972343.2.12.7b475aaaLiCfMf&repoId=142093

### 手动安装
#### 基础环境依赖

```
Python=3.6.5    
Django=2.0.7  
MySQL>=5.6
Inception审核工具：https://github.com/mysql-inception/inception
```

```
#基础python虚拟环境
virtualenv venv4archer --python=python3
source /opt/venv4archer/bin/activate

#下载release包，安装依赖
https://github.com/hhyo/archer/releases/
pip3 install -r requirements.txt -i https://mirrors.ustc.edu.cn/pypi/web/simple/ 

#修改archer/settings.py文件DATABASES配置项，数据库字符集utf8

#数据库初始化
https://github.com/hhyo/archer/tree/master/src/init_sql

#或者使用命令初始化
python3 manage.py makemigrations sql  
python3 manage.py migrate 

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
#### 启动
```
#启动
python3 manage.py runserver 0.0.0.0:9123  --insecure   
#访问
http://127.0.0.1:9123/
```

依赖或引用项目
===============
- [inception](https://github.com/mysql-inception/inception)
- [Themis](https://github.com/CreditEaseDBA/Themis)
- [binlog2sql](https://github.com/danfengcao/binlog2sql)
- [aquila_v2](https://github.com/thinkdb/aquila_v2)
- [SQLAdvisor](https://github.com/Meituan-Dianping/SQLAdvisor)
