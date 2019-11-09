FROM sunnywalden/archery-multi-tenant:base-python37

ENV VERSION feature/muti-tenant

WORKDIR /opt/archery

COPY . /opt/archery/

#archery
RUN cd /opt \
    && yum -y install openldap-devel gettext nginx \
    && source /opt/venv4archery/bin/activate \
#    && git clone https://github.com/sunnywalden/archery.git -b feature/muti-tenant --depth 3 \
    && cd /opt/archery \
#    && git checkout $VERSION \
    && pip3 install -r /opt/archery/requirements.txt \
    && cp /opt/archery/src/docker/nginx.conf /etc/nginx/ \
    && mv /opt/sqladvisor /opt/archery/src/plugins/ \
    && mv /opt/soar /opt/archery/src/plugins/ \
    && mv /opt/tmp_binlog2sql /opt/archery/src/plugins/binlog2sql

#port
EXPOSE 9123

#start service
ENTRYPOINT bash /opt/archery/src/docker/startup.sh && bash
