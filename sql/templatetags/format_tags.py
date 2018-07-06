# -*- coding: UTF-8 -*-
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


# 替换换行符
@register.simple_tag
def format_str(str):
    # 换行
    return mark_safe(str.replace(',', '<br/>'))
