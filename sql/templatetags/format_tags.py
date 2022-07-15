# -*- coding: UTF-8 -*-
from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

register = template.Library()


# 替换换行符
@register.simple_tag
def format_str(string):
    # 换行
    return mark_safe(string.replace(",", "<br/>").replace("\n", "<br/>"))


# split
@register.filter
@stringfilter
def split(string, sep):
    """Return the string split by sep.
    Example usage: {{ value|split:"/" }}
    """
    return string.split(sep)


# in
@register.filter
def is_in(var, args):
    return True if str(var) in args.split(",") else False


@register.filter
def key_value(data, key):
    try:
        return data[key]
    except KeyError:
        return ""
