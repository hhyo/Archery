# -*- coding: UTF-8 -*-
from . import EngineBase
from .models import ResultSet


class MqttEngine(EngineBase):
    name = "MQTT"
    info = "MQTT engine"

    def test_connection(self):
        raise NotImplementedError

    def get_all_databases(self, **kwargs):
        db_name = self.db_name or "default"
        return ResultSet(rows=[{"value": db_name, "text": db_name}])

    def get_all_tables(self, db_name, **kwargs):
        return ResultSet(rows=[])
