#!/bin/bash

gunicorn -w 2 --env DJANGO_SETTINGS_MODULE=archer.settings --error-logfile=/tmp/archer.err -b 192.168.1.12:8888 archer.wsgi:application
