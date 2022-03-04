FROM hhyo/archery-base:sha-3c64fc8

WORKDIR /opt/archery

COPY . /opt/archery/

#archery
RUN cd /opt \
    && yum -y install nginx \
    && source /opt/venv4archery/bin/activate \
    && pip3 install -r /opt/archery/requirements.txt \
    && cp /opt/archery/src/docker/nginx.conf /etc/nginx/ \
    && cp /opt/archery/src/docker/supervisord.conf /etc/ \
    && mv /opt/sqladvisor /opt/archery/src/plugins/ \
    && mv /opt/soar /opt/archery/src/plugins/ \
    && mv /opt/tmp_binlog2sql /opt/archery/src/plugins/binlog2sql \
    && mv /opt/my2sql /opt/archery/src/plugins/

#port
EXPOSE 9123

#start service
ENTRYPOINT bash /opt/archery/src/docker/startup.sh && bash
