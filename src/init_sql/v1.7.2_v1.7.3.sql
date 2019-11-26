-- 修改工具插件的菜单code
UPDATE auth_permission SET codename='menu_tools' WHERE codename='menu_menu_tools';

-- SQL上线工单增加需求链接
ALTER TABLE sql_workflow ADD demand_url varchar(500) NOT NULL DEFAULT '' COMMENT '需求链接';