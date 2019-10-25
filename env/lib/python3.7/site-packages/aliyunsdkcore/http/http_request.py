# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# coding=utf-8

from aliyunsdkcore.http import format_type
from aliyunsdkcore.utils import parameter_helper as helper


class HttpRequest:

    content_md5 = "Content-MD5"
    content_length = "Content-Length"
    content_type = "Content-Type"

    def __init__(self, host="", url="/", method=None, headers=None):
        self.__host = host
        self.__url = url
        self.__method = method
        self.__content_type = None
        self.__content = None
        self.__encoding = None
        self.__headers = headers or {}
        self.__body = None

    def get_host(self):
        return self.__host

    def set_host(self, host):
        self.__host = host

    def get_body(self):
        return self.__body

    def set_body(self, body):
        self.__body = body

    def get_url(self):
        return self.__url

    def set_url(self, url):
        self.__url = url

    def get_encoding(self):
        return self.__encoding

    def set_encoding(self, encoding):
        self.__encoding = encoding

    def get_content_type(self):
        return self.__content_type

    def set_content_type(self, content_type):
        self.__content_type = content_type

    def get_method(self):
        return self.__method

    def set_method(self, method):
        self.__method = method

    def get_content(self):
        return self.__content

    def get_header_value(self, name):
        return self.__headers.get(name)

    def put_header_parameter(self, key, value):
        if key is not None and value is not None:
            self.__headers[key] = value

    def remove_header_parameter(self, key):
        if key is not None:
            if key in self.__headers:
                self.__headers.pop(key)

    def set_content(self, content, encoding, format=format_type.RAW):
        self.__content = content
        if content is None:
            self.remove_header_parameter(self.content_md5)
            self.remove_header_parameter(self.content_type)
            self.remove_header_parameter(self.content_length)
            self.__content_type = None
            self.__encoding = None
        else:
            str_md5 = helper.md5_sum(content)
            content_length = len(content)
            self.__headers[self.content_md5] = str_md5
            self.__headers[self.content_length] = str(content_length)
            self.__headers[self.content_type] = format
            self.__encoding = encoding

    def get_headers(self):
        return self.__headers
