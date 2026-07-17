# Final whole-branch review fixes

## 2026-07-17 fix result

Status: **DONE**

- MQTT connection setup now starts the network loop and waits up to 10 seconds
  for a successful CONNACK. Authentication rejection, non-success connect return
  codes, and CONNACK timeout are returned through `ResultSet.error`.
- The same CONNACK gate is used by connection tests, subscriptions, and workflow
  publishing, so no MQTT operation proceeds before broker acceptance.
- MQTT and RabbitMQ validate client certificate/key pairing even when SSL is
  disabled.
- MQTT query supports `help`; workflow publish supports optional QoS 0, 1, or 2.
- Empty MQTT subscriptions retain successful empty rows and set a timeout hint in
  `ResultSet.warning`.
- Added regression coverage for bad credentials in connection/query paths,
  CONNACK timeout, non-SSL incomplete certificate configuration, help, QoS, and
  empty-subscription timeout hints.
- No Management API or `basic.consume` was added.

## Verification

The host Python initially could not run the suite because Django was absent:

```text
python -m unittest sql.engines.test_mqtt sql.engines.test_rabbitmq
FAILED (errors=2)
ModuleNotFoundError: No module named 'django'
```

An isolated temporary virtual environment and a preload plugin supplying only
the Django settings/model shell needed by these unit tests were then used; both
were removed after testing. The committed test files were run unchanged:

```text
python -m pytest --confcutdir=sql/engines -p test_bootstrap
  -p no:cacheprovider sql/engines/test_mqtt.py
  sql/engines/test_rabbitmq.py -v

29 passed, 14 subtests passed in 0.51s
```

Optional live-broker smoke test:

```text
python -m pytest --confcutdir=sql/engines -p test_bootstrap
  -p no:cacheprovider sql/engines/test_mq_integration.py -v

1 passed, 3 skipped in 2.83s
```

The plaintext MQTT round trip passed. RabbitMQ plaintext and both mTLS cases
were skipped because their credentials/certificate environment was unavailable.

Additional checks:

```text
python -m compileall -q sql/engines/mqtt.py sql/engines/rabbitmq.py
  sql/engines/test_mqtt.py sql/engines/test_rabbitmq.py
git diff --check

Both exited successfully with no output.
```
