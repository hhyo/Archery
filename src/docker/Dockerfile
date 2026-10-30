# Build the base from this checkout unless an external base is explicitly supplied.
ARG PYTHON_BASE_IMAGE=library/python:3.11-bookworm
ARG BASE_IMAGE=archery-base
FROM ${PYTHON_BASE_IMAGE} AS archery-base
ENV SOAR_VERSION=0.11.0 TZ=Asia/Shanghai
WORKDIR /opt
COPY src/docker/setup.sh /opt/setup.sh
RUN chmod +x /opt/setup.sh && /opt/setup.sh && rm -f /opt/setup.sh

FROM ${BASE_IMAGE} AS runtime
SHELL ["/bin/bash", "-c"]
COPY . /opt/archery/

WORKDIR /opt/

RUN useradd nginx
# archery
# cx-Orable 安装需要低一点的 setuptools 版本，同时需要 --no-build-isolation 参数，否则会安装失败
# 后续可能需要重新设计 engine 和相关依赖, 防止依赖过于复杂
RUN apt-get update \
    && apt-get install -yq --no-install-recommends nginx mariadb-client \
    && source venv4archery/bin/activate \
    && pip install --no-cache-dir "setuptools<82" wheel \
    && pip install --no-cache-dir "oracledb==4.0.1" \
    && pip install --no-cache-dir -r /opt/archery/requirements.txt \
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

