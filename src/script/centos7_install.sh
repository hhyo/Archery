#!/usr/bin/env bash

DIR="$( cd "$( dirname "$0"  )" && pwd  )"
cd $DIR
cd ../../../ \
yum -y install unzip git gcc gcc-c++ make cmake bison openssl-devel mysql-devel \
&& yum -y install epel-release \
&& yum -y install python34 python34-pip python34-devel.x86_64 \
&& pip3 install virtualenv -i https://mirrors.ustc.edu.cn/pypi/web/simple/ \
&& virtualenv venv4archer --python=python3.4 \
&& source venv4archer/bin/activate \
&& pip3 install -r archer/requirements.txt -i https://mirrors.ustc.edu.cn/pypi/web/simple/ \
&& cp archer/src/pymysql/connections.py venv4archer/lib/python3.4/site-packages/pymysql/ \
&& cp archer/src/pymysql/cursors.py venv4archer/lib/python3.4/site-packages/pymysql/ \
