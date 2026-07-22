from sql.models import InstanceAccount

SUPPORTED_MANAGEMENT_DB_TYPE = ["mysql", "mongo", "pgsql", "gaussdb"]


def get_instanceaccount_unique_value(db_type: str, account: InstanceAccount) -> str:
    """根据存储的实例账号数据，返回该实例类型的唯一值"""
    if db_type == "mysql":
        return f"`{account['user']}`@`{account['host']}`"
    elif db_type == "mongo":
        return f"{account['db_name']}.{account['user']}"
    elif db_type in ("pgsql", "gaussdb"):
        return f"{account['user']}@{account.get('host', '%')}"
    return f"{account['user']}@{account.get('host', '%')}"


def get_instanceaccount_unique_key(db_type: str) -> str:
    if db_type == "mysql":
        return "user_host"
    elif db_type == "mongo":
        return "db_name_user"
    elif db_type in ("pgsql", "gaussdb"):
        return "user_host"
    return "user_host"
