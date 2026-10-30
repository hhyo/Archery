# Debian 12 container baseline

The default application and standalone base images use Python 3.11 on Debian 12
(Bookworm). Debian 11 community LTS ended on 2026-08-31; archive repositories can
restore old builds but do not provide ongoing community security updates.
Bookworm LTS is scheduled through 2028-06-30. This is a compatibility step toward
a newer baseline, not a change to the application's Python version.

The application Dockerfile builds its base stage from the current checkout.
It no longer silently depends on the previously published Bullseye base tag.
An explicitly supplied `BASE_IMAGE` build argument can still select a separately
published base image. Both Dockerfiles share `setup.sh`.

```sh
docker build --platform linux/amd64 -f src/docker/Dockerfile-base -t archery-base:bookworm .
docker build --platform linux/amd64 -f src/docker/Dockerfile -t archery:bookworm .
docker run --rm --network none --entrypoint bash archery:bookworm /opt/archery/src/docker/smoke-test.sh
```

The smoke test does not start Archery, a worker, or any database connection. It
checks native Python driver imports, Oracle and ODBC client loading, nginx
configuration, SQLAdvisor library resolution and utility help/version commands.
It is run for application-image pull requests. Changes to `setup.sh` also trigger
the standalone base-image workflow.

Microsoft's Debian 12 repository package supplies its signing key and repository
configuration. Percona Toolkit uses its dedicated `pt` repository rather than
the obsolete Percona Server 5.7 repository. APT signature verification remains
enabled; Debian archive sources are not used.

The image remains amd64 because the bundled third-party tools and Oracle client
are amd64 binaries. Live database connectivity, SQL execution, external identity
providers and production rollout require separate integration validation. This
change does not upgrade the bundled legacy Mongo shell or other third-party tool
versions. Keep the previously deployed image digest available for rollback;
there are no database migrations associated with this container-base change.

References:
- https://lists.debian.org/debian-announce/2026/msg00008.html
- https://www.debian.org/releases/
- https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
- https://docs.percona.com/percona-toolkit/installation.html
