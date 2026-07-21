# MQ 本地环境与仓库产物清理设计

日期：2026-07-21  
分支：`feat/mqtt-rabbitmq-engine`  
状态：已定稿（待实现）

## 问题

本地测试 MySQL 时：实例配置与连通正常，但提交 SQL / 选择数据库时报：

`module 'pymysql' has no attribute 'escape_string'`

用户要求：

1. 查明是否因 MQTT/RabbitMQ 改动影响了原有 MySQL 功能
2. 本地虚拟环境统一使用 `.venv`，不要使用 `.venv-mq`
3. 清理本分支产生的、生产不需要的工具产物，并正确更新 `.gitignore`

## 根因结论

这不是 MQTT/RabbitMQ 业务代码回归。

证据：

1. 相对 `master`，本分支对 `sql/engines/mysql.py`、`sql/slowlog.py`、`sql_api/api_instance.py` 均为空 diff。
2. MySQL 列库路径仍走既有逻辑：`query_engine.escape_string()` → `pymysql.escape_string()`（master 原有代码）。
3. 本地实际使用的是 `.venv-mq`，其中 `PyMySQL` 被装成 `1.1.1` / `1.4.6` 系列；`requirements.txt` 锁定的是 `pymysql==0.9.3`。
4. `pymysql` 1.x 已移除模块级 `escape_string`，因此报错。
5. 本机当前不存在 `.venv`，只有破损的 `.venv-mq`。
6. `scripts/mq_env/fix_deps.sh`（未跟踪）在缺 `MySQLdb` 时错误执行 `pip install PyMySQL==1.1.1`，进一步污染环境。

`manage.py` 中的 `pymysql.install_as_MySQLdb()` 仅为**本地未提交改动**，相对 `master` 分支正式提交为零 diff；该 shim 不是功能所需，必须丢弃。

## 目标

1. 恢复与 `requirements.txt` 一致的本地 Python 环境（目录名固定为 `.venv`）。
2. 从分支与工作区清理生产/上游不需要的工具产物。
3. 正确更新 `.gitignore`，且不误伤 master 已有的 `scripts/run_pytest.sh`。
4. **不修改**任何既有数据库引擎（MySQL 等）业务代码来“适配”错误依赖版本。

## 非目标

1. 不升级 `pymysql` 到 1.x，不改写 `escape_string` 调用以兼容新版本。
2. 不把 `scripts/` 整目录 ignore。
3. 不删除本分支合法的 MQ 引擎/API/测试代码。
4. 不强制删除本机磁盘上的 `scripts/mq_env/` 工作副本（可保留本地联调），只保证它们不再进入 Git。

## 方案选择

| 方案 | 做法 | 取舍 |
|------|------|------|
| A. 仅降级 `.venv-mq` 的 pymysql | 快，但不解决命名与依赖纪律问题 | 否决 |
| B. 统一 `.venv` + 清理 ignore/跟踪 + 丢弃 manage.py shim | 与仓库锁定版本一致，避免污染上游 | **采用** |
| C. 改 MySQL 代码兼容 pymysql 1.x | 把环境问题转成全局 API 变更，风险扩散到全仓 | 否决 |

推荐 B。

## 设计

### 1. 本地虚拟环境

1. 虚拟环境目录名固定为 `.venv`（已在 `.gitignore` 中）。
2. 删除 `.venv-mq`（或停止使用；脚本与文档不再引用）。
3. 新建/重建 `.venv` 时严格按 `requirements.txt` 安装：
   - `mysqlclient==2.*`
   - `pymysql==0.9.3`
   - 本分支新增：`pika==1.3.2`、`paho-mqtt==2.1.0`
4. 禁止“缺模块就随便 pip install”的本地补丁脚本；若保留本地联调脚本，必须只允许安装 `requirements.txt` 中已锁定的包。
5. 验收：`.venv` 中 `hasattr(pymysql, "escape_string") is True`；MySQL 实例可选库、可提交查询。

### 2. `manage.py`

1. 丢弃工作区未提交的 `pymysql.install_as_MySQLdb()` 改动。
2. 保持与 `master` 一致，本功能不引入对 `manage.py` 的任何正式变更。

### 3. `.gitignore`

在现有规则基础上精确增加：

```gitignore
.codegraph/
.gstack/
.superpowers/
scripts/mq_env/
```

同时：

1. **撤销**错误的整目录规则 `scripts/`（若本地已加入）。
2. 保留已有 `docs/superpowers/testdata/mq-certs/`（证书私料，不入库）。
3. 不新增对 `docs/superpowers/specs|plans` 的 ignore（设计/计划文档可继续作为可审查文档跟踪，除非后续单独决定从 PR 剥离）。

### 4. 已跟踪但生产不需要的产物：取消跟踪

以下路径本分支已提交或本地工具生成，**不参与生产运行**，应从 Git 跟踪移除（文件可留在磁盘）：

| 路径 | 处理 |
|------|------|
| `.superpowers/`（含已提交的 `sdd/*report.md`） | `git rm -r --cached` + ignore |
| `scripts/mq_env/`（含已提交的 README / gen_certs / verify_auth） | `git rm -r --cached` + ignore |
| `.codegraph/`、`.gstack/`、`.venv-mq/` | **从未提交过**，不需要 `git rm`；仅加入/确认 ignore（`.venv-mq` 可选，因其自带内部 ignore） |

说明：

- `scripts/run_pytest.sh` 属于 master 既有资产，继续跟踪。
- MQ 引擎源码、`sql/engines/test_*.py`、`sql_api/test_mq_*.py` 等**测试与功能代码继续跟踪**，不得 ignore。

### 5. 本地未跟踪临时脚本

`scripts/mq_env/` 下未跟踪的启动/补依赖脚本（如 `fix_deps.sh`、`run_archery_local.sh`、`bootstrap_and_check.sh` 等）：

1. 因目录将被 ignore，不再入库。
2. 实现阶段应删除或重写其中会安装 `PyMySQL==1.1.1` 的逻辑，避免再次污染 `.venv`。
3. 若保留本地 README，所有激活命令改为 `source .venv/bin/activate`。

### 6. 验证清单

实现完成后至少验证：

1. `git diff master...HEAD -- manage.py` 为空。
2. `git ls-files scripts/mq_env .superpowers .codegraph .gstack` 为空。
3. `git ls-files scripts/run_pytest.sh` 仍存在。
4. `.gitignore` 含 `.codegraph/`、`.gstack/`、`.superpowers/`、`scripts/mq_env/`，且不含整目录 `scripts/`。
5. `.venv` 中 `pymysql.__version__` 对应 `0.9.3`，且存在 `escape_string`。
6. MySQL：选实例可列库、可提交 SQL。
7. MQTT/RabbitMQ：既有引擎单测与关键验收不因清理而破坏（代码本身不改业务路径）。

## 风险与约束

1. 取消跟踪 `scripts/mq_env` 后，上游 PR 将不再包含本机 broker 验收脚本；这是有意的，避免把本地联调产物带进生产仓库。
2. 取消跟踪 `.superpowers` 后，开发过程报告不再出现在 PR diff 中；设计文档仍在 `docs/superpowers/`。
3. 重建 `.venv` 需要本机能编译/安装 `mysqlclient`；若安装失败，应修环境，而不是回退到 PyMySQL shim。
4. 全局约束不变：**不得**为修环境去改动其他数据库引擎行为。

## 实现顺序（摘要）

1. 丢弃 `manage.py` 本地 shim。
2. 修正 `.gitignore`（精确规则 + 去掉 `scripts/`）。
3. `git rm --cached` 已跟踪的 `.superpowers/` 与 `scripts/mq_env/`。
4. 删除/停用 `.venv-mq`；按 `requirements.txt` 建立 `.venv`。
5. 清理本地会装错版本的临时脚本引用。
6. 按验证清单回归 MySQL 与 MQ。
)