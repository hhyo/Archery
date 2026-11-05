# Security dependency update

This update targets the Python 3.11/3.12 CI baseline independently of the
Python/Django/Debian migration in #3269.

| Dependency | Previous | Updated |
| --- | --- | --- |
| Requests | 2.31.0 | 2.34.2 |
| PyMySQL | 0.9.3 | 1.2.3 |
| mysql-replication | 0.22 | 1.0.17 |
| PyMongo | 4.6.3 | 4.18.3 |
| sshtunnel | 0.1.5 | 0.5.1 |
| Paramiko | transitive, unbounded | 5.1.0 |

Requests and the two database drivers replace versions affected by published
security advisories. PyMongo 4.18.3 covers the fixes identified in this review
without taking 4.19's additional Python-version removals. sshtunnel 0.5.1
supports modern Paramiko versions that no longer expose `DSSKey`. Paramiko is
now declared explicitly because Archery imports its RSA-key API directly.

## Compatibility boundaries

- The selected Requests release requires Python 3.10 or newer. The repository's
  tested Python 3.11/3.12 baseline is retained; Python 3.14 remains separate work.
- **PyMongo 4.18 requires MongoDB Server 4.4 or newer.** MongoDB 3.6, 4.0 and 4.2
  installations supported by the old driver must be upgraded before adopting
  this dependency set. No database server is upgraded by this code change.
- PyMySQL escaping now uses `pymysql.converters.escape_string`, the supported
  location for the existing API. Escaping semantics and account/SQL validation
  rules are unchanged. Its legacy top-level import is no longer used by MySQL,
  GoInception, TDengine or slow-log handling.
- The binlog-reader dependency is upgraded with PyMySQL because version 0.22
  imports the removed `pymysql.util` module. Reader import is covered without
  starting replication or contacting a server.
- SSH password/RSA initialization is exercised against the real dependencies
  without starting a tunnel or contacting a server. Production SSH policies and
  database authentication still require integration validation before rollout.

The regression tests cover quote, backslash, control-character and Unicode
escaping, literal quoting, and SSH key discovery/forwarder initialization.
Full-suite tests use disposable internal-only MySQL/Redis services. Security
scanning of the six exact target versions is a dependency advisory check,
not a proof that all application paths or transitive dependencies are safe.

References:
- https://github.com/psf/requests/security/advisories
- https://github.com/advisories/GHSA-v9hf-5j83-6xpp
- https://github.com/mongodb/mongo-python-driver/security/advisories
- https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/upgrade/
- https://pypi.org/project/sshtunnel/0.5.1/
