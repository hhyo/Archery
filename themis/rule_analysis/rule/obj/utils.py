# -*- coding: utf-8 -*-

import re


def regex_time(time):
    pattern = re.compile('((((19|20)?\d{2})[-/]*((1[0-2])|(0?[1-9]))' + 
                '[-/]*(([12][0-9])|(3[01])|(0?[1-9])))|(((1[0-2])|' +
                '(0?[1-9]))[-/]*(([12][0-9])|(3[01])|(0?[1-9]))[-/' +
                ']*((19|20)?\d{2}))|((([12][0-9])|(3[01])|(0?[1-9])' +
                ')[-/]*((1[0-2])|(0?[1-9]))[-/]*((19|20)?\d{2})))(' +
                '\s{1,}([01]?\d|2[0-3]):?([0-5]?\d):?([0-5]?\d))?$')
    if not pattern.match(time):
        return True
    return False


def regex_date(date):
    pattern = re.compile('((19|20)?\d{2})((1[0-2])|(0[1-9]))(([12][0-9]' +
                ')|(3[01])|(0[1-9]))(([01]\d|2[0-3])([0-5]\d)([0-5]\d))?$')
    if pattern.search(date):
        return True
    return False


def regex_phone(phone):
    pattern = re.compile('(\+?0?86\-?)?1[3|4|5|7|8][0-9]\d{8}$')
    if pattern.match(phone):
        return True
    return False


def regex_fax(fax):
    # 匹配传真
    pattern = re.compile('(((0?10)|(0?[2-9]\d{2,3}))[-\s]?)?[1-9]\d{6,7}$')
    if pattern.match(fax):
        return True
    return False


def regex_bank_account(account):
    # 匹配银行账户
    pattern = re.compile('(\d{16}|\d{19}|\d{12})$')
    if pattern.match(account):
        return True
    return False


def regex_head(head):
    pattern = re.compile('0\d*')
    if pattern.match(head):
        return True
    return False


def regex_char_bar_blackslash(string):
    # 不是日期，并且包含字母
    # 匹配不是日期并且包含字母，2016-10-25 16:24:33，2016/10/25，2016/10/25 +8
    pattern = re.compile('[^0-9\-\/\+\:\s]')
    if pattern.search(string):
        return True
    return False


def regex_date_bar_blackslash(string):
    # 匹配日期
    pattern = re.compile('[\-\/]')
    if pattern.search(string):
        return True
    return False

