# -*- coding: UTF-8 -*-
import base64
import simplejson as json

from decimal import Decimal
from datetime import datetime, date, timedelta
from functools import singledispatch
from ipaddress import IPv4Address, IPv6Address
from uuid import UUID
from bson.objectid import ObjectId
from bson.timestamp import Timestamp


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
    return o.__str__()


@convert.register(Decimal)
def _(o):
    return str(o)


@convert.register(memoryview)
def _(o):
    return str(o)


@convert.register(set)
def _(o):
    return list(o)


@convert.register(UUID)
def _(o):
    return str(o)


@convert.register(IPv4Address)
def _(o):
    return str(o)


@convert.register(IPv6Address)
def _(o):
    return str(o)


@convert.register(ObjectId)
def _(o):
    return str(o)


@convert.register(Timestamp)
def _(o):
    return str(o)


class ExtendJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return convert(obj)
        except TypeError:
            return super(ExtendJSONEncoder, self).default(obj)


class ExtendJSONEncoderFTime(json.JSONEncoder):

    def default(self, obj):
        try:
            if isinstance(obj, datetime):
                return obj.isoformat(' ')
            else:
                return convert(obj)
        except TypeError:
            return super(ExtendJSONEncoderFTime, self).default(obj)


# 使用simplejson处理形如 b'\xaa' 的bytes类型数据会失败，但使用json模块构造这个对象时不能使用bigint_as_string方法
import json
class ExtendJSONEncoderBytes(json.JSONEncoder):
    def default(self, obj): 
        try:
            # 使用convert.register处理会报错 ValueError: Circular reference detected
            # 不是utf-8格式的bytes格式需要先进行base64编码转换
            if isinstance(obj, bytes):
                try:
                    return o.decode('utf-8')
                except:
                    return base64.b64encode(obj).decode('utf-8')
            else:
                return convert(obj)
        except TypeError:
            print(type(obj))
            return super(ExtendJSONEncoderBytes, self).default(obj)

