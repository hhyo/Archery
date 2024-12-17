-- https://github.com/hhyo/Archery/pull/2108
alter table instance_account
    add db_name varchar(128) default '' not null comment '数据库名（mongodb）' after host;

-- instance_account表调整唯一索引
-- set @drop_sql=(select concat('alter table instance_account drop index ', constraint_name) from information_schema.table_constraints where table_schema=database() and table_name='instance_account' and constraint_type='UNIQUE');
-- prepare stmt from @drop_sql;
-- execute stmt;
-- drop prepare stmt;
-- alter table instance_account add unique index uidx_instanceid_user_host_dbname(`instance_id`, `user`, `host`, `db_name`);

-- resolved delete uniq index: instance_account_instance_id_user_host_514c1ac6_uniq to raise fk error.
-- 禁用外键检查
SET foreign_key_checks = 0;
-- 删除外键约束
ALTER TABLE instance_account DROP FOREIGN KEY instance_account_instance_id_53a7a305_fk_sql_instance_id;
-- 删除不需要的唯一索引
ALTER TABLE instance_account DROP INDEX instance_account_instance_id_user_host_514c1ac6_uniq;
-- 添加新的唯一索引
ALTER TABLE instance_account ADD UNIQUE INDEX uidx_instanceid_user_host_dbname(`instance_id`, `user`, `host`, `db_name`);
-- 重新添加外键约束
ALTER TABLE instance_account ADD CONSTRAINT instance_account_instance_id_53a7a305_fk_sql_instance_id FOREIGN KEY (`instance_id`) REFERENCES sql_instance (`id`);
-- 重新启用外键检查
SET foreign_key_checks = 1;

--- 增加 ssl 支持
ALTER TABLE sql_instance ADD is_ssl tinyint(1) DEFAULT 0  COMMENT '是否启用SSL';
