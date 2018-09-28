#!/bin/bash

cd /opt/archery
#切换python运行环境
source /opt/venv4archery/bin/activate
#修改重定向端口
if [ -z $NGINX_PORT ]; then
    sed -i "s/:nginx_port//g" /etc/nginx/nginx.conf
else
    sed -i "s/nginx_port/$NGINX_PORT/g" /etc/nginx/nginx.conf
fi
#启动ngnix
/usr/sbin/nginx

#收集所有的静态文件到STATIC_ROOT
python3 manage.py collectstatic -v0 --noinput

settings=${1:-"archery.settings"}
ip=${2:-"127.0.0.1"}
port=${3:-8888}

gunicorn -w 4 --env DJANGO_SETTINGS_MODULE=${settings} --error-logfile=/tmp/archery.err -b ${ip}:${port} --timeout 600  archery.wsgi:application
