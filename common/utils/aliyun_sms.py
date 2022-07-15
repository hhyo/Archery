# -*- coding: utf-8 -*-
from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from common.config import SysConfig
import traceback
import logging

logger = logging.getLogger("default")


class AliyunSMS:
    def __init__(self):
        all_config = SysConfig()
        self.access_key_id = all_config.get("aliyun_access_key_id", "")
        self.access_key_secret = all_config.get("aliyun_access_key_secret", "")
        self.sign_name = all_config.get("aliyun_sign_name", "")
        self.template_code = all_config.get("aliyun_template_code", "")
        self.variable_name = all_config.get("aliyun_variable_name", "code")

    def create_client(self):
        config = open_api_models.Config(
            access_key_id=self.access_key_id, access_key_secret=self.access_key_secret
        )
        config.endpoint = f"dysmsapi.aliyuncs.com"
        return Dysmsapi20170525Client(config)

    def send_code(self, **kwargs):
        result = {"status": 0, "msg": "ok"}
        client = AliyunSMS.create_client(self)

        send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
            phone_numbers=kwargs["phone"],
            sign_name=self.sign_name,
            template_code=self.template_code,
            template_param=f"{{{self.variable_name}: '{kwargs['otp']}'}}",
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = client.send_sms_with_options(send_sms_request, runtime)
            if response.body.code != "OK":
                result["status"] = 1
                result["msg"] = response.body.message
        except Exception as e:
            result["status"] = 1
            result["msg"] = str(e)
            logger.error(str(e))
            logger.error(traceback.format_exc())

        return result

    @property
    def provider(self):
        """返回服务商代码"""
        return "aliyun"
