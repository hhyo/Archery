# Implementation Plan: Workflow Operations REST API Migration

**Branch**: `003-migrate-workflow-api` | **Date**: 2026-08-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-migrate-workflow-api/spec.md`

## Summary

将 `sql/sql_workflow.py` 中的十项工单操作迁移到会话身份驱动的 DRF API，并删除对应的函数视图和旧路由。新接口统一置于 `/api/v1/workflows/`，页面模板只替换请求地址，保留原有请求字段、成功响应包络和业务语义。共享的操作服务负责权限校验、审计、状态变更、调度生命周期和通知；DRF 视图仅负责请求解析、响应和 HTTP 语义。

## Technical Context

**Language/Version**: Python 3.x, Django 4.x, Django REST Framework; jQuery 3 + Bootstrap 3 templates  
**Primary Dependencies**: Django REST Framework, drf-spectacular, django-q, simplejson, existing `sql.engines` adapter layer  
**Storage**: Existing Archery MySQL models (`SqlWorkflow`, `SqlWorkflowContent`, `WorkflowAudit`, `WorkflowLog`) and django-q `Schedule`; no new storage  
**Testing**: pytest + pytest-django + DRF `APIClient`; mock engine, django-q and notification side effects  
**Target Platform**: Linux-hosted Django web application
**Project Type**: Server-rendered web application with DRF backend  
**Performance Goals**: No additional browser request round trips; list, details and control endpoints retain existing response shape and pagination behavior; engine call remains the dominant cost for rollback/OSC  
**Constraints**: New paths are exclusively under `/api/v1/workflows/`; do not retain legacy operation URLs or aliases; front-end changes are URL-only where request method/payload and response shape already match; use `request.user`, never a client-supplied actor; preserve multi-engine adapter use and configured notifications  
**Scale/Scope**: Ten existing operation capabilities, seven removed form/JSON routes, three updated list-page URLs, one detail page and one rollback page; one dedicated DRF module, serializer set, service module and pytest module

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Multi-engine compatibility impact is listed and bounded by adapter or capability layer.
  *Rollback and OSC remain behind `get_engine(instance=workflow.instance)`; new API/service code does not branch by database type.*
- [x] Test plan is unit-test-first with pytest; integration scope is explicitly minimized.
  *Service tests cover state, authorization, audit, scheduling and notifications with mocks; only endpoint authentication/routing and legacy-route removal require HTTP integration tests.*
- [x] Shared setup is designed via conftest.py fixtures; duplicate setup is eliminated.
  *Extend existing workflow, user, resource group, instance and audit fixtures in `conftest.py`, then share API client and mocked external-side-effect fixtures across the dedicated test module.*
- [x] Any integration test includes a written justification for why unit tests are insufficient.
  *Route and session authentication behavior crosses Django URL resolution and DRF dispatch; each such test will state this boundary rationale.*

## Project Structure

### Documentation (this feature)

```text
specs/003-migrate-workflow-api/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── workflow-operations.openapi.yaml
└── tasks.md              # Created by /speckit.tasks
```

### Source Code (repository root)
```text
archery/
└── urls.py                            # Mounts sql_api at /api/

sql_api/
├── api_workflow_operations.py          # New session-user workflow operation views
├── serializers.py                      # New request serializers and response schema types
├── services/
│   └── workflow_operations.py          # New transactional operation orchestration
├── urls.py                             # Adds /api/v1/workflows/ routes
└── test_workflow_operations_api.py     # New focused pytest unit and integration tests

sql/
├── sql_workflow.py                     # Remove migrated function views and obsolete imports
├── urls.py                             # Remove all migrated legacy operation routes
├── templates/
│   ├── sqlworkflow.html                # Replace list URL only
│   ├── audit_sqlworkflow.html          # Replace list URL only
│   ├── sqlexportworkflow.html          # Replace list URL only
│   ├── detail.html                     # Replace operation URLs only
│   └── rollback.html                   # Replace rollback URL only
└── tests.py                            # Move/replace legacy route checks

conftest.py                             # Extend reusable workflow API fixtures as needed
```

**Structure Decision**: Keep the existing Django application layout. Add a dedicated `sql_api` operation module instead of extending the generic `api_workflow.py`, whose current client-supplied actor contract is not safe for page requests. Put state-changing orchestration in a small service module so views remain declarative and service tests can cover transactional outcomes without HTTP setup.

## Complexity Tracking

No constitution violations. The service module is a bounded extraction required to unit-test atomic state transitions and to prevent duplicated workflow side effects across DRF views.

---

## Phase 0: Research Summary

See [research.md](research.md). Key decisions: new paths use `/api/v1/workflows/`; original field names and JSON envelopes remain where page JavaScript consumes them; old operation routes are deleted with no aliases; all authority derives from `request.user`; scheduling effects are coordinated with database state using transaction completion hooks.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md), [workflow-operations.openapi.yaml](contracts/workflow-operations.openapi.yaml), and [quickstart.md](quickstart.md).

### Post-design Constitution Check

- [x] Multi-engine access stays isolated at the existing engine adapter boundary.
- [x] The test design is service-unit-test-first; HTTP checks only cover DRF/session/URL boundaries.
- [x] Existing `conftest.py` workflow fixtures are extended rather than duplicated.
- [x] Each endpoint integration test documents that unit tests cannot validate its route and session dispatch boundary.
