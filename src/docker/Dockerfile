FROM hhyo/archery-base:sha-b3a08ef

WORKDIR /opt/archery

ADD http://mirrors.ustc.edu.cn/epel/RPM-GPG-KEY-EPEL-7 /etc/pki/rpm-gpg/
COPY . /opt/archery/

#archery
RUN cd /opt \
    && yum -y install nginx \
    && source /opt/venv4archery/bin/activate \
    && pip3 install -r /opt/archery/requirements.txt \
    && cp -f /opt/archery/src/docker/nginx.conf /etc/nginx/ \
    && cp -f /opt/archery/src/docker/supervisord.conf /etc/ \
    && mv /opt/sqladvisor /opt/archery/src/plugins/ \
    && mv /opt/soar /opt/archery/src/plugins/ \
    && mv /opt/my2sql /opt/archery/src/plugins/ \
    && yum clean all \
    && rm -rf /var/cache/yum/* \
    && rm -rf ~/.cache

#port
EXPOSE 9123

#start service
ENTRYPOINT bash /opt/archery/src/docker/startup.sh && bash

