# coding:utf-8

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

import time
import json
import logging

from aliyunsdkcore.auth.signers.signer import Signer
from aliyunsdkcore.auth.signers.access_key_signer import AccessKeySigner
from aliyunsdkcore.acs_exception import error_code
from aliyunsdkcore.acs_exception import exceptions
from aliyunsdkcore.auth.credentials import RamRoleArnCredential
from aliyunsdkcore.auth.credentials import AccessKeyCredential
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.compat import ensure_string

logger = logging.getLogger(__name__)


class RamRoleArnSigner(Signer):
    _SESSION_PERIOD = 3600
    _REFRESH_SCALE = 0.8
    _RETRY_DELAY_FAST = 3
    _PRIORITY = 1

    def __init__(self, credential, do_action_api):
        if isinstance(credential, RamRoleArnCredential):
            self._credential = credential
            self._doAction = do_action_api
            self._last_update_time = 0
            if len(self._credential.session_role_name) == 0:
                self._credential.session_role_name = "aliyun-python-sdk-" + str(time.time())

    def sign(self, region_id, request):
        self._check_session_credential()
        session_ak, session_sk, token = self._session_credential
        if request.get_style() == 'RPC':
            request.add_query_param("SecurityToken", token)
        else:
            request.add_header("x-acs-security-token", token)
        header = request.get_signed_header(region_id, session_ak, session_sk)
        url = request.get_url(region_id, session_ak, session_sk)
        return header, url

    def _check_session_credential(self):
        now = int(time.time())
        if now - self._last_update_time > (self._SESSION_PERIOD * self._REFRESH_SCALE):
            self._refresh_session_ak_and_sk()

    def _refresh_session_ak_and_sk(self):
        request = CommonRequest(product="Sts", version='2015-04-01', action_name='AssumeRole')
        request.set_method('POST')
        request.set_protocol_type('https')
        request.add_query_param('RoleArn', self._credential.role_arn)
        request.add_query_param('RoleSessionName', self._credential.session_role_name)
        request.add_query_param('DurationSeconds', self._SESSION_PERIOD)
        request.set_accept_format('JSON')

        access_key_credential = AccessKeyCredential(self._credential.sts_access_key_id,
                                                    self._credential.sts_access_key_secret)
        signer = AccessKeySigner(access_key_credential)

        status, headers, body, exception = self._doAction(request, signer)
        if status == 200:
            response = json.loads(body.decode('utf-8'))
            session_ak = response.get("Credentials").get("AccessKeyId")
            session_sk = response.get("Credentials").get("AccessKeySecret")
            token = response.get("Credentials").get("SecurityToken")
            self._session_credential = session_ak, session_sk, token
            self._last_update_time = int(time.time())
        else:
            code = error_code.SDK_GET_SESSION_CREDENTIAL_FAILED
            message = "refresh session token failed, server return: " + ensure_string(body)
            http_status = status

            raise exceptions.ServerException(code, message, http_status)
