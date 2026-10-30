ARG BASE_IMAGE="hhyo/archery-base:sha-d8159f4"
FROM ${BASE_IMAGE}
SHELL ["/bin/bash", "-c"]
COPY . /opt/archery/

WORKDIR /opt/

RUN useradd nginx
# archery
# cx-Orable 安装需要低一点的 setuptools 版本，同时需要 --no-build-isolation 参数，否则会安装失败
# 后续可能需要重新设计 engine 和相关依赖, 防止依赖过于复杂
# Debian 11's package repositories are archived after the end of LTS.
# Keep signature verification enabled and leave newer base images unchanged.
RUN if [ "$(. /etc/os-release && printf '%s' "$VERSION_CODENAME")" = "bullseye" ]; then \
        find /etc/apt -type f \( -name '*.list' -o -name '*.sources' \) \
            -exec sed -i \
                -e 's|http[s]*://deb.debian.org/debian-security|https://archive.debian.org/debian-security|g' \
                -e 's|http[s]*://security.debian.org/debian-security|https://archive.debian.org/debian-security|g' \
                -e 's|http[s]*://deb.debian.org/debian|https://archive.debian.org/debian|g' {} +; \
    fi \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get update \
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

