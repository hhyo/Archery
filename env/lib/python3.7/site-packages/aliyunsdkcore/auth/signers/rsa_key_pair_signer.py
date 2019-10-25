# coding:utf-8
import json
import time
import logging
import socket

from aliyunsdkcore.auth.signers.signer import Signer
from aliyunsdkcore.acs_exception import error_code
from aliyunsdkcore.acs_exception import error_msg
from aliyunsdkcore.acs_exception import exceptions
from aliyunsdkcore.request import RpcRequest
from aliyunsdkcore.auth.algorithm import sha_hmac256

logger = logging.getLogger(__name__)


class RsaKeyPairSigner(Signer):
    _MIN_SESSION_PERIOD = 900
    _MAX_SESSION_PERIOD = 3600

    def __init__(self, credential, region_id, debug=False):
        if credential.session_period < self._MIN_SESSION_PERIOD or \
           credential.session_period > self._MAX_SESSION_PERIOD:
            raise exceptions.ClientException(
                error_code.SDK_INVALID_SESSION_EXPIRATION,
                error_msg.get_msg('SDK_INVALID_SESSION_EXPIRATION').format(
                    self._MIN_SESSION_PERIOD,
                    self._MAX_SESSION_PERIOD))
        credential.region_id = region_id
        self._public_key_id = credential.public_key_id
        self._private_key = credential.private_key
        self._session_period = credential.session_period
        self._last_update_time = 0
        # self._schedule_interval = credential.session_period if debug \
        #     else max(credential.session_period * 0.8, 5)
        from aliyunsdkcore.client import AcsClient
        self._sts_client = AcsClient(
            self._public_key_id, self._private_key, credential.region_id)
        self._session_credential = None

    def sign(self, region_id, request):
        self._check_session_credential()
        session_ak, session_sk = self._session_credential
        header = request.get_signed_header(region_id, session_ak, session_sk)
        url = request.get_url(region_id, session_ak, session_sk)
        return header, url

    def _check_session_credential(self):
        if self._session_credential is None:
            self._get_session_ak_and_sk()
            return

        now = int(time.time())
        if now - self._last_update_time > (self._session_period * 0.8):
            self._get_session_ak_and_sk()

    def _get_session_ak_and_sk(self):
        request = GetSessionAkRequest()
        request.set_method("GET")
        request.set_duration_seconds(self._session_period)

        try:
            response_str = self._sts_client.do_action_with_exception(request)
            response = json.loads(response_str.decode('utf-8'))
            session_ak = str(response.get(
                "SessionAccessKey").get("SessionAccessKeyId"))
            session_sk = str(response.get(
                "SessionAccessKey").get("SessionAccessKeySecret"))

            self._session_credential = session_ak, session_sk
            self._last_update_time = int(time.time())
        except exceptions.ServerException as srv_ex:
            if srv_ex.error_code == 'InvalidAccessKeyId.NotFound' or \
               srv_ex.error_code == 'SignatureDoesNotMatch':
                raise exceptions.ClientException(error_code.SDK_INVALID_CREDENTIAL,
                                                 error_msg.get_msg('SDK_INVALID_CREDENTIAL'))
            else:
                raise


class GetSessionAkRequest(RpcRequest):
    def __init__(self):
        RpcRequest.__init__(self, product='Sts', version='2015-04-01',
                            action_name='GenerateSessionAccessKey',
                            signer=sha_hmac256)
        self.set_protocol_type('https')

    def get_duration_seconds(self):
        return self.get_query_params().get("DurationSeconds")

    def set_duration_seconds(self, duration_seconds):
        self.add_query_param('DurationSeconds', duration_seconds)

    def get_public_key_id(self):
        return self.get_query_params().get('PublicKeyId')

    def set_public_key_id(self, public_key_id):
        self.add_query_param('PublicKeyId', public_key_id)
