## 手动部署
### 安装
```
#Python环境（Python>=3.6.5，建议使用虚拟环境 ）
virtualenv venv4archery --python=python3
source /opt/venv4archery/bin/activate

#下载release包，安装依赖
https://github.com/hhyo/archery/releases/
pip3 install -r requirements.txt -i https://mirrors.ustc.edu.cn/pypi/web/simple/ 

#修改archery/settings.py文件DATABASES配置项

#数据库初始化
python3 manage.py makemigrations sql  
python3 manage.py migrate 

#创建管理用户
python3 manage.py createsuperuser
```

### 启动
#### runserver启动
```
source /opt/venv4archery/bin/activate
python3 manage.py runserver 0.0.0.0:9123  --insecure   
```

#### gunicorn+nginx启动
```
source /opt/venv4archery/bin/activate
pip3 install gunicorn

#nginx配置示例  
server{
        listen 9123; #监听的端口
        server_name archery;
        proxy_read_timeout 600s;  #超时时间与gunicorn超时时间设置一致，主要用于在线查询

        location / {
          proxy_pass http://127.0.0.1:8888;
          proxy_set_header Host $host:9123; #解决重定向404的问题
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /static {
          alias /archery/static; #此处指向settings.py配置项STATIC_ROOT目录的绝对路径，用于nginx收集静态资源
        }

        error_page 404 /404.html;
            location = /40x.html {
        }

        error_page 500 502 503 504 /50x.html;
            location = /50x.html {
        }
    } 

#启动  
bash startup.sh
```
### 访问
http://127.0.0.1:9123/

## 采取docker部署
### 准备构建配置
具体可参考：https://github.com/hhyo/archery/raw/master/src/docker/install.zip

### 启动

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

#### 访问
http://127.0.0.1:9123/