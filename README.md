[![Build Status](https://travis-ci.org/hhyo/archery.svg?branch=master)](https://travis-ci.org/hhyo/archery)
[![version](https://img.shields.io/badge/python-3.6.5-blue.svg)](https://www.python.org/downloads/release/python-365/)
[![version](https://img.shields.io/badge/django-2.0.8-brightgreen.svg)](https://docs.djangoproject.com/zh-hans/2.0/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](http://github.com/hhyo/archery/blob/master/LICENSE)

[文档](https://github.com/hhyo/archery/wiki) | [FAQ](https://github.com/hhyo/archery/wiki/FAQ) | [Releases](https://github.com/hhyo/archery/releases/)

介绍
============
项目基于[archer](https://github.com/jly8866/archer)，优化了工作流、权限、项目、配置管理等一系列模块，不定期更新，请通过[Issues](https://github.com/hhyo/archery/issues)沟通反馈


快速开始
===============
### 系统体验
[在线体验](http://139.199.0.191/) 
  
| 账号 | 密码 |
| --- | --- |
| archer | archer |

### Docker
#### 准备运行配置
具体可参考：https://github.com/hhyo/archery/raw/master/src/docker/install.zip

#### 启动

```bash
#启动
docker-compose -f docker-compose.yml up -d

#表结构初始化（先创建数据库archery，字符集utf8）
docker exec -ti archery /bin/bash
cd /opt/archery
source /opt/venv4archery/bin/activate
python3 manage.py makemigrations sql  #这一步如果遇到报错可忽略
python3 manage.py migrate 

#创建管理用户
python3 manage.py createsuperuser

#日志查看和问题排查
docker logs archery
/downloads/log/archery.log
```

#### 访问
http://127.0.0.1:9123/

手动安装
===============
[部署说明](https://github.com/hhyo/archery/wiki/%E9%83%A8%E7%BD%B2)


主要依赖或引用项目
===============
- [archer](https://github.com/jly8866/archer)
- [inception](https://github.com/hhyo/inception)
- [Themis](https://github.com/CreditEaseDBA/Themis)
- [binlog2sql](https://github.com/danfengcao/binlog2sql)
- [SQLAdvisor](https://github.com/Meituan-Dianping/SQLAdvisor)
- [SOAR](https://github.com/XiaoMi/soar)
- [SchemaSync](https://github.com/seanlook/SchemaSync)
- [aquila_v2](https://github.com/thinkdb/aquila_v2)
