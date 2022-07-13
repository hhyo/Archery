# -*- coding: utf-8 -*-
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
    TencentCloudSDKException,
)
from tencentcloud.sms.v20210111 import sms_client, models
from common.config import SysConfig
import traceback
import logging

logger = logging.getLogger("default")


class TencentSMS:
    def __init__(self):
        all_config = SysConfig()
        self.secret_id = all_config.get("tencent_secret_id", "")
        self.secret_key = all_config.get("tencent_secret_key", "")
        self.sign_name = all_config.get("tencent_sign_name", "")
        self.template_id = all_config.get("tencent_template_id", "")
        self.sdk_appid = all_config.get("tencent_sdk_appid", "")

    def create_client(self):
        cred = credential.Credential(self.secret_id, self.secret_key)
        client = sms_client.SmsClient(cred, "ap-guangzhou")
        return client

    def send_code(self, **kwargs):
        result = {"status": 0, "msg": "ok"}
        client = TencentSMS.create_client(self)

        try:
            req = models.SendSmsRequest()
            req.SmsSdkAppId = self.sdk_appid
            req.SignName = self.sign_name
            req.TemplateId = self.template_id
            req.TemplateParamSet = [kwargs["otp"]]
            req.PhoneNumberSet = [kwargs["phone"]]

            resp = client.SendSms(req)
            if resp.SendStatusSet[0].Code != "Ok":
                result["status"] = 1
                result["msg"] = resp.SendStatusSet[0].Message
        except TencentCloudSDKException as e:
            result["status"] = 1
            result["msg"] = str(e)
            logger.error(str(e))
            logger.error(traceback.format_exc())

        return result

    @property
    def provider(self):
        """返回服务商代码"""
        return "tencent"
