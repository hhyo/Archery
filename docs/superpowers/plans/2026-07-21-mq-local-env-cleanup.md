# MQ Local Env Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the local MySQL `pymysql.escape_string` failure by restoring a `requirements.txt`-faithful `.venv`, and remove production-irrelevant branch artifacts from Git tracking without changing MySQL/MQ engine behavior.

**Architecture:** Environment and repo hygiene only. Discard the local `manage.py` PyMySQL shim; tighten `.gitignore`; `git rm --cached` already-tracked `.superpowers/` and `scripts/mq_env/`; stop using `.venv-mq` and recreate `.venv` from `requirements.txt`. No changes to `sql/engines/mysql.py` or other DB engines.

**Tech Stack:** Git, `.gitignore`, WSL Python venv, `requirements.txt` (`mysqlclient==2.*`, `pymysql==0.9.3`, `pika==1.3.2`, `paho-mqtt==2.1.0`)

**Spec:** `docs/superpowers/specs/2026-07-21-mq-local-env-cleanup-design.md`

## Global Constraints

- Do **not** modify MySQL or other existing DB engine business code to work around wrong PyMySQL versions.
- Do **not** upgrade `pymysql` to 1.x; keep `pymysql==0.9.3` from `requirements.txt`.
- Virtualenv directory name must be `.venv` (never `.venv-mq`).
- Do **not** ignore the whole `scripts/` directory; only `scripts/mq_env/`.
- Keep tracking `scripts/run_pytest.sh`.
- Keep tracking MQ feature/test code under `sql/` and `sql_api/`.
- `.codegraph/`, `.gstack/`, `.venv-mq/` were **never committed** — do not run `git rm` on them.
- Do not commit secrets (`.env`, certs, `local_settings.py`).
- Prefer PowerShell on Windows; use `;` not `&&`. Use WSL for Linux venv/pip commands.

## File map

| Path | Action | Responsibility |
|------|--------|----------------|
| `manage.py` | Discard local uncommitted shim | Stay identical to `master` |
| `.gitignore` | Modify | Ignore tool dirs + `scripts/mq_env/`; remove bad `scripts/` rule |
| `.superpowers/` | `git rm -r --cached` | Dev process reports leave the index |
| `scripts/mq_env/` | `git rm -r --cached` | Local MQ broker helpers leave the index |
| `.venv-mq/` | Delete or abandon on disk | Stop using polluted env |
| `.venv/` | Create/reinstall | Faithful install from `requirements.txt` |
| `scripts/mq_env/fix_deps.sh` (local) | Delete or neutralize | Must not install `PyMySQL==1.1.1` |
| `docs/superpowers/specs/2026-07-21-mq-local-env-cleanup-design.md` | Already written | Source of truth |
| Engine / API / test code | **No change** | Out of scope |

---

### Task 1: Discard local `manage.py` shim

**Files:**
- Modify (discard): `manage.py` (working tree only; must match `master`)

**Interfaces:**
- Consumes: none
- Produces: clean `manage.py` with no `pymysql.install_as_MySQLdb()`

- [ ] **Step 1: Confirm the only local diff is the shim**

```powershell
cd e:\github\Archery
git diff -- manage.py
git diff master...HEAD -- manage.py
```

Expected:
- Working tree diff shows the 7-line `pymysql.install_as_MySQLdb()` block
- `master...HEAD` diff is empty

- [ ] **Step 2: Restore `manage.py` to HEAD (which equals master for this file)**

```powershell
git restore manage.py
```

- [ ] **Step 3: Verify**

```powershell
git diff -- manage.py
git diff master...HEAD -- manage.py
Get-Content manage.py
```

Expected: both diffs empty; file content is:

```python
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "archery.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
```

- [ ] **Step 4: Commit**

No commit needed if nothing was staged for `manage.py`. If a previous mistaken commit existed (it should not), do not amend remote history; leave as-is and only ensure working tree is clean for this file.

---

### Task 2: Fix `.gitignore` rules

**Files:**
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Task 1 clean tree preference
- Produces: ignore rules for `.codegraph/`, `.gstack/`, `.superpowers/`, `scripts/mq_env/` only

- [ ] **Step 1: Read current `.gitignore` end section**

```powershell
Get-Content .gitignore
```

- [ ] **Step 2: Make the trailing rules exactly**

Ensure the file ends with (keep existing earlier rules unchanged, including `docs/superpowers/testdata/mq-certs/` if present):

```gitignore
docs/superpowers/testdata/mq-certs/
.codegraph/
.gstack/
.superpowers/
scripts/mq_env/
```

Explicitly **remove** any bare `scripts/` line if present.

Do **not** add `.venv-mq/` unless desired for clarity; it already self-ignores via `.venv-mq/.gitignore`.

- [ ] **Step 3: Verify ignore behavior**

```powershell
git check-ignore -v .codegraph/ .gstack/ .superpowers/ scripts/mq_env/ scripts/run_pytest.sh
```

Expected:
- `.codegraph/`, `.gstack/`, `.superpowers/`, `scripts/mq_env/` match the new rules
- `scripts/run_pytest.sh` is **not** ignored (no output line, or exit indicating not ignored)

- [ ] **Step 4: Commit**

```powershell
git add .gitignore
git commit -m @"
chore(mq): ignore local tool dirs and scripts/mq_env

"@
```

---

### Task 3: Untrack `.superpowers/` and `scripts/mq_env/` from the branch

**Files:**
- Index only: `.superpowers/**`, `scripts/mq_env/**`
- Keep on disk: optional (files may remain locally)

**Interfaces:**
- Consumes: Task 2 ignore rules so untracked files stay ignored
- Produces: empty `git ls-files` for those two trees; `scripts/run_pytest.sh` still tracked

- [ ] **Step 1: List currently tracked paths to remove**

```powershell
git ls-files .superpowers scripts/mq_env
```

Expected (at least):
- `.superpowers/sdd/cli-task-final-fix-report.md`
- `.superpowers/sdd/task-final-fix-report.md`
- `scripts/mq_env/README.md`
- `scripts/mq_env/gen_certs.sh`
- `scripts/mq_env/verify_auth.py`

- [ ] **Step 2: Remove from index only**

```powershell
git rm -r --cached .superpowers
git rm -r --cached scripts/mq_env
```

- [ ] **Step 3: Verify tracking**

```powershell
git ls-files .superpowers scripts/mq_env .codegraph .gstack .venv-mq
git ls-files scripts/run_pytest.sh
```

Expected:
- First command: empty
- Second: `scripts/run_pytest.sh`

- [ ] **Step 4: Neutralize local bad installer if the file still exists on disk**

If `scripts/mq_env/fix_deps.sh` exists locally, either delete it or ensure it no longer contains:

```bash
MySQLdb) pip install -q PyMySQL==1.1.1 ;;
```

Preferred: delete `scripts/mq_env/fix_deps.sh` (local-only; ignored after Task 2).

Also rewrite any local activation lines from `.venv-mq` to `.venv` in leftover local scripts/README if kept on disk (not committed).

- [ ] **Step 5: Commit**

```powershell
git add -u .superpowers scripts/mq_env
git status --short
git commit -m @"
chore(mq): stop tracking local mq_env scripts and superpowers reports

"@
```

---

### Task 4: Replace `.venv-mq` with a faithful `.venv`

**Files:**
- Delete/abandon: `.venv-mq/` (disk)
- Create: `.venv/` (disk, already gitignored via `.venv/`)

**Interfaces:**
- Consumes: `requirements.txt` pins
- Produces: `.venv` with `pymysql==0.9.3` exposing `pymysql.escape_string`

- [ ] **Step 1: Confirm pins in `requirements.txt`**

```powershell
Select-String -Path requirements.txt -Pattern 'mysqlclient|pymysql|pika|paho-mqtt'
```

Expected lines include:
- `mysqlclient==2.*`
- `pymysql==0.9.3`
- `pika==1.3.2`
- `paho-mqtt==2.1.0`

- [ ] **Step 2: Stop using `.venv-mq`**

```bash
wsl -e bash -lc 'cd /mnt/e/github/Archery; rm -rf .venv-mq'
```

If deletion is undesirable, at minimum never activate it again.

- [ ] **Step 3: Create `.venv` and install exactly from requirements**

```bash
wsl -e bash -lc 'cd /mnt/e/github/Archery; python3 -m venv .venv; source .venv/bin/activate; pip install -U pip; pip install -r requirements.txt'
```

If `mysqlclient` fails to build, fix OS packages / build deps in WSL. Do **not** install PyMySQL 1.x as a substitute and do **not** re-add a `manage.py` shim.

- [ ] **Step 4: Verify PyMySQL API**

```bash
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv/bin/activate; python -c "import pymysql; print(pymysql.__version__); print(hasattr(pymysql, \"escape_string\")); print(pymysql.escape_string(\"a'\''b\"))"'
```

Expected:
- version `0.9.3`
- `True`
- escaped string printed (no AttributeError)

- [ ] **Step 5: Smoke Django import path (optional but recommended)**

```bash
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv/bin/activate; export PYTHONPATH=/mnt/e/github/Archery; python -c "import MySQLdb; print(MySQLdb.__name__)"'
```

Expected: imports successfully via `mysqlclient` (module name `MySQLdb`), not a PyMySQL shim.

- [ ] **Step 6: Commit**

No commit — `.venv` is gitignored.

---

### Task 5: Regression verification

**Files:**
- None (verification only)

**Interfaces:**
- Consumes: Tasks 1–4 complete
- Produces: pass/fail evidence for spec verification checklist

- [ ] **Step 1: Repo hygiene checks**

```powershell
cd e:\github\Archery
git diff master...HEAD -- manage.py
git ls-files scripts/mq_env .superpowers .codegraph .gstack .venv-mq
git ls-files scripts/run_pytest.sh
Select-String -Path .gitignore -Pattern '^\.codegraph/|^\.gstack/|^\.superpowers/|^scripts/mq_env/|^scripts/$'
```

Expected:
1. `manage.py` branch diff empty
2. first `ls-files` empty
3. `scripts/run_pytest.sh` listed
4. `.gitignore` matches the four ignore rules; **no** bare `scripts/` rule

- [ ] **Step 2: Focused MQ unit tests still collect/pass in `.venv`**

```bash
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv/bin/activate; pytest -q sql/engines/test_mq_cli.py sql/engines/test_mqtt.py sql/engines/test_rabbitmq.py sql/services/test_mq_query_job.py sql_api/test_mq_query_job_api.py sql_api/test_instance_serializer_secrets.py'
```

Expected: all pass (or same pre-existing env limitations documented; do not “fix” by changing engine code).

- [ ] **Step 3: Manual MySQL UI check**

Start Archery with `.venv` (not `.venv-mq`), open SQL query page:

1. Select a MySQL instance → database list loads
2. Submit a simple `SELECT 1` (or equivalent) → no `escape_string` error

- [ ] **Step 4: Final status commit if any leftover tracked cleanup remains**

Only if `git status` shows remaining intentional tracked fixes not yet committed. Do not commit `.env`, `local_settings.py`, certs, or `.venv`.

```powershell
git status --short
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Root cause is env, not MQ engine code | Task 4–5 (no engine edits) |
| Use `.venv`, not `.venv-mq` | Task 4 |
| Install from `requirements.txt` pins | Task 4 |
| Discard `manage.py` shim | Task 1 |
| `.gitignore` exact rules; no whole `scripts/` | Task 2 |
| Untrack `.superpowers/` and `scripts/mq_env/` | Task 3 |
| Do not `git rm` never-tracked `.codegraph/` `.gstack/` `.venv-mq/` | Task 3 Step 3 verify empty |
| Keep `scripts/run_pytest.sh` | Task 3 Step 3 |
| Neutralize `PyMySQL==1.1.1` installer | Task 3 Step 4 |
| Verification checklist | Task 5 |
| Do not change MySQL engine code | Global + all tasks |

## Self-review notes

- No placeholders / TBD left in steps.
- No engine/API code changes planned.
- Commit messages follow existing `chore(mq):` / branch style.
)