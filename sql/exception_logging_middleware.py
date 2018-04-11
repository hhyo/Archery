# -*- coding: UTF-8 -*-
import logging

logger = logging.getLogger('default')


class ExceptionLoggingMiddleware(object):
    def process_exception(self, request, exception):
        import traceback
        logger.error(traceback.format_exc())
