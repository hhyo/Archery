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
    result = []
    lower_table_name = table_name.lower()

    for instance in instances:
        query_engine = get_engine(instance=instance)
        databases = query_engine.get_all_databases()
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

            if any(
                _normalize_table_name(tb).lower() == lower_table_name
                for tb in tables.rows
            ):
                result.append(
                    {
                        "id": instance.id,
                        "name": instance.instance_name,
                        "db_type": instance.db_type,
                        "db_name": db_name,
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
        normalized.append(
            {
                "id": item.get("id", 0),
                "name": item["name"],
                "db_type": item.get("db_type", ""),
                "db_name": item.get("db_name", ""),
            }
        )
    return normalized
