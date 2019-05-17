#!/bin/bash

nohup python3 manage.py runserver 0.0.0.0:9123  --insecure &

# 启动Django Q cluster
nohup python3 manage.py qcluster &
