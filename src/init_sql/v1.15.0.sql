-- 增加参数对比菜单权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 参数对比', @content_type_id, 'menu_param_compare');
