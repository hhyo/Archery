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
#
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# coding=utf-8

"""
Acs error message module.
"""

SDK_ENDPOINT_MANAGEMENT_DOC_HTML = "https://www.alibabacloud.com/help/doc-detail/92074.htm"

INVALID_REGION_ID = "No such region '{region_id}'. Please check your region ID."

ENDPOINT_NO_REGION = "No endpoint in the region '{region_id}' for product '{product_code}'.\n" +\
                     "You can set an endpoint for your request explicitly.{more}\n" +\
                     "See " + SDK_ENDPOINT_MANAGEMENT_DOC_HTML + "\n"

ENDPOINT_NO_PRODUCT = "No endpoint for product '{product_code}'.\n" +\
                      "Please check the product code, " +\
                      "or set an endpoint for your request explicitly.\n" +\
                      "See " + SDK_ENDPOINT_MANAGEMENT_DOC_HTML + "\n"

__dict = dict(
    SDK_INVALID_REGION_ID='Can not find endpoint to access.',
    SDK_SERVER_UNREACHABLE='Unable to connect server',
    SDK_INVALID_REQUEST='The request is not a valid AcsRequest.',
    SDK_MISSING_ENDPOINTS_FILER='Internal endpoints info is missing.',
    SDK_UNKNOWN_SERVER_ERROR="Can not parse error message from server response.",
    SDK_INVALID_CREDENTIAL="Need a ak&secret pair or public_key_id&private_key pair to auth.",
    SDK_INVALID_SESSION_EXPIRATION="Session expiration must between {0} and {1} seconds")


def get_msg(code):
    return __dict.get(code)
