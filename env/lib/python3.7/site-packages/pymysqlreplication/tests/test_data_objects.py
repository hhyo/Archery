import sys
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from pymysqlreplication.column import Column
from pymysqlreplication.table import Table
from pymysqlreplication.event import GtidEvent

from pymysqlreplication.tests import base

__all__ = ["TestDataObjects"]


class TestDataObjects(base.PyMySQLReplicationTestCase):
    def ignoredEvents(self):
        return [GtidEvent]

    def test_column_is_primary(self):
        col = Column(1,
                     {"COLUMN_NAME": "test",
                      "COLLATION_NAME": "utf8_general_ci",
                      "CHARACTER_SET_NAME": "UTF8",
                      "COLUMN_COMMENT": "",
                      "COLUMN_TYPE": "tinyint(2)",
                      "COLUMN_KEY": "PRI"},
                     None)
        self.assertEqual(True, col.is_primary)

    def test_column_not_primary(self):
        col = Column(1,
                     {"COLUMN_NAME": "test",
                      "COLLATION_NAME": "utf8_general_ci",
                      "CHARACTER_SET_NAME": "UTF8",
                      "COLUMN_COMMENT": "",
                      "COLUMN_TYPE": "tinyint(2)",
                      "COLUMN_KEY": ""},
                     None)
        self.assertEqual(False, col.is_primary)

    def test_column_serializable(self):
        col = Column(1,
                     {"COLUMN_NAME": "test",
                      "COLLATION_NAME": "utf8_general_ci",
                      "CHARACTER_SET_NAME": "UTF8",
                      "COLUMN_COMMENT": "",
                      "COLUMN_TYPE": "tinyint(2)",
                      "COLUMN_KEY": "PRI"},
                     None)

        serialized = col.serializable_data()
        self.assertIn("type", serialized)
        self.assertIn("name", serialized)
        self.assertIn("collation_name", serialized)
        self.assertIn("character_set_name", serialized)
        self.assertIn("comment", serialized)
        self.assertIn("unsigned", serialized)
        self.assertIn("type_is_bool", serialized)
        self.assertIn("is_primary", serialized)

        self.assertEqual(col, Column(**serialized))

    def test_table(self):
        tbl = Table(1, "test_schema", "test_table", [], [])

        serialized = tbl.serializable_data()
        self.assertIn("table_id", serialized)
        self.assertIn("schema", serialized)
        self.assertIn("table", serialized)
        self.assertIn("columns", serialized)
        self.assertIn("column_schemas", serialized)

        self.assertEqual(tbl, Table(**serialized))


if __name__ == "__main__":
    unittest.main()
