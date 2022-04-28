from sql.models import TwoFactorAuthConfig
from django.conf import settings
import os


class TwoFactorAuthBase:

    def __init__(self, user=None):
        self.user = user

    def get_captcha(self):
        """获取验证码"""

    def verify(self, opt):
        """校验一次性验证码"""

    def enable(self):
        """启用"""
        result = {'status': 1, 'msg': 'failed'}
        return result

    def disable(self):
        """禁用"""
        result = {'status': 0, 'msg': 'ok'}
        twofa = TwoFactorAuthConfig.objects.filter(user=self.user)
        if twofa:
            if twofa[0].qrcode:
                qrcode_file = os.path.join(settings.STATICFILES_DIRS[0], twofa[0].qrcode)
                os.remove(qrcode_file)
            twofa.delete()
        return result

    @property
    def auth_type(self):
        """返回认证类型"""
        return "base"


def get_authenticator(user=None, auth_type=None):
    """获取认证器"""
    if auth_type == "totp":
        from .totp import TOTP

        return TOTP(user=user)
