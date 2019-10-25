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

import logging

from aliyunsdkcore.auth.signers.signer import Signer

logger = logging.getLogger(__name__)


class StsTokenSigner(Signer):
    def __init__(self, sts_credential):
        self._credential = sts_credential

    def sign(self, region_id, request):
        sts_cred = self._credential
        if request.get_style() == 'RPC':
            request.add_query_param("SecurityToken", sts_cred.sts_token)
        else:
            request.add_header("x-acs-security-token", sts_cred.sts_token)
        header = request.get_signed_header(region_id, sts_cred.sts_access_key_id,
                                           sts_cred.sts_access_key_secret)
        url = request.get_url(region_id, sts_cred.sts_access_key_id, sts_cred.sts_access_key_secret)
        return header, url
