# -*- coding: UTF-8 -*-

import datetime
import logging
from logging.handlers import RotatingFileHandler, SysLogHandler
import traceback
import threading
import os


def get_logger():
    return logging.getLogger('default')
# def get_logger(name="logs/sql_audit.log"):
#     os.path.exists(name)
#     logger = logging.getLogger()
#     handler = logging.StreamHandler()
#     formatter = logging.Formatter("%(asctime)s %(process)d %(levelname)s %(thread)d - %(funcName)s %(filename)s:%(lineno)d %(message)s")
#     handler.setFormatter(formatter)
#     logger.addHandler(handler)
#
#     return logger
