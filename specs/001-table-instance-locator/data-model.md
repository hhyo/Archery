# Data Model: Table Instance Locator API

## 1) TableLocatorRequest

Represents API input and provider input.

Fields:
- `table_name` (string, optional, max 256): exact table name.
- `table_pattern` (string, optional, max 256): LIKE-style pattern using `%` and `_`.
- `match_mode` (enum, derived): `exact` or `pattern`.
- `request_user_id` (int, derived runtime context): current authenticated user id.

Validation rules:
- Exactly one of `table_name` or `table_pattern` must be provided.
- Provided value must be non-empty after trimming.
- Length must be <= 256.
- Pattern mode only accepts `%` and `_` wildcard semantics.

State transitions:
- `received` -> `validated` -> `resolved_to_execution_plan`.
- Invalid input transitions to `rejected` with user-readable errors.

## 2) TableLocationItem

Represents one matched table location.

Fields:
- `instance_name` (string, **required**): display name of the instance.
- `db_type` (string, **required**): database engine type (e.g. `mysql`, `postgresql`).
- `db_name` (string, **required**): name of the database inside the instance.
- `instance_id` (int, optional): numeric primary key of the instance.
- `table_name` (string, optional): matched table name; populated when available from provider.
- `match_type` (enum: `exact` | `pattern`, optional): how the table was matched.

Validation/normalization rules:
- `instance_name`, `db_type`, and `db_name` must be non-empty after normalization; items missing any of these are rejected from the result set.
- Optional fields missing from provider output are omitted (not set to null) in the response.
- Returned items are sorted deterministically by `(instance_name, db_name, table_name, instance_id)`.

## 3) LocatorExecutionSummary

Represents request execution status including partial failures.

Fields:
- `processed_instance_count` (int)
- `success_instance_count` (int)
- `failed_instance_count` (int)
- `failure_reasons` (array of objects)

Failure reason object:
- `instance_id` (int, optional when unknown)
- `instance_name` (string, optional)
- `reason` (string)

Validation rules:
- `processed_instance_count = success_instance_count + failed_instance_count`.
- `failure_reasons` length should equal `failed_instance_count` when reason collection is enabled.

## 4) LocatorProvider (interface contract)

A callable abstraction used by default and custom implementations.

Signature:
- Input: `request: TableLocatorRequest`, `instances: Iterable[Instance]`, optional context kwargs.
- Output: `tuple[list[TableLocationItem], LocatorExecutionSummary]` or backward-compatible list normalized by resolver.

Behavior rules:
- Provider must not return data from unauthorized instances.
- Provider should continue when a subset of instances fails and report failures in summary.
- Provider output must be normalizable to fixed API schema.
