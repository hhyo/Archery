FROM docker.io/centos:7

#python3.6
RUN yum -y install wget gcc make zlib-devel openssl openssl-devel \
    && cd /opt \
    && wget "https://www.python.org/ftp/python/3.6.5/Python-3.6.5.tar.xz" \
    && tar -xvJf Python-3.6.5.tar.xz \
    && cd /opt/Python-3.6.5 \
    && ./configure prefix=/usr/local/python3 \
    && make && make install \
    && ln -fs /usr/local/python3/bin/python3 /usr/bin/python3 \
    && ln -fs /usr/local/python3/bin/pip3 /usr/bin/pip3 \
    && pip3 install virtualenv -i https://mirrors.ustc.edu.cn/pypi/web/simple/ \
    && cd /opt \
    && ln -fs /usr/local/python3/bin/virtualenv /usr/bin/virtualenv \
    && virtualenv venv4archery --python=python3 \
    && rm -rf Python-3.6.5 \
    && rm -rf Python-3.6.5.tar.xz \
#修改中文支持
    && rm -rf /etc/localtime && ln -s /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && yum -y install kde-l10n-Chinese \
    && localedef -c -f UTF-8 -i zh_CN zh_CN.utf8
#sqladvisor
RUN yum -y install epel-release \
    && yum -y install cmake bison gcc-c++ git mysql-devel libaio-devel libffi-devel glib2 glib2-devel \
    && yum -y install http://www.percona.com/downloads/percona-release/redhat/0.1-3/percona-release-0.1-3.noarch.rpm \
    && yum -y install Percona-Server-devel-56.x86_64  Percona-Server-shared-56.x86_64  Percona-Server-client-56.x86_64 \
    && cd /opt \
    && git clone https://github.com/hhyo/SQLAdvisor.git \
    && cd /opt/SQLAdvisor/ \
    && cmake -DBUILD_CONFIG=mysql_release -DCMAKE_BUILD_TYPE=debug -DCMAKE_INSTALL_PREFIX=/usr/local/sqlparser ./ \
    && make && make install \
    && cd sqladvisor/ \
    && cmake -DCMAKE_BUILD_TYPE=debug ./ \
    && make \
    && mv /opt/SQLAdvisor/sqladvisor/sqladvisor /opt \
    && rm -rf /opt/SQLAdvisor/
#schemasync
RUN cd /opt \
    && virtualenv venv4schemasync  --python=python2 \
    && source venv4schemasync/bin/activate \
    && git clone https://github.com/hhyo/SchemaSync.git \
    && git clone https://github.com/hhyo/SchemaObject.git \
    && cd SchemaObject && python setup.py install \
    && cd ../SchemaSync && python setup.py install \
    && cd /opt && rm -rf /opt/SchemaObject/ && rm -rf /opt/SchemaSync/ \
    && yum install -y python-devel \
    && pip install mysql-python
#soar
RUN cd /opt \
    && wget https://github.com/XiaoMi/soar/releases/download/0.10.0/soar.linux-amd64 -O soar \
    && chmod a+x soar
#archery
RUN cd /opt \
    && yum -y install openldap-devel nginx \
    && git clone https://github.com/hhyo/archery.git && cd archery && git checkout v1.3.8 \
    && source /opt/venv4archery/bin/activate \
    && pip3 install -r /opt/archery/requirements.txt -i https://mirrors.ustc.edu.cn/pypi/web/simple/ \
    && cp /opt/archery/src/docker/nginx.conf /etc/nginx/ \
    && cp /opt/archery/src/docker/soar.yaml /etc/


ENV LANG en_US.UTF-8
ENV LC_ALL zh_CN.utf8

#port
EXPOSE 9123

#start service
ENTRYPOINT bash /opt/archery/src/docker/startup.sh && bash
