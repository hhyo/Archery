-- 增加权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 SQL审核', @content_type_id, 'menu_sqlcheck');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 SQL分析', @content_type_id, 'menu_sqlanalyze');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('执行SQL分析', @content_type_id, 'sql_analyze');

-- SQL工单、查询权限增加Instance外键，联级删除和更新
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
SET FOREIGN_KEY_CHECKS = 1;

-- 修改instance_id信息
UPDATE sql_workflow sw JOIN sql_instance si on sw.instance_name = si.instance_name SET sw.instance_id=si.id;
UPDATE query_privileges qp JOIN sql_instance si on qp.instance_name = si.instance_name SET qp.instance_id=si.id;
UPDATE query_privileges_apply qpa JOIN sql_instance si on qpa.instance_name = si.instance_name SET qpa.instance_id=si.id;

-- 删除instance_name
ALTER TABLE query_privileges DROP COLUMN instance_name;
ALTER TABLE query_privileges_apply DROP COLUMN instance_name;
ALTER TABLE sql_workflow DROP COLUMN instance_name;
