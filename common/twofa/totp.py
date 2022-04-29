from django.db import transaction
from django.conf import settings
from qrcode import QRCode, constants
from sql.models import TwoFactorAuthConfig
from . import TwoFactorAuthBase
import traceback
import logging
import pyotp
import os

logger = logging.getLogger('default')


class TOTP(TwoFactorAuthBase):
    """Time-based One-time Password，适用Google身份验证器等App"""

    def __init__(self, user=None):
        super(TOTP, self).__init__(user=user)
        self.user = user

    def verify(self, opt):
        """校验一次性验证码"""
        result = {'status': 0, 'msg': 'ok'}
        secret_key = TwoFactorAuthConfig.objects.get(username=self.user.username).secret_key
        t = pyotp.TOTP(secret_key)
        status = t.verify(opt)
        result['status'] = 0 if status else 1
        result['msg'] = 'ok' if status else '验证码不正确！'
        return result

    def enable(self):
        """启用2fa"""
        result = {'status': 0, 'msg': 'ok', 'src': ''}

        qrcode_path = os.path.join(settings.STATICFILES_DIRS[0], '2fa_qrcode')
        if not os.path.exists(qrcode_path):
            os.mkdir(qrcode_path)

        # 生成用户secret_key
        secret_key = pyotp.random_base32(32)

        # 生成二维码
        qr_data = pyotp.totp.TOTP(secret_key).provisioning_uri(self.user.username, issuer_name="Archery")
        qrcode = QRCode(version=1, error_correction=constants.ERROR_CORRECT_L,
                        box_size=6, border=4)
        try:
            qrcode.add_data(qr_data)
            qrcode.make(fit=True)
            qr_img = qrcode.make_image()
            qrcode_file = os.path.join(qrcode_path, secret_key + '.png')
            qr_img.save(qrcode_file)
        except Exception as msg:
            result['status'] = 1
            result['msg'] = str(msg)
            logger.error(traceback.format_exc())
        else:
            try:
                with transaction.atomic():
                    # 删除旧的2fa配置和文件
                    self.disable()
                    # 创建新的2fa配置
                    TwoFactorAuthConfig.objects.create(
                        username=self.user.username,
                        auth_type=self.auth_type,
                        secret_key=secret_key,
                        qrcode=f'2fa_qrcode/{secret_key}.png',
                        user=self.user
                    )
            except Exception as msg:
                result['status'] = 1
                result['msg'] = str(msg)
                logger.error(traceback.format_exc())
            else:
                result['src'] = f'2fa_qrcode/{secret_key}.png'

        return result

    @property
    def auth_type(self):
        """返回认证类型"""
        return "totp"
