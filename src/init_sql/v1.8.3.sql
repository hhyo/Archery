-- 增加登录审计日志
CREATE TABLE `audit_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `user_id` int(11) DEFAULT NULL COMMENT '用户id',
  `user_name` varchar(255) DEFAULT NULL COMMENT '用户名称',
  `ip` varchar(255) DEFAULT NULL COMMENT '登录ip',
  `action` varchar(255) DEFAULT NULL COMMENT '动作',
  `action_time` datetime(6) NOT NULL COMMENT '操作时间',
  PRIMARY KEY (`id`),
  KEY `idx_username` (`user_name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT='登录审计日志表';

-- 新增my2sql菜单权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 My2SQL', @content_type_id, 'menu_my2sql');

-- ssh 隧道功能修改
ALTER TABLE `ssh_tunnel` ADD COLUMN pkey longtext NULL AFTER password;

-- 审计功能增强 
alter table audit_log change `ip` `extra_info` longtext DEFAULT NULL COMMENT '额外的信息'; 
alter table audit_log add `user_display` varchar(50) DEFAULT NULL COMMENT '用户中文名'; 

set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
insert IGNORE INTO auth_permission (name, content_type_id, codename) VALUES
('审计权限', @content_type_id, 'audit_user');

-- 在线查询下载权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
insert IGNORE INTO auth_permission (name, content_type_id, codename) VALUES
('在线查询下载权限', @content_type_id, 'query_download');

-- 实例配置表新增mode字段，用于redis实例；为历史数据设置默认值
alter table sql_instance add column `mode` varchar(10) DEFAULT '' after `db_type`;
update sql_instance set mode='standalone' where db_type='redis';
