#!/bin/bash

if [[ -x ".venv/bin/python" ]]; then
	PYTHON_BIN=".venv/bin/python"
elif [[ -x "venv/bin/python" ]]; then
	PYTHON_BIN="venv/bin/python"
elif [[ -x "env/bin/python" ]]; then
	PYTHON_BIN="env/bin/python"
else
	PYTHON_BIN="python3"
fi

nohup "$PYTHON_BIN" manage.py runserver 0.0.0.0:9123 --insecure &

# 启动Django Q cluster
nohup "$PYTHON_BIN" manage.py qcluster &
