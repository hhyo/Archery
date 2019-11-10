-- 增加导出数据字典权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
INSERT IGNORE INTO auth_permission (name, content_type_id, codename) VALUES ('导出数据字典', @content_type_id, 'data_dictionary_export');
