# -*- coding: UTF-8 -*-

import datetime
import logging
from logging.handlers import RotatingFileHandler, SysLogHandler
import traceback
import threading
import os


def get_logger():
    return logging.getLogger('default')
