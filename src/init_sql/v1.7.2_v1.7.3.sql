-- 修改工具插件的菜单code
UPDATE auth_permission SET codename='menu_tools' WHERE codename='menu_menu_tools';

-- SQL上线工单增加需求链接
ALTER TABLE sql_workflow ADD demand_url varchar(500) NOT NULL DEFAULT '' COMMENT '需求链接';

-- 增加事务查看权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
INSERT IGNORE INTO auth_permission (name, content_type_id, codename) VALUES ('查看事务信息', @content_type_id, 'trx_view');

