[![Build Status](https://travis-ci.org/hhyo/archery.svg?branch=master)](https://travis-ci.org/hhyo/archery)

介绍
============
项目基于[archer](https://github.com/jly8866/archer)，有问题请提交issue
- [文档](https://github.com/hhyo/archery/wiki)
- [release版本](https://github.com/hhyo/archery/releases/)

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
archery镜像：https://dev.aliyun.com/detail.html?spm=5176.1972343.2.2.58c75aaa3iK1Sb&repoId=244140    
inception镜像: https://dev.aliyun.com/detail.html?spm=5176.1972343.2.12.7b475aaaLiCfMf&repoId=142093

#### docker-compose.yml

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
    image: mongo:3.6
    container_name: mongo
    restart: always
    volumes:
      - "./mongo/datadir:/data/db"
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

  archery:
    image: registry.cn-hangzhou.aliyuncs.com/lihuanhuan/archery
    container_name: archery
    restart: always
    ports:
      - "9123:9123"
    volumes:
      - "./archery/settings.py:/opt/archery/archery/settings.py"
      - "./archery/downloads:/opt/archery/downloads"
    command: ["bash","/opt/archery/src/docker/startup.sh"]
    environment:
      NGINX_PORT: 9123

```

#### 准备构建配置
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

#创建管理用户
python3 manage.py createsuperuser

#日志查看和问题排查
docker logs archery
```

手动安装
===============
[部署说明](https://github.com/hhyo/archery/wiki/%E9%83%A8%E7%BD%B2)

依赖或引用项目
===============
- [archer](https://github.com/jly8866/archer)
- [inception](https://github.com/hhyo/inception)
- [Themis](https://github.com/CreditEaseDBA/Themis)
- [binlog2sql](https://github.com/danfengcao/binlog2sql)
- [SQLAdvisor](https://github.com/Meituan-Dianping/SQLAdvisor)
- [SOAR](https://github.com/XiaoMi/soar)
- [SchemaSync](https://github.com/seanlook/SchemaSync)
- [aquila_v2](https://github.com/thinkdb/aquila_v2)
