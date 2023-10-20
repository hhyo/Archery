-- 脱敏区分大小写支持，添加唯一键，避免同时配置同库同表同列添加两条脱敏规则
ALTER TABLE  data_masking_columns ADD COLUMN  case_sensitive TINYINT(1) NOT NULL default 0  comment '字段是否区分大小写' AFTER  column_name;
ALTER TABLE data_masking_columns ADD UNIQUE INDEX uk_instance_id_table_schema_table_name_column_name(instance_id,table_schema,table_name,column_name);