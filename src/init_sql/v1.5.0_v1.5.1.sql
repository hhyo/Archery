
ALTER TABLE sql_instance
  ADD `sid` varchar(50) DEFAULT NULL
COMMENT 'Oracle sid'
  AFTER password,
  ADD `service_name` varchar(50) DEFAULT NULL
COMMENT 'Oracle Service name'
  AFTER password;

alter table query_privileges_apply add `schema_list` longtext NOT NULL after db_list;

alter table query_privileges add `schema_name` varchar(64) NOT NULL after db_name;

alter table query_log add `schema_name` varchar(64) NOT NULL after db_name;
