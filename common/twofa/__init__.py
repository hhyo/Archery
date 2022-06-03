from sql.models import TwoFactorAuthConfig


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
        try:
            TwoFactorAuthConfig.objects.get(user=self.user).delete()
        except TwoFactorAuthConfig.DoesNotExist as e:
            result = {'status': 0, 'msg': str(e)}
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
