# -*- coding: UTF-8 -*-
import datetime
import logging
from logging.handlers import RotatingFileHandler
import traceback
import threading
import os


def get_logger(name="logs/sql_audit.log"):
    os.path.exists(name)
    logger = logging.getLogger()
    handler = RotatingFileHandler(filename=os.path.join('./logs', __name__ + '.log'), maxBytes=5 * 1024 * 1024 * 1024, backupCount=5)
    formatter = logging.Formatter("%(asctime)s %(process)d %(levelname)s %(thread)d - %(funcName)s %(filename)s:%(lineno)d %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
