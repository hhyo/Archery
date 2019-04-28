FROM liwu/archerybase:0.1
#archery
RUN cd /opt \
    && yum -y install openldap-devel unixODBC-devel gettext nginx \
    && git clone https://github.com/GiftLee/Archery.git && cd Archery  \
    && source /opt/venv4archery/bin/activate \
    && pip3 install pytest-runner \
    && pip3 install -r /opt/Archery/requirements.txt  -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com \
    && cp /opt/Archery/src/docker/nginx.conf /etc/nginx/ \
    && mv /opt/sqladvisor /opt/Archery/src/plugins/ \
    && mv /opt/soar /opt/Archery/src/plugins/ \
    && mv /opt/tmp_binlog2sql /opt/Archery/src/plugins/binlog2sql \
    && ln -fs /opt/Archery /opt/archery


ENV LANG en_US.UTF-8
ENV LC_ALL zh_CN.utf8

#port
EXPOSE 9123

#start service
ENTRYPOINT bash /opt/Archery/src/docker/startup.sh && bash