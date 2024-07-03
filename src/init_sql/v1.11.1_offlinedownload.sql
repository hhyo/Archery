  alter table sql_workflow
  add column export_format varchar(10) DEFAULT NULL,
  add column is_offline_export varchar(3) NOT NULL,
  add column file_name varchar(255) DEFAULT NULL;


  set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
  insert IGNORE INTO auth_permission (name, content_type_id, codename) VALUES
('离线下载权限', @content_type_id, 'offline_download');