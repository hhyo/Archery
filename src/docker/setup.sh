#!/bin/bash
set -euxo pipefail
#sqladvisor
curl -o sqladvisor -L https://github.com/LeoQuote/SQLAdvisor/releases/download/v2.1/sqladvisor-linux-amd64
chmod +x sqladvisor
curl -o sqlparser.tar.gz -L https://github.com/LeoQuote/SQLAdvisor/releases/download/v2.1/sqlparser-linux-amd64.tar.gz
tar -xzvf sqlparser.tar.gz
mv sqlparser /usr/local/sqlparser
rm -rf sqlparser*
#soar
curl -L -q https://github.com/XiaoMi/soar/releases/download/$SOAR_VERSION/soar.linux-amd64 -o soar
chmod +x soar
#my2sql
curl -L -q https://raw.githubusercontent.com/liuhr/my2sql/master/releases/centOS_release_7.x/my2sql -o my2sql
chmod +x my2sql
#mongo
curl -L -q -o mongodb-linux-x86_64-rhel70-3.6.20.tgz https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-rhel70-3.6.20.tgz
tar -xvf mongodb-linux-x86_64-rhel70-3.6.20.tgz
mv /opt/mongodb-linux-x86_64-rhel70-3.6.20/bin/mongo /usr/local/bin/
chmod +x /usr/local/bin/mongo
rm -rf /opt/mongodb*
#msodbc
curl -q -L https://packages.microsoft.com/keys/microsoft.asc -o /etc/apt/trusted.gpg.d/microsoft.asc
curl -q -L https://packages.microsoft.com/config/debian/11/prod.list -o /etc/apt/sources.list.d/mssql-release.list
apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev
#oracle client
mkdir -p /opt/oracle 
cd /opt/oracle
curl -q -L -o oracle-install.zip https://download.oracle.com/otn_software/linux/instantclient/1921000/instantclient-basic-linux.x64-19.21.0.0.0dbru.zip
unzip oracle-install.zip
apt-get install libaio1
sh -c "echo /opt/oracle/instantclient_19_21 > /etc/ld.so.conf.d/oracle-instantclient.conf"
ldconfig
rm -rf oracle-install.zip
cd -
# mysql/percona client
curl -O https://repo.percona.com/apt/percona-release_latest.generic_all.deb
apt-get install -yq --no-install-recommends gnupg2 lsb-release ./percona-release_latest.generic_all.deb
apt-get update
percona-release setup -y ps-57
apt-get install -yq --no-install-recommends percona-toolkit
percona-release disable  ps-57
apt-get install -yq --no-install-recommends gcc libmariadb-dev libldap2-dev libsasl2-dev ldap-utils
# mysql 软链, 供 sqladvisor 使用
ln -s /usr/lib/x86_64-linux-gnu/libmariadb.so.3 /usr/lib/x86_64-linux-gnu/libmysqlclient.so.18
apt-get clean
ln -snf /usr/share/zoneinfo/$TZ /etc/localtime
echo $TZ > /etc/timezone
chmod +x sqladvisor soar my2sql
chmod +x /usr/local/bin/mongo
python3 -m venv venv4archery
