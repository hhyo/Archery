-- 增加SQL统计菜单权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
INSERT IGNORE INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 SQL统计', @content_type_id, 'menu_sqlstats');

