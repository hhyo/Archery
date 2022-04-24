-- 新增openapi菜单权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 OpenAPI', @content_type_id, 'menu_openapi');
