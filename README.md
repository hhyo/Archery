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
archer镜像：https://dev.aliyun.com/detail.html?spm=5176.1972343.2.14.58c75aaaaSPjnX&repoId=142147  
inception镜像: https://dev.aliyun.com/detail.html?spm=5176.1972343.2.12.7b475aaaLiCfMf&repoId=142093
#### 单个容器启动
```bash
#新建Docker网络(inception直接通过容器名连接)
docker network create -d bridge archer-net

#准备inc.cnf文件，启动inception
docker run --name inception --network archer-net -v /your_path/inc.cnf:/etc/inc.cnf  -p 6669:6669 -dti registry.cn-hangzhou.aliyuncs.com/lihuanhuan/inception

#准备settings.py文件，启动archer，tag对应release版本，如1.3.2
docker run --name archer --network archer-net -v /your_path/:/opt/archer/downloads -v /your_path/settings.py:/opt/archer/archer/settings.py  -e NGINX_PORT=9123 -p 9123:9123 -dti registry.cn-hangzhou.aliyuncs.com/lihuanhuan/archer:tag

#表结构初始化
docker exec -ti archer /bin/bash
cd /opt/archer
source /opt/venv4archer/bin/activate
python3 manage.py makemigrations sql  
python3 manage.py migrate 

#创建管理用户
python3 manage.py createsuperuser

#启动日志查看和问题排查
docker logs archer
cat /tmp/archer.log
```

#### docker-compose

```yaml
version: '3'

services:
  mysql:
    image: mysql:5.7
    container_name: mysql
    restart: always
    ports:
      - "3306:3306"
    volumes:
      - "./mysql/my.cnf:/etc/mysql/my.cnf"
      - "./mysql/datadir:/var/lib/mysql"
    environment:
      MYSQL_ROOT_PASSWORD: xxx

  mongo:
    image: mongo
    container_name: mongo
    restart: always
    volumes:
      - "./mongo:/etc/mongo"
    ports:
      - 27017:27017
    environment:
      MONGO_INITDB_ROOT_USERNAME: xxx
      MONGO_INITDB_ROOT_PASSWORD: xxx

  inception:
    image: registry.cn-hangzhou.aliyuncs.com/lihuanhuan/inception
    container_name: inception
    restart: always
    ports:
      - "6669:6669"
    volumes:
      - "./inception/inc.cnf:/etc/inc.cnf"

  archer:
    image: registry.cn-hangzhou.aliyuncs.com/lihuanhuan/archer:1.3.2
    container_name: archer
    restart: always
    ports:
      - "9123:9123"
    volumes:
      - "./archer/settings.py:/opt/archer/archer/settings.py"
      - "./archer/downloads:/opt/archer/downloads"
    command: ["bash","/opt/archer/src/docker/startup.sh"]
    environment:
      NGINX_PORT: 9123

```


手动安装
===============
[部署说明](https://github.com/hhyo/archer/wiki/%E9%83%A8%E7%BD%B2)


依赖或引用项目
===============
- [inception](https://github.com/mysql-inception/inception)
- [Themis](https://github.com/CreditEaseDBA/Themis)
- [binlog2sql](https://github.com/danfengcao/binlog2sql)
- [aquila_v2](https://github.com/thinkdb/aquila_v2)
- [SQLAdvisor](https://github.com/Meituan-Dianping/SQLAdvisor)
- [SchemaSync](https://github.com/seanlook/SchemaSync)
