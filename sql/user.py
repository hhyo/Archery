# -*- coding: UTF-8 -*-
import simplejson as json
from common.utils.permission import superuser_required
from common.utils.extend_json_encoder import ExtendJSONEncoder
from django.http import HttpResponse
from .models import Users


@superuser_required
def lists(request):
    """获取用户列表"""
    users = Users.objects.order_by('username')
    users = users.values("id", "username", "display", "is_superuser", "is_staff", "is_active", "email")

    rows = [row for row in users]

    result = {"status": 0, "msg": "ok", "data": rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
