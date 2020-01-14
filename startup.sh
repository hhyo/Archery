#!/bin/bash

# 收集所有的静态文件到STATIC_ROOT
python3 manage.py collectstatic -v0 --noinput

# 启动服务
supervisord -c supervisord.conf

