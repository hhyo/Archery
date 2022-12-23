FROM hhyo/archery-base

WORKDIR /opt/archery

COPY . /opt/archery/
COPY ./src/docker/soar /opt/archery/src/plugins/
COPY ./src/docker/my2sql /opt/archery/src/plugins/

#archery
RUN cd /opt \
    && yum -y install nginx \
    && source /opt/venv4archery/bin/activate \
    && pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple -r /opt/archery/requirements.txt \
    && cp /opt/archery/src/docker/nginx.conf /etc/nginx/ \
    && cp /opt/archery/src/docker/supervisord.conf /etc/ \
    && mv /opt/sqladvisor /opt/archery/src/plugins/ \
    && yum clean all \
    && rm -rf /var/cache/yum/*

#port
EXPOSE 9123

#start service
ENTRYPOINT bash /opt/archery/src/docker/startup.sh && bash
