from rest_framework.renderers import JSONRenderer
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.views import exception_handler
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


# 导入控制返回的JSON格式的类
class CustomRenderer(JSONRenderer):
    # 重构render方法
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context:
            response = renderer_context["response"]
            if response.status_code < 400:
                # 如果正常返回，则设置默认的消息为“请求成功”。
                msg = data.pop("msg", "请求成功")
                code = response.status_code
                ret = {"msg": msg, "code": code, "data": data}
            else:
                # 如果出现异常，则提取异常详细信息以及状态码。
                msg = str(data.get("msg", data.get("detail", "请求失败")))
                code = response.status_code
                ret = {"msg": msg, "code": code, "data": None}
            return super().render(ret, accepted_media_type, renderer_context)
        else:
            return super().render(data, accepted_media_type, renderer_context)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, AuthenticationFailed):
        detail = exc.detail
        custom_response_data = {"msg": detail, "code": exc.status_code, "data": None}
        response.data = custom_response_data
        response.status_code = exc.status_code

    elif isinstance(exc, InvalidToken) or isinstance(exc, TokenError):
        detail = str(exc)
        custom_response_data = {"msg": detail, "code": exc.status_code, "data": None}
        response.data = custom_response_data
        response.status_code = exc.status_code
    return response
