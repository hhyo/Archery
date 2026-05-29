from rest_framework.response import Response


def envelope(status=0, msg="ok", data=None):
    if data is None:
        data = []
    return {"status": status, "msg": msg, "data": data}


def envelope_response(status=0, msg="ok", data=None, http_status=200):
    return Response(envelope(status=status, msg=msg, data=data), status=http_status)
