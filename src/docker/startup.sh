#!/bin/bash

cd /opt/archery

#切换python运行环境
source /opt/venv4archery/bin/activate

#修改重定向端口
if [[ -z $NGINX_PORT ]]; then
    sed -i "s/:nginx_port//g" /etc/nginx/nginx.conf
else
    sed -i "s/nginx_port/$NGINX_PORT/g" /etc/nginx/nginx.conf
fi

#启动nginx
/usr/sbin/nginx

#收集所有的静态文件到STATIC_ROOT
python3 manage.py collectstatic -v0 --noinput

#编译翻译文件
python3 manage.py compilemessages

#启动Django Q cluster，建议使用supervisor等进程管理工具
nohup python3 manage.py qcluster >> /opt/archery/downloads/log/qcluster.log 2>&1 &

settings=${1:-"archery.settings"}
ip=${2:-"127.0.0.1"}
port=${3:-8888}

gunicorn -w 4 --env DJANGO_SETTINGS_MODULE=${settings} --log-level=debug --error-logfile=/tmp/archery.err -b ${ip}:${port} --preload=True --timeout=600  archery.wsgi:application
