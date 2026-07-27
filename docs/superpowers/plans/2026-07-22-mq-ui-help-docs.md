# MQTT / RabbitMQ UI 帮助文档 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 SQL 查询页与 SQL 上线页为 MQTT / RabbitMQ 增加与 Redis 同构的分组帮助 Tab，文案按 MQTTX / rabbitmqadmin 子集编写，示例一行一条可复制，并写清 SysConfig 超时。

**Architecture:** 纯前端静态 HTML + 少量 JS，仿照 `sqlquery.html` 中 Redis 帮助 Tab。查询页扩展 `engineDisplayConfig` 与 `*_help_tab_add/remove`；上线页新增同构 Tab 壳。两页内嵌同一套分组全文（允许复制粘贴重复，不抽 include）。用轻量 pytest 断言两页模板均含规格要求的示例行与关键文案，防止漏拷。

**Tech Stack:** Django templates、jQuery / Bootstrap tabs（现有页面）、pytest（模板内容契约测试）

**Spec:** `docs/superpowers/specs/2026-07-22-mq-ui-help-docs-design.md`

## Global Constraints

- 口吻：MQTTX 子集 / rabbitmqadmin 子集；不写内部实现史或已废弃语法对照
- 示例：等宽、一行一条；规格 §6.2 / §6.3 示例下限必须全部出现在**两个**模板中
- 超时文案必须出现：`mq_query_timeout_default`、`mq_query_timeout_max`、默认 60、硬顶 3600；并写明本子集不提供 CLI 等待超时旗标
- 不修改 `sql/engines/mqtt.py` / `rabbitmq.py` 的 `*_HELP_ROWS`
- 不改变解析、异步查询、权限校验行为
- RabbitMQ 分组 radio 顺序：`help` `list` `show` `declare` `delete` `publish` `get` `purge` `close`
- MQTT 分组 radio 顺序：`help` `sub` `pub` `其它`
- Tab 标题固定：「MQTT帮助文档」「RabbitMQ帮助文档」
- 与 Redis 帮助互斥；切实例只增删帮助 Tab，不主动取消异步 MQ job（沿用现有离开页逻辑）

## File map

| 文件 | 职责 |
|------|------|
| `sql/templates/sqlquery.html` | 查询页：MQTT/RabbitMQ 帮助面板 HTML、分组 radio、`show_mqtt_help` / `show_rabbitmq_help`、Tab add/remove、`engineDisplayConfig` |
| `sql/templates/sqlsubmit.html` | 上线页：帮助 Tab 壳 + 与查询页同文的面板 + 实例变更时显隐 |
| `sql/tests/test_mq_help_templates.py` | 契约测试：两页均含必需字符串与分组锚点 id |

---

### Task 1: 模板内容契约测试（先红）

**Files:**
- Create: `sql/tests/test_mq_help_templates.py`
- Modify: none yet
- Test: `sql/tests/test_mq_help_templates.py`

**Interfaces:**
- Consumes: 无
- Produces: 模块级常量 `QUERY_TEMPLATE`、`SUBMIT_TEMPLATE`、`REQUIRED_SNIPPETS`；测试函数 `test_query_and_submit_contain_required_mq_help_snippets`

- [ ] **Step 1: Write the failing test**

创建 `sql/tests/test_mq_help_templates.py`：

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUERY_TEMPLATE = ROOT / "sql" / "templates" / "sqlquery.html"
SUBMIT_TEMPLATE = ROOT / "sql" / "templates" / "sqlsubmit.html"

# Spec §6.2 / §6.3 示例下限 + 关键文案锚点（两页都必须出现）
REQUIRED_SNIPPETS = [
    # MQTT examples
    "sub -t demo/test",
    "sub -t demo/test -C 1",
    "sub -t demo/test -C 10",
    "sub -t demo/test -q 0 -C 5",
    "sub -t demo/test -q 1 -C 5",
    "sub -t demo/test -q 2 -C 1",
    "sub --topic demo/test --count 3",
    "mqttx sub -t demo/test -C 1",
    "mqttx -h 127.0.0.1 -p 1883 sub -t demo/test -C 1",
    "pub -t demo/test -m hello",
    'pub -t demo/test -m "hello from archery"',
    'pub -t demo/test -m "hello" -q 0',
    'pub -t demo/test -m "hello" -q 1',
    'pub --topic demo/test --message "hello" --qos 1',
    'mqttx pub -t demo/test -m "hello from archery"',
    'mqttx -h 127.0.0.1 -p 1883 pub -t demo/test -m "hi"',
    # RabbitMQ examples
    "get queue=demo.q",
    "get queue=demo.q count=1",
    "get queue=demo.q count=5",
    "rabbitmqadmin get queue=demo.q count=1",
    "rabbitmqadmin -H 127.0.0.1 -P 5672 -u guest -p guest get queue=demo.q count=1",
    "list queues",
    "declare queue name=demo.q",
    "declare queue name=demo.q durable=true",
    "declare queue name=demo.q durable=false",
    "declare exchange name=demo.ex",
    "declare exchange name=demo.ex type=direct",
    "declare exchange name=demo.ex type=topic durable=true",
    "declare binding queue=demo.q exchange=demo.ex routing_key=demo.q",
    "publish routing_key=demo.q payload=hello",
    'publish routing_key=demo.q payload="hello from archery"',
    'publish routing_key=demo.q payload="hello" exchange=',
    'publish routing_key=demo.rk payload="hello" exchange=demo.ex',
    "purge queue name=demo.q",
    "delete queue name=demo.q",
    # Timeout / config
    "mq_query_timeout_default",
    "mq_query_timeout_max",
    # DOM anchors
    'id="mqtt_help"',
    'id="rabbitmq_help"',
    'id="mqttHelpSub"',
    'id="rabbitmqHelpGet"',
    "MQTT帮助文档",
    "RabbitMQ帮助文档",
    "本子集未支持",
    "ackmode",
]


def test_query_and_submit_contain_required_mq_help_snippets():
    query = QUERY_TEMPLATE.read_text(encoding="utf-8")
    submit = SUBMIT_TEMPLATE.read_text(encoding="utf-8")
    missing = []
    for snippet in REQUIRED_SNIPPETS:
        if snippet not in query:
            missing.append(f"sqlquery.html missing: {snippet!r}")
        if snippet not in submit:
            missing.append(f"sqlsubmit.html missing: {snippet!r}")
    assert not missing, "\n".join(missing)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest sql/tests/test_mq_help_templates.py -v`

Expected: FAIL，提示两页 missing 大量 snippet。

- [ ] **Step 3: Commit**

```bash
git add sql/tests/test_mq_help_templates.py
git commit -m "test(mq): add template contract for MQTT/RabbitMQ help docs"
```

---

### Task 2: 查询页 — MQTT 帮助面板 + Tab JS

**Files:**
- Modify: `sql/templates/sqlquery.html`
- Test: `sql/tests/test_mq_help_templates.py`

**Interfaces:**
- Consumes: Redis 模式 `redis_help_tab_add` / `redis_help_tab_remove`、`optgroup_control`
- Produces:
  - DOM: `#mqtt_help`；面板 id：`mqttHelpHelp`、`mqttHelpSub`、`mqttHelpPub`、`mqttHelpOther`
  - JS: `mqtt_help_tab_add()`、`mqtt_help_tab_remove()`、`show_mqtt_help(o)`
  - Config: `showMqttHelp` under `"MQTT"` in `engineDisplayConfig`

- [ ] **Step 1: Insert MQTT help tabpanel HTML**

在 `#tab-content` 内、`#redis_help` 之后插入。结构仿 Redis：

- radio：`help` / `sub` / `pub` / `其它`，value 分别为 `help` `sub` `pub` `other`，`onclick="show_mqtt_help(this)"`
- 面板 id：`mqttHelpHelp`、`mqttHelpSub`、`mqttHelpPub`、`mqttHelpOther`；默认显示 `mqttHelpSub`，其余 `display:none`
- `sub`：语法、默认值、连接忽略、异步、超时配置名与 60/3600、「本子集不提供 CLI 等待超时旗标」、规格全部 sub 示例
- `pub` / `help` / `其它`：按 spec §6.3

示例用 `<pre style="margin:0;white-space:pre-wrap;">` 一行一条。

- [ ] **Step 2: Add JS tab helpers and radio switcher**

```javascript
function mqtt_help_tab_add() {
    mqtt_help_tab_remove();
    var li = document.createElement("li");
    li.setAttribute("id", "mqtt_help_tab");
    li.setAttribute("role", "presentation");
    var href_a = document.createElement("a");
    href_a.setAttribute("href", "#mqtt_help");
    href_a.setAttribute("role", "tab");
    href_a.setAttribute("data-toggle", "tab");
    href_a.innerHTML = "MQTT帮助文档";
    li.appendChild(href_a);
    $("#nav-tabs").prepend(li);
    // 不调用 tab('show')，避免抢占异步结果 Tab（spec §5.3）
}

function mqtt_help_tab_remove() {
    $("#mqtt_help_tab").remove();
}

function show_mqtt_help(o) {
    var pages = ["mqttHelpHelp", "mqttHelpSub", "mqttHelpPub", "mqttHelpOther"];
    pages.forEach(function (id) {
        document.getElementById(id).style.display = "none";
    });
    var map = {
        help: "mqttHelpHelp",
        sub: "mqttHelpSub",
        pub: "mqttHelpPub",
        other: "mqttHelpOther"
    };
    var target = map[o.value];
    if (target) {
        document.getElementById(target).style.display = "block";
    }
}
```

- [ ] **Step 3: Wire engineDisplayConfig and optgroup_control**

`defaultDisplayConfig` 增加 `showMqttHelp: false`、`showRabbitmqHelp: false`。

```javascript
"MQTT": createDisplayConfig({
    showTableName: false,
    showSchemaName: false,
    showMqttHelp: true,
    showFormat: false,
    showExplain: false
}),
```

```javascript
if (displayConfig.showMqttHelp) {
    mqtt_help_tab_add();
} else {
    mqtt_help_tab_remove();
}
```

- [ ] **Step 4: Manual smoke**

选 MQTT 实例 → 「MQTT帮助文档」；选 MySQL → Tab 消失。

- [ ] **Step 5: Commit**

```bash
git add sql/templates/sqlquery.html
git commit -m "feat(mq): add MQTT help tab on SQL query page"
```

---

### Task 3: 查询页 — RabbitMQ 帮助面板 + Tab JS

**Files:**
- Modify: `sql/templates/sqlquery.html`
- Test: `sql/tests/test_mq_help_templates.py`

**Interfaces:**
- Consumes: Task 2 Tab 模式
- Produces:
  - DOM: `#rabbitmq_help`；`rabbitmqHelpHelp` … `rabbitmqHelpClose`（九个）
  - JS: `rabbitmq_help_tab_add()`、`rabbitmq_help_tab_remove()`、`show_rabbitmq_help(o)`
  - Config: `"RabbitMQ"` + `showRabbitmqHelp: true`

- [ ] **Step 1: Insert RabbitMQ help HTML**

九分组按 spec §6.2；`get` 含超时与 `ackmode` 未支持说明；`show`/`close` 为「本子集未支持」；全部示例下限进 `<pre>`。

- [ ] **Step 2: Add JS**

```javascript
function rabbitmq_help_tab_add() {
    rabbitmq_help_tab_remove();
    var li = document.createElement("li");
    li.setAttribute("id", "rabbitmq_help_tab");
    li.setAttribute("role", "presentation");
    var href_a = document.createElement("a");
    href_a.setAttribute("href", "#rabbitmq_help");
    href_a.setAttribute("role", "tab");
    href_a.setAttribute("data-toggle", "tab");
    href_a.innerHTML = "RabbitMQ帮助文档";
    li.appendChild(href_a);
    $("#nav-tabs").prepend(li);
}

function rabbitmq_help_tab_remove() {
    $("#rabbitmq_help_tab").remove();
}

function show_rabbitmq_help(o) {
    var pages = [
        "rabbitmqHelpHelp", "rabbitmqHelpList", "rabbitmqHelpShow",
        "rabbitmqHelpDeclare", "rabbitmqHelpDelete", "rabbitmqHelpPublish",
        "rabbitmqHelpGet", "rabbitmqHelpPurge", "rabbitmqHelpClose"
    ];
    pages.forEach(function (id) {
        document.getElementById(id).style.display = "none";
    });
    var map = {
        help: "rabbitmqHelpHelp",
        list: "rabbitmqHelpList",
        show: "rabbitmqHelpShow",
        declare: "rabbitmqHelpDeclare",
        delete: "rabbitmqHelpDelete",
        publish: "rabbitmqHelpPublish",
        get: "rabbitmqHelpGet",
        purge: "rabbitmqHelpPurge",
        close: "rabbitmqHelpClose"
    };
    var target = map[o.value];
    if (target) {
        document.getElementById(target).style.display = "block";
    }
}
```

- [ ] **Step 3: Wire displayConfig**

```javascript
"RabbitMQ": createDisplayConfig({
    showTableName: false,
    showSchemaName: false,
    showRabbitmqHelp: true,
    showFormat: false,
    showExplain: false
}),
```

```javascript
if (displayConfig.showRabbitmqHelp) {
    rabbitmq_help_tab_add();
} else {
    rabbitmq_help_tab_remove();
}
```

- [ ] **Step 4: Manual smoke**

选 RabbitMQ → 帮助 Tab；切 MQTT → 互斥正确。

- [ ] **Step 5: Commit**

```bash
git add sql/templates/sqlquery.html
git commit -m "feat(mq): add RabbitMQ help tab on SQL query page"
```

---

### Task 4: 上线页 — Tab 壳 + 全文复制

**Files:**
- Modify: `sql/templates/sqlsubmit.html`
- Test: `sql/tests/test_mq_help_templates.py`

**Interfaces:**
- Consumes: Task 2–3 的 `#mqtt_help` / `#rabbitmq_help` 全文（**相同 id**）
- Produces: `#mq-help-panel-wrap`、上线页 tab add/remove、契约测试全绿

- [ ] **Step 1: Add tab shell + paste panels**

在「检测结果」panel 之前增加 `#mq-help-panel-wrap`（默认 `display:none`），内含 `#mq-help-nav-tabs` 与 `#mq-help-tab-content`。将查询页 `#mqtt_help`、`#rabbitmq_help` **原样粘贴**进 content。

- [ ] **Step 2: Wire instance change JS**

在 `$("#instance_name").change` 中：`optgroup === "MQTT"` → `mqtt_help_tab_add()`；`RabbitMQ` → `rabbitmq_help_tab_add()`；否则 remove 并 hide wrap。复制 `show_mqtt_help` / `show_rabbitmq_help`。Mongo hint 不变。

上线页 `*_help_tab_add` 可 `tab('show')` 并 `$("#mq-help-panel-wrap").show()`（无异步结果 Tab 冲突）。

- [ ] **Step 3: Run contract tests**

Run: `pytest sql/tests/test_mq_help_templates.py -v`

Expected: PASS

- [ ] **Step 4: Manual acceptance (spec §8)**

按规格 §8 六条手工点验；回归 Redis 帮助与 Mongo 提示。

- [ ] **Step 5: Commit**

```bash
git add sql/templates/sqlsubmit.html sql/templates/sqlquery.html sql/tests/test_mq_help_templates.py
git commit -m "feat(mq): add MQTT/RabbitMQ help tabs on SQL submit page"
```

---

## Spec coverage checklist

| Spec 项 | Task |
|---------|------|
| 查询页帮助 Tab | 2, 3 |
| 上线页帮助 Tab + 全文一致 | 4 |
| rabbitmqadmin / MQTTX 分组 | 2, 3 |
| 可复制示例下限 | 1, 2–4 |
| SysConfig 超时 | 2, 3, 1 |
| 未支持 show/close/其它；list Management | 3, 2 |
| 不改引擎 / 解析 | 全局 |
| 与 Redis 互斥、不抢异步焦点 | 2 |
| 验收 §8 | 4 |

## Placeholder / consistency review

- 无 TBD；DOM id 与契约测试一致；上线页粘贴查询页 HTML 防漂移。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-22-mq-ui-help-docs.md`. Two execution options:

**1. Subagent-Driven (recommended)** — 每 Task 子代理 + 任务间审查  

**2. Inline Execution** — 本会话连续执行  

Which approach?
