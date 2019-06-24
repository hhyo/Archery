FROM docker.io/centos:7

ENV VERSION v1.6.3

WORKDIR /opt/archery

#python3.6
RUN yum -y install wget gcc make zlib-devel openssl openssl-devel ncurses-devel\
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
#locale
    && rm -rf /etc/localtime && ln -s /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && yum -y install kde-l10n-Chinese \
    && localedef -c -f UTF-8 -i zh_CN zh_CN.utf8
#dockerize
ENV DOCKERIZE_VERSION v0.6.1
RUN wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && rm dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz
#sqladvisor
RUN yum -y install epel-release \
    && yum -y install cmake bison gcc-c++ git mysql-devel libaio-devel libffi-devel glib2 glib2-devel \
    && yum -y install https://repo.percona.com/yum/percona-release-latest.noarch.rpm \
    && yum -y install Percona-Server-devel-56 Percona-Server-shared-56  Percona-Server-client-56 \
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
    && yum install -y python-devel \
    && pip install schema-sync mysql-python
#soar
RUN cd /opt \
    && wget https://github.com/XiaoMi/soar/releases/download/0.11.0/soar.linux-amd64 -O soar \
    && chmod a+x soar
#binlog2sql
RUN cd /opt \
    && git clone https://github.com/danfengcao/binlog2sql.git \
    && mv binlog2sql/binlog2sql/ tmp_binlog2sql \
    && rm -rf binlog2sql
#msodbc
RUN cd /opt \
    && curl https://packages.microsoft.com/config/rhel/7/prod.repo > /etc/yum.repos.d/mssql-release.repo \
    && ACCEPT_EULA=Y yum -y install msodbcsql17 \
    && yum -y install unixODBC-devel
#oracle instantclient
RUN yum -y install http://yum.oracle.com/repo/OracleLinux/OL7/oracle/instantclient/x86_64/getPackage/oracle-instantclient19.3-basiclite-19.3.0.0.0-1.x86_64.rpm
#archery
RUN cd /opt \
    && yum -y install openldap-devel gettext nginx \
    && git clone https://github.com/hhyo/archery.git && cd archery && git checkout $VERSION \
    && source /opt/venv4archery/bin/activate \
    && pip3 install -r /opt/archery/requirements.txt -i https://mirrors.ustc.edu.cn/pypi/web/simple/ \
    && cp /opt/archery/src/docker/nginx.conf /etc/nginx/ \
    && mv /opt/sqladvisor /opt/archery/src/plugins/ \
    && mv /opt/soar /opt/archery/src/plugins/ \
    && mv /opt/tmp_binlog2sql /opt/archery/src/plugins/binlog2sql


ENV LANG en_US.UTF-8
ENV LC_ALL zh_CN.utf8

#port
EXPOSE 9123

#start service
ENTRYPOINT bash /opt/archery/src/docker/startup.sh && bash
