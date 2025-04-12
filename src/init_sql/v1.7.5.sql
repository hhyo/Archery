-- 增加归档相关权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
insert IGNORE INTO auth_permission (name, content_type_id, codename) VALUES
('菜单 数据归档', @content_type_id, 'menu_archive'),
('提交归档申请', @content_type_id, 'archive_apply'),
('审核归档申请', @content_type_id, 'archive_audit'),
('管理归档申请', @content_type_id, 'archive_mgt');

-- 归档配置表
CREATE TABLE `archive_config` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `title` varchar(50) NOT NULL COMMENT '归档配置说明',
  `resource_group_id` int(11) NOT NULL COMMENT '资源组',
  `audit_auth_groups` varchar(255) NOT NULL COMMENT '审批权限组列表',
  `src_instance_id` int(11) NOT NULL COMMENT '源实例',
  `src_db_name` varchar(64) NOT NULL COMMENT '源数据库',
  `src_table_name` varchar(64) NOT NULL COMMENT '源表',
  `dest_instance_id` int(11) DEFAULT NULL COMMENT '目标实例',
  `dest_db_name` varchar(64) DEFAULT NULL COMMENT '目标数据库',
  `dest_table_name` varchar(64) DEFAULT NULL COMMENT '目标表',
  `condition` varchar(1000) NOT NULL COMMENT '归档条件，where条件',
  `mode` varchar(10) NOT NULL COMMENT '归档模式',
  `no_delete` tinyint(1) NOT NULL COMMENT '是否保留源数据',
  `sleep` int(11) NOT NULL COMMENT '归档limit行记录后的休眠秒数',
  `status` int(11) NOT NULL COMMENT '审核状态',
  `state` tinyint(1) NOT NULL COMMENT '是否启用归档',
  `user_name` varchar(30) NOT NULL COMMENT '申请人',
  `user_display` varchar(50) NOT NULL COMMENT '申请人中文名',
  `create_time` datetime(6) NOT NULL COMMENT '创建时间',
  `last_archive_time` datetime(6) DEFAULT NULL COMMENT '最近归档时间',
  `sys_time` datetime(6) NOT NULL COMMENT '系统时间修改',
  PRIMARY KEY (`id`),
  KEY `idx_dest_instance_id` (`dest_instance_id`),
  KEY `idx_resource_group_id` (`resource_group_id`),
  KEY `idx_src_instance_id` (`src_instance_id`),
  CONSTRAINT `fk_archive_dest_instance_id` FOREIGN KEY (`dest_instance_id`) REFERENCES `sql_instance` (`id`),
  CONSTRAINT `fk_archive_resource_id` FOREIGN KEY (`resource_group_id`) REFERENCES `resource_group` (`group_id`),
  CONSTRAINT `fk_archive_src_instance_id` FOREIGN KEY (`src_instance_id`) REFERENCES `sql_instance` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '归档配置表';

-- 归档日志表
CREATE TABLE `archive_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `archive_id` int(11) NOT NULL COMMENT '归档配置ID',
  `cmd` varchar(2000) NOT NULL COMMENT '归档命令',
  `condition` varchar(1000) NOT NULL COMMENT '归档条件',
  `mode` varchar(10) NOT NULL COMMENT '归档模式',
  `no_delete` tinyint(1) NOT NULL COMMENT '是否保留源数据',
  `sleep` int(11) NOT NULL COMMENT '归档limit行记录后的休眠秒数',
  `select_cnt` int(11) NOT NULL COMMENT '查询数量',
  `insert_cnt` int(11) NOT NULL COMMENT '插入数量',
  `delete_cnt` int(11) NOT NULL COMMENT '删除数量',
  `statistics` longtext NOT NULL COMMENT '归档统计日志',
  `success` tinyint(1) NOT NULL COMMENT '是否归档成功',
  `error_info` longtext NOT NULL COMMENT '错误信息',
  `start_time` datetime(6) NOT NULL COMMENT '开始时间',
  `end_time` datetime(6) NOT NULL COMMENT '结束时间',
  `sys_time` datetime(6) NOT NULL COMMENT '系统时间修改',
  PRIMARY KEY (`id`),
  KEY `idx_archive_id` (`archive_id`),
  CONSTRAINT `fk_archive_config_id` FOREIGN KEY (`archive_id`) REFERENCES `archive_config` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '归档日志表';
