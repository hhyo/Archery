# -*- coding: utf-8 -*-

from pymysqlreplication.tests.test_basic import *
from pymysqlreplication.tests.test_data_type import *
from pymysqlreplication.tests.test_data_objects import *

if __name__ == "__main__":
    if sys.version_info < (2, 7):
        import unittest2 as unittest
    else:
        import unittest
    unittest.main()
