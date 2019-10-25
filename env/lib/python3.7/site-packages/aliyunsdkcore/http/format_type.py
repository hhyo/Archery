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


XML = 'XML'
JSON = 'JSON'
RAW = 'RAW'
APPLICATION_FORM = 'application/x-www-form-urlencoded'
APPLICATION_XML = 'application/xml'
APPLICATION_JSON = 'application/json'
APPLICATION_OCTET_STREAM = 'application/octet-stream'
TEXT_XML = 'text/xml'


def map_format_to_accept(format):
    if format == XML:
        return APPLICATION_XML
    if format == JSON:
        return APPLICATION_JSON
    return APPLICATION_OCTET_STREAM


def map_accept_to_format(accept):
    if accept.lower() == APPLICATION_XML or accept.lower() == TEXT_XML:
        return XML
    if accept.lower() == APPLICATION_JSON:
        return JSON
    return RAW
