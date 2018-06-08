# -*- coding: UTF-8 -*-
import simplejson as json

from datetime import datetime, date
from decimal import Decimal
from functools import singledispatch


class MyClass:
    def __init__(self, value):
        self._value = value

    def get_value(self):
        return self._value


# 创建非内置类型的实例
mc = MyClass('i am class MyClass ')
dm = Decimal('11.11')
dt = datetime.now()
dat = date.today()


@singledispatch
def convert(o):
    raise TypeError('can not convert type')


@convert.register(datetime)
def _(o):
    return o.strftime('%Y-%m-%d %H:%M:%S')


@convert.register(date)
def _(o):
    return o.strftime('%Y-%m-%d')


# @convert.register(Decimal)
# def _(o):
#     return float(o)


@convert.register(MyClass)
def _(o):
    return o.get_value()


class ExtendJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return convert(obj)
        except TypeError:
            return super(ExtendJSONEncoder, self).default(obj)


data = {
    'mc': mc,
    'dm': dm,
    'dt': dt,
    'dat': dat,
    'bigint': 988983860501598208
}

#print(json.dumps(data, cls=ExtendJSONEncoder, bigint_as_string=True))
