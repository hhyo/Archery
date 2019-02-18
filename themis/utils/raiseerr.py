# -*- coding: UTF-8 -*-

import datetime


class APIError(Exception):
    time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def __init__(self, message, errcode, timespan=time):
        super(APIError, self).__init__()
        self.message = message
        self.errcode = errcode
        self.timespan = timespan


# test
if __name__ == "__main__":
    try:
        raise APIError("result error", 1000)
    except APIError as e:
        r = {
            'message': e.message,
            'errcode': e.errcode,
            'timespan': e.timespan
        }
        print(r)
