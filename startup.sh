#!/bin/bash

# 收集所有的静态文件到STATIC_ROOT
python3 manage.py collectstatic -v0 --noinput

# 编译翻译文件
python3 manage.py compilemessages

# 启动Django Q cluster
nohup python3 manage.py qcluster &

settings=${1:-"archery.settings"}
ip=${2:-"127.0.0.1"}
port=${3:-8000}

gunicorn -w 4 --env DJANGO_SETTINGS_MODULE=${settings} --log-level=debug --error-logfile=/tmp/archery.err -b ${ip}:${port} --preload=True --timeout=600  archery.wsgi:application
