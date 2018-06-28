# -*- coding: UTF-8 -*-
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('default')


class ExceptionLoggingMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        import traceback
        logger.error(traceback.format_exc())
