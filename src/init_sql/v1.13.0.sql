-- 工单表字段添加
ALTER TABLE sql_workflow
ADD COLUMN export_format VARCHAR(10) DEFAULT NULL,
ADD COLUMN is_offline_export TINYINT(1) NOT NULL,
ADD COLUMN file_name VARCHAR(255) DEFAULT NULL;

-- 权限添加
SET @content_type_id=(SELECT id FROM django_content_type WHERE app_label='sql' AND model='permission');
INSERT IGNORE INTO auth_permission (name, content_type_id, codename) 
VALUES
  ('离线下载权限', @content_type_id, 'offline_download'),
  ('菜单 数据导出', @content_type_id, 'menu_sqlexportworkflow'),
  ('提交数据导出', @content_type_id, 'sqlexport_submit');

-- 添加original_sql，存储原始语句
ALTER TABLE query_log ADD original_sql longtext NOT NULL AFTER sqllog;
-- 将历史数据空的original_sql更新成sqllog的内容
UPDATE query_log SET original_sql=sqllog WHERE original_sql = '';
