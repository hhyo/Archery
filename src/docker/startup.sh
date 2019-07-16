#!/bin/bash

cd /opt/archery

echo 切换python运行环境
source /opt/venv4archery/bin/activate

echo 修改重定向端口
if [[ -z $NGINX_PORT ]]; then
    sed -i "s/:nginx_port//g" /etc/nginx/nginx.conf
else
    sed -i "s/nginx_port/$NGINX_PORT/g" /etc/nginx/nginx.conf
fi

echo 启动nginx
/usr/sbin/nginx

echo 收集所有的静态文件到STATIC_ROOT
python3 manage.py collectstatic -v0 --noinput

echo 启动Django Q cluster
supervisord -c qcluster_supervisord.conf

echo 启动服务
settings=${1:-"archery.settings"}
ip=${2:-"127.0.0.1"}
port=${3:-8888}

gunicorn -w 4 --env DJANGO_SETTINGS_MODULE=${settings} --log-level=debug --error-logfile=/tmp/archery.err -b ${ip}:${port} --preload --timeout 600  archery.wsgi:application
