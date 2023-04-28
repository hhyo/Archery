from django_cas_ng.backends import CASBackend
from django.contrib.auth.models import User
from django.core.cache import cache
from common.config import SysConfig
from django.conf import settings


class CustomCASBackend(CASBackend):
    def configure_user(self, user: User):
        """
        该函数在CAS验证完成后，调用此方法补充信息
        """
        if not user.email and settings.ENABLE_LDAP_DATA_COMPLETION:
            from django_auth_ldap.backend import LDAPBackend
            from common.utils.feishu_api_new import FSMessage

            #  从缓存里获取  LDAP  验证结果
            ldap_user = cache.get(user.username)
            if ldap_user is None:
                #  如果缓存里没有，就进行  LDAP  验证并缓存结果
                backend = LDAPBackend()
                ldap_user = backend.populate_user(user.username)
                cache.set(user.username, ldap_user)

            #  当  LDAP  验证失败时，返回  None
            if not ldap_user:
                return None

            try:
                fs = FSMessage()
                email = ldap_user.ldap_user.attrs["mail"][0]
                user.email = email
                user.display = ldap_user.ldap_user.attrs["cn"][0]
                sys_config = SysConfig()
                if sys_config.get("feishu_appid"):
                    user.feishu_open_id = fs.get_user_id(email)
                user.save()
            except Exception:
                #  当飞书请求失败时，返回  None
                return None
