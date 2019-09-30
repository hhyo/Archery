--  删除Themis权限
set @perm_id=(select id from auth_permission where codename='menu_themis');
delete from auth_group_permissions where permission_id=@perm_id;
delete from sql_users_user_permissions where permission_id=@perm_id;
delete from auth_permission where codename='menu_themis';
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
-- 增加实例账号管理权限，变更菜单权限信息
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 管理实例账号', @content_type_id, 'instance_account_manage');
UPDATE auth_permission set name='菜单 实例账号管理',codename='menu_instance_account' where codename='menu_instance_user';
-- 增加实例数据库权限
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 数据库管理', @content_type_id, 'menu_database');
-- 增加资源组粒度的查询权限
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('可查询所在资源组内的所有实例', @content_type_id, 'query_resource_group_instance');
-- 增加工具插件的权限
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 工具插件', @content_type_id, 'menu_menu_tools');

-- 添加钉钉user id
alter table sql_users
  add ding_user_id varchar(64) default null comment '钉钉user_id';


-- 增加实例账号表
CREATE TABLE `instance_account` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user` varchar(128) NOT NULL COMMENT '账号',
  `host` varchar(64) NOT NULL COMMENT '主机',
  `password` varchar(128) NOT NULL COMMENT '密码',
  `remark` varchar(255) NOT NULL COMMENT '备注',
  `sys_time` datetime(6) NOT NULL COMMENT '系统时间',
  `instance_id` int(11) NOT NULL COMMENT '实例',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_instance_id_user_host` (`instance_id`,`user`,`host`),
  CONSTRAINT `fk_account_sql_instance_id` FOREIGN KEY (`instance_id`) REFERENCES `sql_instance` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- 增加实例数据库表
CREATE TABLE `instance_database` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `db_name` varchar(128) NOT NULL COMMENT '账号',
  `owner` varchar(30) NOT NULL COMMENT '负责人',
  `owner_display` varchar(50) NOT NULL DEFAULT '负责人中文名',
  `remark` varchar(255) NOT NULL COMMENT '备注',
  `sys_time` datetime(6) NOT NULL COMMENT '系统时间',
  `instance_id` int(11) NOT NULL COMMENT '实例',
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_database_sql_instance_id` FOREIGN KEY (`instance_id`) REFERENCES `sql_instance` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


