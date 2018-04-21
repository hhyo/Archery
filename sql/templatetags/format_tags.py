# -*- coding: UTF-8 -*-
from django import template

register = template.Library()


# 替换换行符
@register.simple_tag
def format_str(str):
    # 替换所有的换行符
    str = str.replace('\r', '<br>')
    str = str.replace('\n', '<br>')
    # 替换所有的空格
    str = str.replace('\s', '&nbsp;')
    # 逗号替换成换行符
    str = str.replace(',', '<br>')

    return str
