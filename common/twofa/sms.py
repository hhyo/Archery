from common.utils.aliyun_sms import AliyunSMS
from django_redis import get_redis_connection
from django.db import transaction
from sql.models import TwoFactorAuthConfig
from . import TwoFactorAuthBase
from common.config import SysConfig
import traceback
import logging
import json
import time

logger = logging.getLogger("default")


class SMS(TwoFactorAuthBase):
    """短信验证码验证"""

    def __init__(self, user=None):
        super(SMS, self).__init__(user=user)
        self.user = user

        sms_provider = SysConfig().get("sms_provider", "disabled")
        if sms_provider == "aliyun":
            from common.utils.aliyun_sms import AliyunSMS

            self.client = AliyunSMS()
        elif sms_provider == "tencent":
            from common.utils.tencent_sms import TencentSMS

            self.client = TencentSMS()
        else:
            self.client = None

    def get_captcha(self, **kwargs):
        """获取验证码"""
        result = {"status": 0, "msg": "ok"}
        r = get_redis_connection("default")
        data = r.get(f"captcha-{kwargs['phone']}")
        if data:
            captcha = json.loads(data.decode("utf8"))
            if int(time.time()) - captcha["update_time"] > 60:
                if self.client:
                    result = self.client.send_code(**kwargs)
                else:
                    result = {"status": 1, "msg": "系统未配置短信服务商！"}
            else:
                result["status"] = 1
                result[
                    "msg"
                ] = f"获取验证码太频繁，请于{captcha['update_time'] - int(time.time()) + 60}秒后再试"
        else:
            if self.client:
                result = self.client.send_code(**kwargs)
            else:
                result = {"status": 1, "msg": "系统未配置短信服务商！"}
        return result

    def verify(self, otp, phone=None):
        """校验验证码"""
        result = {"status": 0, "msg": "ok"}
        if phone:
            phone = phone
        else:
            phone = TwoFactorAuthConfig.objects.get(username=self.user.username).phone

        r = get_redis_connection("default")
        data = r.get(f"captcha-{phone}")
        if not data:
            result["status"] = 1
            result["msg"] = "未获取验证码或验证码已过期！"
        else:
            captcha = json.loads(data.decode("utf8"))
            if otp != captcha["otp"]:
                result["status"] = 1
                result["msg"] = "验证码不正确！"
        return result

    def save(self, phone):
        """保存2fa配置"""
        result = {"status": 0, "msg": "ok"}

        try:
            with transaction.atomic():
                # 删除旧的2fa配置
                self.disable(self.auth_type)
                # 创建新的2fa配置
                TwoFactorAuthConfig.objects.create(
                    username=self.user.username,
                    auth_type=self.auth_type,
                    phone=phone,
                    user=self.user,
                )
        except Exception as msg:
            result["status"] = 1
            result["msg"] = str(msg)
            logger.error(traceback.format_exc())

        return result

    @property
    def auth_type(self):
        """返回认证类型"""
        return "sms"
