# -*- coding: utf-8 -*-


def mongo_query(func):
    def _wrapper(**kwargs):
        sql = func(**kwargs)
        mongo_client = kwargs.get("mongo_client")
        db_type = kwargs.get("db_type")
        tmp = kwargs.get("tmp")
        if db_type == "O":
            etl_date = kwargs.get("etl_date")
            tmp1 = kwargs.get("tmp1")
            collection_name = kwargs.get("collection_name")
            sql = sql.replace("@username@", username).\
                replace("@etl_date@", etl_date).\
                replace("@tmp@", tmp).\
                replace("@tmp1@", tmp1).\
                replace("@collection_name@", collection_name)
        elif db_type == "mysql":
            sql = sql.replace("@schema_name@", schema).\
                replace("@tmp@", tmp)
        mongo_client.db.command("eval", sql, nolock=True)
        return True
    return _wrapper