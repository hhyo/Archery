#!/bin/bash
# Import native drivers and inspect client binaries without opening connections.
set -euo pipefail
source /etc/os-release
test "$VERSION_CODENAME" = "${EXPECTED_DEBIAN_CODENAME:?Set the expected Debian codename}"
source /opt/venv4archery/bin/activate
cd /opt/archery
python -m pip check
python - <<'PY'
import os
import sys
from copy import copy

if expected := os.environ.get("EXPECTED_PYTHON_VERSION"):
    assert f"{sys.version_info.major}.{sys.version_info.minor}" == expected

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "archery.settings")
import django

django.setup()
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.files.storage import storages
from django.template import Context, Template
from common.storage import ForgivingManifestStaticFilesStorage

assert isinstance(staticfiles_storage, ForgivingManifestStaticFilesStorage)
assert storages["default"].__class__.__name__ == "FileSystemStorage"
assert Template("{{ value }}").render(copy(Context({"value": "ok"}))) == "ok"
print(f"Python {sys.version.split()[0]}, Django {django.get_version()}: setup, templates and storage passed")

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
