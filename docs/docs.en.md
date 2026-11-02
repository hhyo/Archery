# MySQL Database Design Guidelines (for reference)

## Contents

1. Background and purpose
2. Design guidelines
   - 2.1 Database design
     - 2.1.1 Database names
     - 2.1.2 Table structure
     - 2.1.3 Column data types
     - 2.1.4 Index design
     - 2.1.5 Sharding and partitioned tables
     - 2.1.6 Character sets
     - 2.1.7 Application DAO design
     - 2.1.8 Example table definition
   - 2.2 Writing SQL
     - 2.2.1 DML statements
     - 2.2.2 Joins
     - 2.2.3 Transactions
     - 2.2.4 Sorting and grouping
     - 2.2.5 SQL prohibited in production

## 1. Background and purpose

MySQL has strengths and limitations compared with Oracle and SQL Server. These guidelines help developers, QA engineers and operations teams design databases for production workloads. They cover database changes, table design and SQL practices intended to support reliable business systems.

## 2. Design guidelines

### 2.1 Database design

Rules use three priority levels: **HIGH RISK**, **REQUIRED** and **RECOMMENDED**, in descending order of priority. DBAs require changes to designs that violate HIGH RISK or REQUIRED rules.

### 2.1.1 Database names

1. **REQUIRED:** Keep database names within 32 characters. Related table names should convey their relationship, for example `user` and `user_login`.
2. **REQUIRED:** Use `business_system_subsystem` for database names and consistent prefixes for tables in the same module.
3. **REQUIRED:** Name shards using `database_prefix_number`, with numbering starting at zero, for example `wenda_001`. Time-based shards use `database_prefix_time`.
4. **REQUIRED:** Explicitly specify `utf8` or `utf8mb4` when creating a database. Example: `create database db1 default character set utf8;`.

### 2.1.2 Table structure

1. **REQUIRED:** Keep table and column names within 32 characters. Table names must use lowercase letters, numbers and underscores only.
2. **REQUIRED:** Table names must clearly identify their module. For example, use consistent module abbreviations as prefixes.
3. **REQUIRED:** Explicitly specify `utf8` or `utf8mb4` when creating a table.
4. **REQUIRED:** Explicitly specify a storage engine. Use InnoDB unless there is a specific reason otherwise. Engines other than InnoDB, MyISAM and MEMORY require DBA approval before production use. InnoDB is preferred for its transactions, row locking, crash recovery and MVCC support.
5. **REQUIRED:** Add a table comment.
6. **RECOMMENDED:** Use an auto-incrementing `id` of type `int` or `bigint` as the primary key. Store business identifiers such as `user_id` and `order_id` in separate columns with unique indexes. Randomly inserted primary-key values can cause InnoDB page splits and random I/O.
7. **RECOMMENDED:** Core tables, such as user and financial tables, should have `create_time` and `update_time` columns to support troubleshooting.
8. **RECOMMENDED:** Use `NOT NULL` columns and define defaults as appropriate. NULL values add storage overhead and can complicate migration and aggregation.
9. **RECOMMENDED:** Move large `blob` and `text` columns into separate tables and retrieve them only when needed.
10. **RECOMMENDED:** Consider denormalization for frequently joined attributes. For example, copying `user_name` into account and login-log tables can reduce joins.
11. **REQUIRED:** Prefix intermediate tables with `tmp_` and backup or snapshot tables with `bak_`. Clean them up regularly.
12. **REQUIRED:** `ALTER TABLE` on tables exceeding one million rows requires DBA approval and must run during off-peak hours. Table locking may block writes and significantly affect the application.

### 2.1.3 Column data types

1. **RECOMMENDED:** Use `bigint` for auto-increment columns to reduce the risk of exhausting the integer range. The signed `int` range is approximately -2.1 billion to 2.1 billion.
2. **RECOMMENDED:** Use `tinyint` or `smallint` for low-cardinality status and type columns.
3. **RECOMMENDED:** Store IPv4 addresses as `int` rather than `char(15)` to reduce storage. SQL conversions include `inet_aton('192.168.2.12')` and `inet_ntoa(3232236044)`; PHP provides `ip2long()` and `long2ip()`.
4. **RECOMMENDED:** Avoid `enum` and `set`; use `tinyint` or `smallint` for values that may change.
5. **RECOMMENDED:** Avoid large `blob` and `text` values unless the business requires them. Large values can increase disk and memory usage. In the COMPACT row format, large records may place a prefix on the original page and the remainder on overflow pages, increasing reads.
6. **RECOMMENDED:** Store money in an integer number of minor units, multiplying or dividing by 100 in the application, rather than using `double`.
7. **RECOMMENDED:** Prefer variable-length `varchar` over `char` for text. The MySQL row-size limit is 65,535 bytes; multibyte character sets reduce the available character count. The reference guideline recommends keeping `varchar` values within 2,700 characters and using larger text types only when necessary.
8. **RECOMMENDED:** Prefer `timestamp` for time values within its supported range. The reference guideline contrasts its four-byte representation with the older eight-byte `datetime` representation and notes the 1970–2038 range. An alternative is an integer Unix timestamp, converted with `unix_timestamp()` and `from_unixtime()`.

### 2.1.4 Index design

1. **REQUIRED:** InnoDB tables must use an auto-incrementing `id int/bigint` primary key. Do not update primary-key values.
2. **RECOMMENDED:** Use lowercase names beginning with `pk_` for primary keys, `uk_` or `uq_` for unique indexes, and `idx_` for ordinary indexes. Add the table or column name, or an abbreviation, as the suffix.
3. **REQUIRED:** Use BTREE indexes for InnoDB and MyISAM. MEMORY tables may use HASH or BTREE indexes as appropriate.
4. **REQUIRED:** Keep each index record within 64 KB, as specified by the reference guideline.
5. **RECOMMENDED:** Keep the number of indexes on a table within seven.
6. **RECOMMENDED:** Consider composite indexes and put the most selective column first. `select count(distinct userid)` can help assess the cardinality of `userid`.
7. **RECOMMENDED:** Index the join columns of the inner table in a multi-table join.
8. **RECOMMENDED:** Avoid redundant indexes. If `key(a,b)` exists, `key(a)` is normally redundant.

### 2.1.5 Sharding and partitioned tables

1. **REQUIRED:** Index the partition key, either on its own or as the first column of a composite index.
2. **REQUIRED:** Keep the total number of partitions, including subpartitions, within 1,024.
3. **REQUIRED:** Developers or DBAs must define partition creation and cleanup policies before production deployment.
4. **REQUIRED:** Queries against partitioned tables must include the partition key.
5. **RECOMMENDED:** Keep each partition file within 2 GB and the total within 50 GB. Aim for no more than 20 partitions.
6. **REQUIRED:** Run `ALTER TABLE` on partitioned tables during off-peak hours.
7. **REQUIRED:** Keep the number of database shards within 1,024.
8. **REQUIRED:** Keep the number of table shards within 4,096.
9. **RECOMMENDED:** Keep each table shard within five million rows and its `.ibd` file within 2 GB.
10. **RECOMMENDED:** Prefer modulo-based horizontal sharding. Consider date-based sharding for logs and reports.

### 2.1.6 Character sets

1. **REQUIRED:** Use the same character set, `utf8` or `utf8mb4`, for the database, tables and columns.
2. **REQUIRED:** Keep application connection and environment character sets consistent with the database. The reference guideline standardizes application connections on `utf8`.

### 2.1.7 Application DAO design

1. **RECOMMENDED:** For new code, consider explicitly written SQL with bound parameters instead of relying on model-generated SQL. Misused models can generate complex SQL and introduce conversion overhead.
2. **RECOMMENDED:** MySQL and Redis clients must have connection timeouts and reconnection behavior. Add a delay between retries.
3. **RECOMMENDED:** Preserve native MySQL or Redis error information where appropriate to support troubleshooting.
4. **RECOMMENDED:** Configure connection pools for the workload, including initial, minimum and maximum connections, timeouts and recycling. Poor settings can exhaust database connections.
5. **RECOMMENDED:** Define cleanup or archival policies for growing log and history tables before production deployment.
6. **RECOMMENDED:** Account for replication lag in application design. Avoid business impact from brief replica delays of up to 20 seconds. Route strongly consistent reads to the primary in a transaction, or allow a delay before reading a replica after an update.
7. **RECOMMENDED:** Prefer primary-key-based updates to reduce locking contention when concurrent requests modify the same InnoDB data.
8. **RECOMMENDED:** Acquire locks in a consistent order to reduce deadlocks.
9. **RECOMMENDED:** For hot rows or columns with a read/write ratio above 10:1, consider caching in Memcached or Redis to reduce MySQL load.

### 2.1.8 Example table definition

The following illustrates the reference naming and structure conventions:

```sql
CREATE TABLE user (
  `id` bigint(11) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(11) NOT NULL COMMENT 'User ID',
  `username` varchar(45) NOT NULL COMMENT 'Real name',
  `email` varchar(30) NOT NULL COMMENT 'Email address',
  `nickname` varchar(45) NOT NULL COMMENT 'Nickname',
  `avatar` int(11) NOT NULL COMMENT 'Avatar',
  `birthday` date NOT NULL COMMENT 'Date of birth',
  `sex` tinyint(4) DEFAULT '0' COMMENT 'Sex',
  `short_introduce` varchar(150) DEFAULT NULL COMMENT 'Short introduction, up to 50 Chinese characters',
  `user_resume` varchar(300) NOT NULL COMMENT 'Resume storage address',
  `user_register_ip` int NOT NULL COMMENT 'Registration source IP',
  `create_time` timestamp NOT NULL COMMENT 'Record creation time',
  `update_time` timestamp NOT NULL COMMENT 'Profile update time',
  `user_review_status` tinyint NOT NULL COMMENT 'Review status: 1 approved, 2 under review, 3 rejected, 4 not submitted',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_user_id` (`user_id`),
  KEY `idx_username`(`username`),
  KEY `idx_create_time`(`create_time`,`user_review_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='Website user information';
```

## 2.2 Writing SQL

### 2.2.1 DML statements

1. **REQUIRED:** Specify columns in `SELECT`; do not use `SELECT *`. Reading unnecessary columns increases network traffic and can cause model/schema mismatches after schema changes.
2. **REQUIRED:** Specify column names in `INSERT`; avoid `insert into t1 values (...)`.
3. **RECOMMENDED:** Keep multi-row `INSERT ... VALUES (...), (...)` batches within 5,000 rows to limit replication lag.
4. **RECOMMENDED:** Prefer `UNION ALL` to `UNION` when deduplication is unnecessary. Keep UNION clauses within five.
5. **RECOMMENDED:** Keep `IN` lists within 500 values to reduce scanning and database load.
6. **RECOMMENDED:** Use small batches for updates in transactions, with pauses where necessary.
7. **REQUIRED:** All tables in a transaction must use InnoDB, so failures can roll back consistently and avoid replication problems.
8. **REQUIRED:** Route writes and transactions to the primary, and read-only SQL to replicas.
9. **REQUIRED:** Except for static or small tables below 100 rows, DML must have a `WHERE` condition using an index lookup.
10. **REQUIRED:** Do not use optimizer hints such as `sql_no_cache`, `force index`, `ignore key` or `straight join` in production. Forced plans may become unsuitable as data changes.
11. **REQUIRED:** Match the types on both sides of equality comparisons in `WHERE` conditions to allow index use.
12. **RECOMMENDED:** Use indexed `WHERE` conditions for `SELECT`, `UPDATE`, `DELETE` and `REPLACE`.
13. **REQUIRED:** Avoid full scans on large production tables. Full scans may be acceptable for static tables below 100 rows. The reference guideline recommends keeping retrieved rows within 25% of a table to encourage index use.
14. **REQUIRED:** Do not rely solely on a fully wildcarded `LIKE` condition. Include another equality or range predicate that can use an index.
15. **RECOMMENDED:** Avoid functions and expressions on indexed columns, such as `length(name)='Admin'` or `user_id+2=10023`.
16. **RECOMMENDED:** Consider replacing `OR` predicates with separate indexed queries joined by `UNION`, for example separate predicates for `a=1` and `b=2`.
17. **RECOMMENDED:** For large pagination offsets, consider filtering by a key first. For example, replace `select a,b,c from t1 limit 10000,20` with a suitable key-based query such as `select a,b,c from t1 where id>10000 limit 20`.

### 2.2.2 Joins

1. **REQUIRED:** Avoid cross-database joins to reduce module coupling and support future database splitting.
2. **REQUIRED:** Do not use joins in application update statements, for example `update t1 join t2 ...`.
3. **RECOMMENDED:** Avoid subqueries where practical; consider multiple application queries or joins instead.
4. **RECOMMENDED:** Limit production joins to three tables.
5. **RECOMMENDED:** Use table aliases and qualify selected columns appropriately, using database and table names where needed.
6. **RECOMMENDED:** Prefer a table with a smaller result set as the driving table.

### 2.2.3 Transactions

1. **RECOMMENDED:** Keep rows affected by `INSERT`, `UPDATE`, `DELETE` and `REPLACE` in a transaction within 2,000, and `IN` lists within 500 values.
2. **RECOMMENDED:** Control the interval between batch transactions; the reference guideline suggests pauses of five to ten seconds where appropriate.
3. **RECOMMENDED:** Limit concurrent inserts into tables with auto-increment columns to 200.
4. **REQUIRED:** Account for isolation effects, including dirty reads, non-repeatable reads and phantom reads. The reference guideline recommends `repeatable-read` in production.
5. **RECOMMENDED:** Keep transactions within five SQL statements, except for payment workflows. Long transactions can hold locks and consume connections and buffers.
6. **RECOMMENDED:** Base transactional updates on primary or unique keys to reduce gap locking, wider lock ranges and deadlocks.
7. **RECOMMENDED:** Move external calls, such as web services and file-storage access, outside transactions where possible.
8. **RECOMMENDED:** Route reads that are strictly sensitive to replication lag to the primary within a transaction.

### 2.2.4 Sorting and grouping

1. **RECOMMENDED:** Avoid unnecessary sorting or move it to the application when appropriate. `ORDER BY`, `GROUP BY` and `DISTINCT` consume database CPU.
2. **RECOMMENDED:** Use indexes to retrieve already ordered data where possible. For example, `where a=1 order by b` can use `key(a,b)`.
3. **RECOMMENDED:** For queries using sorting, grouping or deduplication, keep the result after `WHERE` filtering within 1,000 rows where practical.

### 2.2.5 SQL prohibited in production

1. **HIGH RISK:** Avoid updates or deletes with `LIMIT`, such as `update|delete t1 ... where a=XX limit XX`, because they can cause replication inconsistencies. The reference guideline recommends adding `ORDER BY` on the primary key.
2. **HIGH RISK:** Do not use correlated subqueries in updates, such as `update t1 set ... where name in(select name from user where ...)`, because of poor efficiency.
3. **REQUIRED:** Do not use stored procedures, stored functions, triggers, views, events or foreign-key constraints under these reference rules. Implement the behavior in application code instead.
4. **REQUIRED:** Avoid `INSERT ... ON DUPLICATE KEY UPDATE` in high-concurrency workloads because the reference guideline identifies replication-consistency risks.
5. **REQUIRED:** Do not use multi-table updates such as `update t1,t2 where t1.id=t2.id ...`.
