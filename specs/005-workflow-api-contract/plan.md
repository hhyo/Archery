# Implementation Plan: Workflow API Contract Completeness

**Branch**: `005-workflow-api-contract` | **Date**: 2026-09-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-workflow-api-contract/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Complete the workflow-facing API contract needed by existing CLI review output, watch behavior, and generated clients. The plan adds a permission-scoped, read-only instance detail surface; reuses the existing SQL Workflow detail endpoint for single-workflow retrieval; makes `workflow.instance` identifier semantics explicit; documents the extension strategy for workflow, workflow content, and workflow log contracts; and documents existing SQL Workflow logs, status, approval, and execution request/response bodies.

Instance detail access changes from administrator-only configuration access to authenticated user read access, but only when the user has submit-style `can_write` access or query-style `can_read` access to the requested instance. The read response must use a narrow public serializer that omits internal and sensitive fields such as connection usernames, passwords, secrets, tunnels, operational flags, and configuration values that do not help ordinary users understand workflow review output.

## Technical Context

**Language/Version**: Python 3 with Django project runtime as configured by the repository  
**Primary Dependencies**: Django, Django REST Framework, django-filter, drf-spectacular, simplejson  
**Storage**: Existing relational database tables for `Instance`, `SqlWorkflow`, `SqlWorkflowContent`, `WorkflowAudit`, and `WorkflowLog`  
**Testing**: pytest using repository `pyproject.toml` configuration and shared `conftest.py` fixtures  
**Target Platform**: Archery web application server and REST API consumers, including CLI/generated clients
**Project Type**: Django web application with REST API  
**Performance Goals**: Direct instance lookup and existing SQL Workflow detail lookup complete with bounded single-resource database access; workflow clients no longer need paginated list scans for one workflow  
**Constraints**: Instance detail must require authentication plus `can_write` or `can_read` instance access; public instance responses must exclude internal/sensitive fields; API errors must be sanitized; OpenAPI contracts must document extension-field strategy for generated clients; do not add a duplicate workflow detail endpoint; audit-id approval/execution endpoints derive actor from session and must not accept caller-supplied `engineer`  
**Scale/Scope**: Contract gap closure for existing instance and SQL workflow APIs; no new database models and no changes to engine execution behavior

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Multi-engine compatibility impact is listed and bounded by adapter or capability layer.
- [x] Test plan is unit-test-first with pytest; integration scope is explicitly minimized.
- [x] Shared setup is designed via conftest.py fixtures; duplicate setup is eliminated.
- [x] Any integration test includes a written justification for why unit tests are insufficient.
- [x] API errors are sanitized for users and unexpected exceptions are logged.
- [x] Breaking API contract changes are documented and preserve existing workflow consumers where required.

## Project Structure

### Documentation (this feature)

```text
specs/005-workflow-api-contract/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
sql_api/
├── api_instance.py
├── api_workflow.py
├── api_workflow_operations.py
├── serializers.py
├── urls.py
├── test_api_instance.py
└── test_workflow_operations_api.py

sql/
├── models.py
└── utils/
    ├── resource_group.py
    └── sql_review.py

conftest.py
```

**Structure Decision**: Keep all implementation in the existing Django REST API app. Add narrow serializers and permission helpers beside the existing instance/workflow views; reuse `user_instances(..., tag_codes=["can_write"])` and `user_instances(..., tag_codes=["can_read"])` for instance eligibility; reuse existing workflow visibility checks for workflow detail. Do not introduce new persistence models or engine abstractions.

## Complexity Tracking

No constitution violations are planned.

## Phase 0 Research

See [research.md](./research.md). Decisions cover instance read permissions, safe public instance fields, reuse of the existing SQL Workflow detail endpoint, identifier semantics, extension strategy documentation, action/status/log schema documentation, OpenAPI documentation, and test boundaries.

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/workflow-api-contract.openapi.yaml](./contracts/workflow-api-contract.openapi.yaml), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

- [x] Multi-engine compatibility remains bounded: the feature exposes metadata and saved workflow records only, without changing engine-specific execution behavior.
- [x] Test strategy remains pytest unit-first for permission helpers, serializer field allowlists, and identifier mapping; generated schema details can be checked with temporary scripts.
- [x] Integration scope is limited to REST routing/authentication/serialization boundaries, with rationale recorded in the quickstart.
- [x] Shared setup relies on existing `conftest.py` fixtures and adds reusable fixtures only when needed.
- [x] API failures are specified as sanitized and deterministic, with internal details excluded from user responses.
