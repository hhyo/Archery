from datetime import time, timedelta, timezone
from unittest import TestCase

import simplejson

from common.utils.extend_json_encoder import ExtendJSONEncoderFTime


class PostgreSQLTimeJSONTest(TestCase):
    def encode_row(self, value):
        payload = simplejson.dumps(
            {"rows": [[value]]},
            cls=ExtendJSONEncoderFTime,
            use_decimal=False,
            bigint_as_string=True,
        )
        return simplejson.loads(payload)["rows"][0][0]

    def test_time_query_value(self):
        self.assertEqual(self.encode_row(time(12, 35)), "12:35:00")

    def test_timetz_query_value_preserves_fraction_and_offset(self):
        value = time(12, 35, microsecond=123000, tzinfo=timezone(timedelta(hours=8)))
        self.assertEqual(self.encode_row(value), "12:35:00.123000+08:00")
