-- 增加权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 SQL审核', @content_type_id, 'menu_sqlcheck');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 SQL分析', @content_type_id, 'menu_sqlanalyze');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('执行SQL分析', @content_type_id, 'sql_analyze');

