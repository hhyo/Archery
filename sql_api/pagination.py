from rest_framework.views import Response
from rest_framework.pagination import PageNumberPagination
from collections import OrderedDict
from django.conf import settings


class CustomizedPagination(PageNumberPagination):
    """
    自定义分页器
    """
    page_size = settings.REST_FRAMEWORK['PAGE_SIZE'] if 'PAGE_SIZE' in settings.REST_FRAMEWORK.keys() else 20
    page_query_param = 'page'
    page_size_query_param = 'size'
    max_page_size = None

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', data.get('count', self.page.paginator.count)),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data.get('data', data))
        ]))
