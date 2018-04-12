FROM docker.io/centos

#archer
RUN yum -y install unzip git gcc gcc-c++ make cmake bison openssl-devel mysql-devel openldap-devel \
    && yum -y install epel-release \
    && yum -y install python34 python34-pip python34-devel.x86_64 \
    && cd /opt \
    && pip3 install virtualenv -i https://mirrors.ustc.edu.cn/pypi/web/simple/ \
    && virtualenv venv4archer --python=python3.4 \
    && source venv4archer/bin/activate \    
    && git clone https://github.com/hhyo/archer.git \
    && pip3 install -r /opt/archer/requirements.txt -i https://mirrors.ustc.edu.cn/pypi/web/simple/ \
    && cp /opt/archer/src/docker/pymysql/connections.py /opt/venv4archer/lib/python3.4/site-packages/pymysql/ \
    && cp /opt/archer/src/docker/pymysql/cursors.py /opt/venv4archer/lib/python3.4/site-packages/pymysql/ \
    && yum -y install nginx \
    && cp /opt/archer/src/docker/nginx.conf /etc/nginx/ \
    && nginx \ 
#sqladvisor
    && yum -y install libaio-devel libffi-devel glib2 glib2-devel \
    && yum -y install http://www.percona.com/downloads/percona-release/redhat/0.1-3/percona-release-0.1-3.noarch.rpm \
    && yum -y install Percona-Server-devel-56.x86_64  Percona-Server-shared-56.x86_64  Percona-Server-client-56.x86_64 \ 
    && git clone https://github.com/Meituan-Dianping/SQLAdvisor.git \
    && cd /opt/SQLAdvisor/ \
    && yum -y install make \
    && cmake -DBUILD_CONFIG=mysql_release -DCMAKE_BUILD_TYPE=debug -DCMAKE_INSTALL_PREFIX=/usr/local/sqlparser ./ \
    && make && make install \
    && cd sqladvisor/ \
    && cmake -DCMAKE_BUILD_TYPE=debug ./ \
    && make \ 
#修改中文支持
    && rm -rf /etc/localtime && ln -s /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \ 
    && yum -y install kde-l10n-Chinese && yum -y reinstall glibc-common \ 
    && localedef -c -f UTF-8 -i zh_CN zh_CN.utf8  

ENV LANG en_US.UTF-8
ENV LC_ALL zh_CN.utf8 

#port
EXPOSE 9123

#start service
ENTRYPOINT bash /opt/archer/src/docker/startup.sh && bash
