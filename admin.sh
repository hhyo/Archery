#!/usr/bin/env bash

#########################################################################
# Update Time : 2020-02-25
# Author: alenx <alenx.hai@gmail.com>
#########################################################################

function init() {
    echo "Initing archery"
    echo "----------------"
    echo "安装/更新可能缺少的依赖: mysql-community-devel gcc gcc-c++ python-devel"
    sudo yum install epel-release
    sudo yum install -y mysql-devel gcc gcc-c++ python-devel MySQL-python
    sudo yum install -y python36 python36-pip openldap-devel unixODBC-devel gettext

    python3 -m pip install virtualenv
    if [ ! -d "venv" ]; then
        virtualenv --system-site-packages -p python3 venv
    fi

    source ./venv/bin/activate
    ./venv/bin/python3 -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
    echo "************************************************"
    echo -e "\033[32m init archery success \033[0m"
    echo -e "\033[32m welcome to archery 2.0 \033[0m"
}

function start() {
    echo "Starting archery"
    echo "----------------"
    source ./venv/bin/activate
    python3 manage.py collectstatic -v0 --noinput
    supervisord -c supervisord.conf
    echo -e "Start archery:                 [\033[32m ok \033[0m]"
}

function stop() {
    echo "Stoping archery"
    echo "----------------"
    PID=$(ps -ef | grep "supervisord" | grep -v grep | awk '{print $2}')
    kill -9 ${PID}
    echo -e "Stop archery:                  [\033[32m ok \033[0m]"
}

function restart() {
    stop
    echo ""
    start
}

function upgrade() {
    echo "Upgrading archery"
    echo "----------------"
    cd $(dirname $0)
    echo -e "建议先暂存本地修改\033[33m git stash\033[0m，更新后再弹出\033[33m git stash pop\033[0m，处理冲突。"
    source ./venv/bin/activate
    git pull
}

function migration() {
    echo "Migration archery"
    echo "----------------"
    source ./venv/bin/activate
    python3 manage.py makemigrations sql
    python3 manage.py migrate
    python3 manage.py dbshell<sql/fixtures/auth_group.sql
    if [ $? == "0" ]; then
        echo -e "Migration:                 [\033[32m ok \033[0m]"
    else
        echo -e "Migration:                 [\033[31m fail \033[0m]"
    fi
}

case "$1" in
    init )
        init
        ;;
    start )
        start
        ;;
    stop )
        stop
        ;;
    restart )
        restart
        ;;
    upgrade )
        upgrade
        migration
        echo -e "\033[32m archery 更新成功. \033[0m \033[33m 建议重启服务 sh admin.sh restart\033[0m"
        ;;
    migration )
        migration
        ;;
    * )
        echo "************************************************"
        echo "Usage: sh admin {init|start|stop|restart|upgrade|migration}"
        echo "************************************************"
        ;;
esac