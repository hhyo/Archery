-- 增加权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 SQL审核', @content_type_id, 'menu_sqlcheck');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 SQL分析', @content_type_id, 'menu_sqlanalyze');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('执行SQL分析', @content_type_id, 'sql_analyze');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('执行SQL上线工单(资源组粒度)', @content_type_id, 'sql_execute_for_resource_group');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('清理BINLOG日志', @content_type_id, 'binlog_del');


-- SQL工单、查询权限、RDS、脱敏配置增加Instance外键，设置为CASCADE级联操作，通过管理后台删除数据时
SET FOREIGN_KEY_CHECKS = 0;
ALTER TABLE sql_workflow
  ADD COLUMN instance_id int(11) NOT NULL AFTER group_name,
  ADD INDEX idx_instance_id (instance_id) USING BTREE,
  ADD CONSTRAINT fk_workflow_instance FOREIGN KEY fk_workflow_instance (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE query_privileges
  ADD COLUMN instance_id int(11) NOT NULL AFTER user_display,
  ADD INDEX idx_instance_id (instance_id) USING BTREE,
  ADD CONSTRAINT fk_query_priv_instance FOREIGN KEY fk_query_priv_instance (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE query_privileges_apply
  ADD COLUMN instance_id int(11) NOT NULL AFTER user_display,
  ADD INDEX idx_instance_id (instance_id) USING BTREE,
  ADD CONSTRAINT fk_query_priv_apply_instance FOREIGN KEY fk_query_priv_apply_instance (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE data_masking_columns
  ADD COLUMN instance_id int(11) NOT NULL AFTER active,
  ADD INDEX idx_instance_id (instance_id) USING BTREE,
  ADD CONSTRAINT fk_data_mask_instance FOREIGN KEY fk_data_mask_instance (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE aliyun_rds_config
  ADD COLUMN instance_id int(11) NOT NULL FIRST,
  ADD INDEX idx_instance_id (instance_id) USING BTREE,
  ADD CONSTRAINT fk_rds_instance FOREIGN KEY fk_rds_instance (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
SET FOREIGN_KEY_CHECKS = 1;

-- 修改instance_id信息，如果有修改过instance_name，可能导致部分数据无法匹配，请手工订正
UPDATE sql_workflow sw JOIN sql_instance si on sw.instance_name = si.instance_name SET sw.instance_id=si.id;
UPDATE query_privileges qp JOIN sql_instance si on qp.instance_name = si.instance_name SET qp.instance_id=si.id;
UPDATE query_privileges_apply qpa JOIN sql_instance si on qpa.instance_name = si.instance_name SET qpa.instance_id=si.id;
UPDATE data_masking_columns dmc JOIN sql_instance si on dmc.instance_name = si.instance_name SET dmc.instance_id=si.id;
UPDATE aliyun_rds_config rds JOIN sql_instance si on rds.instance_name = si.instance_name SET rds.instance_id=si.id;

-- 删除instance_name
ALTER TABLE query_privileges DROP COLUMN instance_name;
ALTER TABLE query_privileges_apply DROP COLUMN instance_name;
ALTER TABLE sql_workflow DROP COLUMN instance_name;
ALTER TABLE data_masking_columns DROP COLUMN instance_name;
ALTER TABLE aliyun_rds_config DROP COLUMN instance_name;


-- 修改字段名称sql_syntax为syntax_type，删除audit_remark和reviewok_time
ALTER TABLE sql_workflow 
  CHANGE sql_syntax  syntax_type tinyint(4) NOT NULL DEFAULT '0' COMMENT '工单类型 1、DDL，2、DML',
  DROP audit_remark,
  DROP reviewok_time;

-- 修改db_name/table_name长度为64
ALTER TABLE sql_workflow MODIFY  db_name varchar(64) NOT NULL DEFAULT '' COMMENT '数据库' AFTER instance_id;
ALTER TABLE query_privileges MODIFY  db_name varchar(64) NOT NULL DEFAULT '' COMMENT '数据库' AFTER instance_id;
ALTER TABLE query_privileges MODIFY  table_name varchar(64) NOT NULL DEFAULT '' COMMENT '表' AFTER instance_id;
ALTER TABLE query_log MODIFY db_name varchar(64) NOT NULL DEFAULT '' COMMENT '数据库' AFTER instance_name;



-- 将SQL工单的大字段拆分到单独的内容表
CREATE TABLE sql_workflow_content(
  id             int(11)  NOT NULL AUTO_INCREMENT PRIMARY KEY,
  workflow_id    int(11)  NOT NULL COMMENT 'SQL工单ID',
  sql_content    longtext NOT NULL COMMENT '提交的SQL文本',
  review_content longtext NOT NULL COMMENT '自动审核内容的JSON格式',
  execute_result longtext NOT NULL COMMENT '执行结果的JSON格式',
  UNIQUE KEY uniq_workflow_id (workflow_id) USING BTREE,
  CONSTRAINT fk_cont_workflow FOREIGN KEY fk_cont_workflow (workflow_id) REFERENCES sql_workflow (id) ON DELETE RESTRICT ON UPDATE RESTRICT
);
-- 数据迁移
SET FOREIGN_KEY_CHECKS = 0;
INSERT INTO sql_workflow_content (workflow_id, review_content, sql_content, execute_result)
SELECT id, review_content, sql_content, execute_result
FROM sql_workflow;
SET FOREIGN_KEY_CHECKS = 1;
-- 字段删除
ALTER TABLE sql_workflow DROP sql_content, DROP review_content, DROP execute_result;
