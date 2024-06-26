ARG BASE_IMAGE="hhyo/archery-base:sha-d8159f4"
FROM ${BASE_IMAGE}
SHELL ["/bin/bash", "-c"]
COPY . /opt/archery/

WORKDIR /opt/

RUN useradd nginx
#archery
RUN apt-get update \
    && apt-get install -yq --no-install-recommends nginx mariadb-client \
    && source venv4archery/bin/activate \
    && pip install -r /opt/archery/requirements.txt \
    && pip install "redis>=4.1.0" \
    && cp -f /opt/archery/src/docker/nginx.conf /etc/nginx/ \
    && cp -f /opt/archery/src/docker/supervisord.conf /etc/ \
    && mv /opt/sqladvisor /opt/archery/src/plugins/ \
    && mv /opt/soar /opt/archery/src/plugins/ \
    && mv /opt/my2sql /opt/archery/src/plugins/ \
    && apt-get -yq remove gcc curl \
    && apt-get clean \
    && rm -rf /var/cache/apt/* \
    && rm -rf /root/.cache

#port
EXPOSE 9123

#start service
ENTRYPOINT ["bash", "/opt/archery/src/docker/startup.sh"]

