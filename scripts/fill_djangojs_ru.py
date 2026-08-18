#!/usr/bin/env python3
"""Extract gettext() msgids from templates/static JS and fill common djangojs.po (ru)."""
from __future__ import annotations

import re
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]
GETTEXT_RE = re.compile(r"""gettext\(\s*(['"])(.*?)\1\s*\)""", re.S)

# Standard DBA / SQL-platform Russian terminology (clear, conventional)
GLOSSARY: dict[str, str] = {
    # actions / common UI
    "操作": "Действия",
    "确定": "OK",
    "取消": "Отмена",
    "清空": "Очистить",
    "搜索": "Поиск",
    "刷新": "Обновить",
    "提交": "Отправить",
    "保存": "Сохранить",
    "删除": "Удалить",
    "编辑": "Редактировать",
    "详情": "Подробности",
    "返回": "Назад",
    "关闭": "Закрыть",
    "启用": "Включить",
    "禁用": "Отключить",
    "绑定": "Привязать",
    "验证": "Проверить",
    "查询": "Запрос",
    "导出": "Экспорт",
    "导入": "Импорт",
    "上传": "Загрузить",
    "下载": "Скачать",
    "全部": "Все",
    "重置": "Сбросить",
    "筛选": "Фильтр",
    "成功": "Успех",
    "失败": "Ошибка",
    "错误": "Ошибка",
    "警告": "Предупреждение",
    "提示": "Подсказка",
    "是": "Да",
    "否": "Нет",
    "状态": "Статус",
    "时间": "Время",
    "类型": "Тип",
    "用户": "Пользователь",
    "用户名": "Имя пользователя",
    "密码": "Пароль",
    "开始": "Начало",
    "结束": "Окончание",
    "自定义": "Произвольный",
    "本月": "Этот месяц",
    "上个月": "Прошлый месяц",
    "最近30日": "Последние 30 дней",
    "全部数据": "Все данные",
    "操作时间": "Время операции",
    "数据加载失败！": "Не удалось загрузить данные!",
    "请选择实例！": "Выберите инстанс!",
    "请选择数据库！": "Выберите базу данных!",
    "请填写SQL！": "Введите SQL!",
    # workflow / tickets
    "工单": "Заявка",
    "工单名称": "Название заявки",
    "工单完整名称": "Полное название заявки",
    "申请标题": "Заголовок заявки",
    "申请类型": "Тип заявки",
    "申请人": "Заявитель",
    "申请时间": "Время подачи",
    "审核状态": "Статус проверки",
    "审核人": "Проверяющий",
    "执行人": "Исполнитель",
    "组": "Группа",
    "资源组": "Группа ресурсов",
    # instance / DB
    "实例": "Инстанс",
    "实例名称": "Имя инстанса",
    "数据库": "База данных",
    "数据库名": "Имя БД",
    "表": "Таблица",
    "表名": "Имя таблицы",
    "表清单：<br>": "Список таблиц:<br>",
    "字段名": "Имя столбца",
    "索引": "Индекс",
    "节点": "Узел",
    "Redis节点": "Узел Redis",
    # SQL / query
    "SQL语句": "SQL-выражение",
    "完整SQL语句": "Полный SQL",
    "SQL内容": "Содержимое SQL",
    "完整SQL内容": "Полное содержимое SQL",
    "分析报告": "Отчёт анализа",
    "命令": "Команда",
    "命令模板": "Шаблон команды",
    "完整命令": "Полная команда",
    # slow query metrics
    "日志统计时间": "Время агрегации лога",
    "执行总次数": "Число выполнений",
    "执行次数": "Число выполнений",
    "执行总时长(秒)": "Суммарное время (с)",
    "平均执行时长(微秒)": "Среднее время (мкс)",
    "平均执行时长(秒)": "Среднее время (с)",
    "95%耗时(微秒)": "95-й перцентиль (мкс)",
    "执行时长(95%)": "Время выполнения (95%)",
    "扫描总行数": "Строк просканировано (всего)",
    "返回总行数": "Строк возвращено (всего)",
    "平均扫描行数": "Среднее число сканируемых строк",
    "平均返回行数": "Среднее число возвращаемых строк",
    "执行开始时间": "Время начала выполнения",
    "总耗时(秒)": "Общее время (с)",
    # archive
    "归档命令": "Команда архивации",
    "归档模式": "Режим архивации",
    "归档条件": "Условие архивации",
    "源数据": "Источник",
    "统计日志": "Лог статистики",
    "开始时间": "Время начала",
    "结束时间": "Время окончания",
    "插入": "INSERT",
    "删除权限": "Отозвать права",
    # validation / notices
    "校验失败": "Проверка не пройдена",
    "校验成功": "Проверка пройдена",
    "行数统计中...": "Подсчёт строк...",
    "正在校验SQL语法并统计结果行数，请稍候...": "Проверка синтаксиса SQL и подсчёт строк, подождите...",
    "暂无描述": "Описание отсутствует",
    "值不同": "Значения различаются",
    "仅源实例存在": "Только на исходном инстансе",
    "已选中{0}项": "Выбрано элементов: {0}",
    "已选择 ": "Выбрано: ",
    "关联对象描述": "Описание связанного объекта",
    "关联对象类型": "Тип связанного объекта",
    # 2FA / auth
    "请输入验证码！": "Введите код подтверждения!",
    "请输入手机号！": "Введите номер телефона!",
    "请输入密码！": "Введите пароль!",
    "验证码已发送，5分钟内有效": "Код отправлен, действует 5 минут",
    "已开启两步验证！": "Двухфакторная аутентификация включена!",
    "验证成功！": "Проверка успешна!",
    "扫码绑定": "Привязка по QR-коду",
    "绑定手机号": "Привязка телефона",
    "配置成功": "Настройки сохранены",
    "注册成功, 请输入密码登录!": "Регистрация выполнена. Войдите с паролем!",
    "获取验证码": "Получить код",
    "Redis帮助文档": "Справка Redis",
    "一键查询": "Быстрый запрос",
    "取消收藏": "Убрать из избранного",
    "变更": "Изменить",
    # calendar / daterangepicker (standard short forms)
    "日": "Вс",
    "一": "Пн",
    "二": "Вт",
    "三": "Ср",
    "四": "Чт",
    "五": "Пт",
    "六": "Сб",
    "一月": "янв",
    "二月": "фев",
    "三月": "мар",
    "四月": "апр",
    "五月": "май",
    "六月": "июн",
    "七月": "июл",
    "八月": "авг",
    "九月": "сен",
    "十月": "окт",
    "十一月": "ноя",
    "十二月": "дек",
    # workflow status keys
    "workflow_finish": "Успешно завершено",
    "workflow_abort": "Отменено вручную",
    "workflow_manreviewing": "Ожидает проверки",
    "workflow_review_pass": "Проверка пройдена",
    "workflow_timingtask": "Отложенное исполнение",
    "workflow_queuing": "В очереди",
    "workflow_executing": "Выполняется",
    "workflow_autoreviewwrong": "Автопроверка не пройдена",
    "workflow_exception": "Ошибка при выполнении",
    "未知状态": "Неизвестный статус",
    "查询权限申请": "Заявка на права запроса",
    "待审核": "Ожидает проверки",
    "%s 秒后重试": "Повтор через %s с",
    "测试水印": "Тестовый водяной знак",
}

# Phrase-level replacements for leftovers (order matters: longer first)
PHRASES = [
    ("执行", "выполнение"),
    ("审核", "проверка"),
    ("实例", "инстанс"),
    ("数据库", "БД"),
    ("权限", "права"),
    ("工单", "заявка"),
    ("用户", "пользователь"),
    ("时间", "время"),
    ("状态", "статус"),
    ("操作", "действие"),
    ("名称", "имя"),
    ("完整", "полный"),
    ("平均", "среднее"),
    ("总数", "итого"),
    ("次数", "число"),
    ("时长", "длительность"),
    ("耗时", "время"),
    ("行数", "число строк"),
    ("成功", "успешно"),
    ("失败", "ошибка"),
    ("错误", "ошибка"),
    ("请选择", "выберите "),
    ("请输入", "введите "),
    ("请填写", "укажите "),
    ("不能为空", "обязательно"),
    ("不存在", "не найден"),
    ("已选择", "выбрано"),
    ("已选中", "выбрано"),
]


def extract_msgids() -> set[str]:
    found: set[str] = set()
    roots = [
        ROOT / "sql" / "templates",
        ROOT / "common" / "templates",
        ROOT / "common" / "static" / "dist",
        ROOT / "common" / "static" / "dbdiagnostic",
        ROOT / "common" / "static" / "ace",
        ROOT / "common" / "static" / "watermark",
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in {".html", ".js"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for m in GETTEXT_RE.finditer(text):
                found.add(m.group(2))
    return found


def translate(msgid: str) -> str | None:
    if msgid in GLOSSARY:
        return GLOSSARY[msgid]
    # keep placeholders intact; only translate if we have a good glossary hit or short label
    if not any("\u4e00" <= c <= "\u9fff" for c in msgid):
        return GLOSSARY.get(msgid)
    # Prefer not to invent bad translations for long unknown strings:
    # try phrase substitution only for short labels (<= 20 chars) with high coverage
    if len(msgid) <= 24:
        out = msgid
        for zh, ru in sorted(PHRASES, key=lambda x: -len(x[0])):
            out = out.replace(zh, ru)
        chinese_left = sum(1 for c in out if "\u4e00" <= c <= "\u9fff")
        if chinese_left == 0:
            return out
    return None


def main() -> None:
    msgids = extract_msgids()
    print(f"extracted {len(msgids)} gettext msgids")

    po_path = ROOT / "common" / "locale" / "ru" / "LC_MESSAGES" / "djangojs.po"
    po = polib.pofile(str(po_path)) if po_path.exists() else polib.POFile()
    if not po_path.exists():
        po.metadata = {
            "Content-Type": "text/plain; charset=UTF-8",
            "Language": "ru",
        }

    existing = {e.msgid: e for e in po if e.msgid}
    added = 0
    filled = 0
    untranslated: list[str] = []

    for mid in sorted(msgids):
        if mid not in existing:
            entry = polib.POEntry(msgid=mid, msgstr="")
            po.append(entry)
            existing[mid] = entry
            added += 1
        entry = existing[mid]
        if not entry.msgstr:
            ru = translate(mid)
            if ru:
                entry.msgstr = ru
                filled += 1
            else:
                untranslated.append(mid)

    po.save(str(po_path))
    print(f"added={added} filled={filled} still_empty={len(untranslated)}")
    Path("/tmp/djangojs_untranslated.txt").write_text(
        "\n".join(untranslated), encoding="utf-8"
    )
    print("wrote /tmp/djangojs_untranslated.txt", len(untranslated))


if __name__ == "__main__":
    main()
