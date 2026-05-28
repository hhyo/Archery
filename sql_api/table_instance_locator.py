import importlib
from typing import Dict, Iterable, List

from django.conf import settings

from sql.engines import get_engine
from sql.models import Instance
from sql.utils.sql_utils import filter_db_list


def _normalize_table_name(row) -> str:
    if isinstance(row, str):
        return row
    if isinstance(row, (list, tuple)) and row:
        return str(row[0])
    if isinstance(row, dict):
        if "name" in row:
            return str(row["name"])
        if row:
            return str(next(iter(row.values())))
    return str(row)


def default_table_instance_locator(
    table_name: str, instances: Iterable[Instance], **kwargs
) -> List[Dict]:
    print(f"默认的table instance locator被调用，table_name={table_name}，实例列表={instances}")  # 调试日志
    result = []
    lower_table_name = table_name.lower()

    for instance in instances:
        query_engine = get_engine(instance=instance)
        databases = query_engine.get_all_databases()
        print(f"查询实例{instance}的数据库列表，结果={databases.rows}，错误={databases.error}")  # 调试日志
        if databases.error:
            continue

        db_list = filter_db_list(
            db_list=databases.rows,
            db_name_regex=query_engine.instance.show_db_name_regex,
            is_match_regex=True,
        )
        db_list = filter_db_list(
            db_list=db_list,
            db_name_regex=query_engine.instance.denied_db_name_regex,
            is_match_regex=False,
        )

        for db_name in db_list:
            tables = query_engine.get_all_tables(db_name=db_name)
            if tables.error:
                continue

            matched_table_name = None
            for tb in tables.rows:
                normalized_tb = _normalize_table_name(tb)
                if normalized_tb.lower() == lower_table_name:
                    matched_table_name = normalized_tb
                    break

            if matched_table_name is not None:
                result.append(
                    {
                        "id": instance.id,
                        "name": instance.instance_name,
                        "db_type": instance.db_type,
                        "db_name": db_name,
                        "table_name": matched_table_name,
                    }
                )
                break

    return result


def _load_custom_locator():
    locator_path = getattr(settings, "TABLE_INSTANCE_LOCATOR", "")
    if not locator_path:
        return None

    try:
        module, fn_name = locator_path.split(":", 1)
        locator = getattr(importlib.import_module(module), fn_name)
    except Exception as e:
        raise RuntimeError(f"自定义TABLE_INSTANCE_LOCATOR加载失败: {e}")

    if not callable(locator):
        raise RuntimeError("自定义TABLE_INSTANCE_LOCATOR不是可调用对象")
    return locator


def resolve_table_instances(table_name: str, instances: Iterable[Instance], **kwargs):
    locator = _load_custom_locator() or default_table_instance_locator
    result = locator(table_name=table_name, instances=instances, **kwargs)
    if not isinstance(result, list):
        raise ValueError("table instance locator必须返回list")

    normalized = []
    for item in result:
        if not isinstance(item, dict):
            raise ValueError("table instance locator返回的元素必须是dict")
        if "name" not in item or not item["name"]:
            raise ValueError("table instance locator返回的实例字典必须包含name")
        item_out = {
            "id": item.get("id", 0),
            "name": item["name"],
            "db_type": item.get("db_type", ""),
            "db_name": item.get("db_name", ""),
        }
        if item.get("table_name"):
            item_out["table_name"] = item["table_name"]
        normalized.append(item_out)
    return normalized
