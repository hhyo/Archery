#!/bin/bash

#收集所有的静态文件到STATIC_ROOT
python3 manage.py collectstatic -v0 --noinput

settings=${1:-"archer.settings"}
ip=${2:-"192.168.1.12"}
port=${3:-8888}

gunicorn -w 2 --env DJANGO_SETTINGS_MODULE=${settings} --error-logfile=/tmp/archer.err -b ${ip}:${port} --daemon archer.wsgi:application
