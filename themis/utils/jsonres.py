# -*- coding: UTF-8 -*-
from django.http import HttpResponse
import simplejson as json

from common.utils.extend_json_encoder import ExtendJSONEncoder
from themis.utils.raiseerr import APIError


def temRes(func):
    def _jsonRes(request, *args, **kwargs):
        try:
            response = func(request, *args, **kwargs)
            if not isinstance(response, dict):
                raise APIError(u"类型错误", 10000)
            if 'message' not in response:
                response.update({'message': ''})
            if 'errcode' not in response:
                response.update({'errcode': 0})
        except APIError as e:
            response = {'message': e.message, 'errcode': e.errcode}
        return HttpResponse(json.dumps(response, cls=ExtendJSONEncoder, bigint_as_string=True),
                            content_type='application/json')

    return _jsonRes
