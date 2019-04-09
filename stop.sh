#!/bin/bash

port=${1:-8000}
ps -ef|grep gunicorn|grep ${port}|awk '{print $2}'|xargs kill -15

ps -ef|grep qcluster|awk '{print $2}'|xargs kill -15
#deactivate

