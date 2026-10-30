#!/bin/bash
# Import native drivers and inspect client binaries without opening connections.
set -euo pipefail
source /etc/os-release
test "$VERSION_CODENAME" = bookworm
source /opt/venv4archery/bin/activate
python - <<'PY'
import MySQLdb
import ldap
import oracledb
import psycopg2
import pyodbc

assert "ODBC Driver 18 for SQL Server" in pyodbc.drivers()
oracledb.init_oracle_client()
print("Native driver imports and Oracle/ODBC client loading passed")
PY
nginx -t
mysql --version
pt-online-schema-change --version
/opt/archery/src/plugins/soar --version
/opt/archery/src/plugins/my2sql -h
if ldd /opt/archery/src/plugins/sqladvisor | grep -q 'not found'; then
    echo 'SQLAdvisor has unresolved shared-library dependencies' >&2
    exit 1
fi
