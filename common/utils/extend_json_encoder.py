# -*- coding: UTF-8 -*-
import simplejson as json

from datetime import datetime, date, timedelta
from functools import singledispatch


@singledispatch
def convert(o):
    raise TypeError('can not convert type')


@convert.register(datetime)
def _(o):
    return o.strftime('%Y-%m-%d %H:%M:%S')


@convert.register(date)
def _(o):
    return o.strftime('%Y-%m-%d')


@convert.register(timedelta)
def _(o):
    return o.total_seconds()


# @convert.register(Decimal)
# def _(o):
#     return float(o)


class ExtendJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return convert(obj)
        except TypeError:
            return super(ExtendJSONEncoder, self).default(obj)
