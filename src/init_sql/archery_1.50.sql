/*
 Navicat Premium Data Transfer

 Source Server         : archery-1.50
 Source Server Type    : MySQL
 Source Server Version : 50722
 Source Host           : 10.10.51.222:3307
 Source Schema         : archery_new

 Target Server Type    : MySQL
 Target Server Version : 50722
 File Encoding         : 65001

 Date: 17/04/2019 15:13:10
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for aliyun_access_key
-- ----------------------------
DROP TABLE IF EXISTS `aliyun_access_key`;
CREATE TABLE `aliyun_access_key` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ak` varchar(50) NOT NULL,
  `secret` varchar(100) NOT NULL,
  `is_enable` tinyint(4) NOT NULL COMMENT '是否启用',
  `remark` varchar(50) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for aliyun_rds_config
-- ----------------------------
DROP TABLE IF EXISTS `aliyun_rds_config`;
CREATE TABLE `aliyun_rds_config` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `instance_id` int(11) NOT NULL,
  `rds_dbinstanceid` varchar(100) NOT NULL,
  `is_enable` tinyint(4) NOT NULL COMMENT '是否启用',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_uni_iid` (`instance_id`),
  CONSTRAINT `fk_instanid__sql_instance_id` FOREIGN KEY (`instance_id`) REFERENCES `sql_instance` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for auth_group
-- ----------------------------
DROP TABLE IF EXISTS `auth_group`;
CREATE TABLE `auth_group` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `name` varchar(80) NOT NULL COMMENT '组',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='权限组';

-- ----------------------------
-- Table structure for auth_group_permissions
-- ----------------------------
DROP TABLE IF EXISTS `auth_group_permissions`;
CREATE TABLE `auth_group_permissions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `group_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_uni_gid_pid` (`group_id`,`permission_id`),
  KEY `idx_pid` (`permission_id`),
  CONSTRAINT `fk_groupid__auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `fk_perid__auth_permission_id` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for auth_permission
-- ----------------------------
DROP TABLE IF EXISTS `auth_permission`;
CREATE TABLE `auth_permission` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int(11) NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_uni_ctid` (`content_type_id`,`codename`),
  CONSTRAINT `fk_ctypeid__django_content_type_id` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=137 DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for data_masking_columns
-- ----------------------------
DROP TABLE IF EXISTS `data_masking_columns`;
CREATE TABLE `data_masking_columns` (
  `column_id` int(11) NOT NULL AUTO_INCREMENT,
  `rule_type` int(11) NOT NULL,
  `active` tinyint(4) NOT NULL COMMENT '激活状态',
  `instance_id` int(11) NOT NULL,
  `table_schema` varchar(64) NOT NULL,
  `table_name` varchar(64) NOT NULL,
  `column_name` varchar(64) NOT NULL,
  `column_comment` varchar(1024) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`column_id`),
  KEY `idx_iid` (`instance_id`),
  CONSTRAINT `fk_instance_id__sql_instance_id` FOREIGN KEY (`instance_id`) REFERENCES `sql_instance` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for data_masking_rules
-- ----------------------------
DROP TABLE IF EXISTS `data_masking_rules`;
CREATE TABLE `data_masking_rules` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `rule_type` int(11) NOT NULL,
  `rule_regex` varchar(255) NOT NULL,
  `hide_group` int(11) NOT NULL,
  `rule_desc` varchar(100) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_uni_rule_type` (`rule_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for django_admin_log
-- ----------------------------
DROP TABLE IF EXISTS `django_admin_log`;
CREATE TABLE `django_admin_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint(5) unsigned NOT NULL,
  `change_message` longtext NOT NULL,
  `content_type_id` int(11) DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ctid` (`content_type_id`),
  KEY `idx_uid` (`user_id`),
  CONSTRAINT `fk_ctid__django_content_type_id` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `fk_users_id__sql_users_id` FOREIGN KEY (`user_id`) REFERENCES `sql_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for django_content_type
-- ----------------------------
DROP TABLE IF EXISTS `django_content_type`;
CREATE TABLE `django_content_type` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_uni_app_label__model` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=34 DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for django_migrations
-- ----------------------------
DROP TABLE IF EXISTS `django_migrations`;
CREATE TABLE `django_migrations` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for django_q_ormq
-- ----------------------------
DROP TABLE IF EXISTS `django_q_ormq`;
CREATE TABLE `django_q_ormq` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `key` varchar(100) NOT NULL,
  `payload` longtext NOT NULL,
  `lock` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for django_q_schedule
-- ----------------------------
DROP TABLE IF EXISTS `django_q_schedule`;
CREATE TABLE `django_q_schedule` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `func` varchar(256) NOT NULL,
  `hook` varchar(256) DEFAULT NULL,
  `args` longtext,
  `kwargs` longtext,
  `schedule_type` varchar(1) NOT NULL,
  `repeats` int(11) NOT NULL,
  `next_run` datetime(6) DEFAULT NULL,
  `task` varchar(100) DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL,
  `minutes` smallint(5) unsigned DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for django_q_task
-- ----------------------------
DROP TABLE IF EXISTS `django_q_task`;
CREATE TABLE `django_q_task` (
  `id` varchar(32) NOT NULL,
  `name` varchar(100) NOT NULL,
  `func` varchar(256) NOT NULL,
  `hook` varchar(256) DEFAULT NULL,
  `args` longtext,
  `kwargs` longtext,
  `result` longtext,
  `started` datetime(6) NOT NULL,
  `stopped` datetime(6) NOT NULL,
  `success` tinyint(4) NOT NULL,
  `group` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for django_session
-- ----------------------------
DROP TABLE IF EXISTS `django_session`;
CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `idx_expire_date` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for param_history
-- ----------------------------
DROP TABLE IF EXISTS `param_history`;
CREATE TABLE `param_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `instance_id` int(11) NOT NULL COMMENT '实例ID',
  `variable_name` varchar(64) NOT NULL COMMENT '参数名',
  `old_var` varchar(1024) NOT NULL COMMENT '修改前参数值',
  `new_var` varchar(1024) NOT NULL COMMENT '修改后参数值',
  `set_sql` varchar(1024) NOT NULL COMMENT '在线变更配置执行的SQL语句',
  `user_name` varchar(30) NOT NULL COMMENT '修改人',
  `user_display` varchar(50) NOT NULL COMMENT '修改人中文名',
  `update_time` datetime(6) NOT NULL COMMENT '修改时间',
  PRIMARY KEY (`id`),
  KEY `idx_iid` (`instance_id`),
  CONSTRAINT `fk_instanceid__sql_instance_id` FOREIGN KEY (`instance_id`) REFERENCES `sql_instance` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for param_template
-- ----------------------------
DROP TABLE IF EXISTS `param_template`;
CREATE TABLE `param_template` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `db_type` varchar(10) NOT NULL COMMENT '数据库类型，mysql、mssql、redis、pgsql',
  `variable_name` varchar(64) NOT NULL COMMENT '参数名',
  `default_value` varchar(1024) NOT NULL COMMENT '默认参数值',
  `editable` tinyint(4) NOT NULL COMMENT '是否支持修改',
  `valid_values` varchar(1024) NOT NULL COMMENT '有效参数值',
  `description` varchar(1024) NOT NULL COMMENT '参数描述',
  `create_time` datetime(6) NOT NULL COMMENT '创建时间',
  `sys_time` datetime(6) NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_uni_db_type__variable_name` (`db_type`,`variable_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for query_log
-- ----------------------------
DROP TABLE IF EXISTS `query_log`;
CREATE TABLE `query_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `instance_name` varchar(50) NOT NULL,
  `db_name` varchar(64) NOT NULL,
  `sqllog` longtext NOT NULL,
  `effect_row` bigint(20) NOT NULL,
  `cost_time` varchar(10) NOT NULL,
  `username` varchar(30) NOT NULL,
  `user_display` varchar(50) NOT NULL,
  `priv_check` tinyint(4) NOT NULL COMMENT '查询权限是否正常校验',
  `hit_rule` tinyint(4) NOT NULL COMMENT '查询是否命中脱敏规则',
  `masking` tinyint(4) NOT NULL COMMENT '查询结果是否正常脱敏',
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for query_privileges
-- ----------------------------
DROP TABLE IF EXISTS `query_privileges`;
CREATE TABLE `query_privileges` (
  `privilege_id` int(11) NOT NULL AUTO_INCREMENT COMMENT '权限id',
  `user_name` varchar(30) NOT NULL COMMENT '用户',
  `user_display` varchar(50) NOT NULL COMMENT '下拉菜单筛选名',
  `instance_id` int(11) NOT NULL,
  `table_name` varchar(64) NOT NULL COMMENT '表',
  `db_name` varchar(64) NOT NULL COMMENT '数据库',
  `valid_date` date NOT NULL COMMENT '有效时间',
  `limit_num` int(11) NOT NULL COMMENT '结果集',
  `priv_type` tinyint(4) NOT NULL COMMENT '权限级别',
  `is_deleted` tinyint(4) NOT NULL COMMENT '删除标记',
  `create_time` datetime(6) NOT NULL COMMENT '申请时间',
  `sys_time` datetime(6) NOT NULL COMMENT '系统时间',
  PRIMARY KEY (`privilege_id`),
  KEY `idx_uname__iid__db_name__vdate` (`user_name`,`instance_id`,`db_name`,`valid_date`),
  KEY `idx_iid` (`instance_id`),
  CONSTRAINT `fk_instid__sql_instance_id` FOREIGN KEY (`instance_id`) REFERENCES `sql_instance` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for query_privileges_apply
-- ----------------------------
DROP TABLE IF EXISTS `query_privileges_apply`;
CREATE TABLE `query_privileges_apply` (
  `apply_id` int(11) NOT NULL AUTO_INCREMENT,
  `group_id` int(11) NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `title` varchar(50) NOT NULL,
  `user_name` varchar(30) NOT NULL,
  `user_display` varchar(50) NOT NULL,
  `instance_id` int(11) NOT NULL,
  `db_list` longtext NOT NULL,
  `table_list` longtext NOT NULL,
  `valid_date` date NOT NULL,
  `limit_num` int(11) NOT NULL,
  `priv_type` tinyint(4) NOT NULL,
  `status` int(11) NOT NULL,
  `audit_auth_groups` varchar(255) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`apply_id`),
  KEY `idx_iid` (`instance_id`),
  CONSTRAINT `fk_insid__sql_instance_id` FOREIGN KEY (`instance_id`) REFERENCES `sql_instance` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for resource_group
-- ----------------------------
DROP TABLE IF EXISTS `resource_group`;
CREATE TABLE `resource_group` (
  `group_id` int(11) NOT NULL AUTO_INCREMENT,
  `group_name` varchar(100) NOT NULL,
  `group_parent_id` bigint(20) NOT NULL,
  `group_sort` int(11) NOT NULL,
  `group_level` int(11) NOT NULL,
  `ding_webhook` varchar(255) NOT NULL,
  `is_deleted` tinyint(4) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`group_id`),
  UNIQUE KEY `idx_uni_group_name` (`group_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for resource_group_relations
-- ----------------------------
DROP TABLE IF EXISTS `resource_group_relations`;
CREATE TABLE `resource_group_relations` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `object_type` tinyint(4) NOT NULL,
  `object_id` int(11) NOT NULL,
  `object_name` varchar(100) NOT NULL,
  `group_id` int(11) NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_uni_oid__gid__object_type` (`object_id`,`group_id`,`object_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for sql_config
-- ----------------------------
DROP TABLE IF EXISTS `sql_config`;
CREATE TABLE `sql_config` (
  `item` varchar(50) NOT NULL,
  `value` varchar(200) NOT NULL,
  `description` varchar(200) NOT NULL,
  PRIMARY KEY (`item`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for sql_instance
-- ----------------------------
DROP TABLE IF EXISTS `sql_instance`;
CREATE TABLE `sql_instance` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `instance_name` varchar(50) NOT NULL,
  `type` varchar(6) NOT NULL,
  `db_type` varchar(10) NOT NULL,
  `host` varchar(200) NOT NULL,
  `port` int(11) NOT NULL,
  `user` varchar(100) NOT NULL,
  `password` varchar(300) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `update_time` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_uni_instance_name` (`instance_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for sql_permission
-- ----------------------------
DROP TABLE IF EXISTS `sql_permission`;
CREATE TABLE `sql_permission` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for sql_users
-- ----------------------------
DROP TABLE IF EXISTS `sql_users`;
CREATE TABLE `sql_users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `PASSWORD` varchar(128) NOT NULL COMMENT '密码',
  `last_login` datetime(6) NOT NULL COMMENT '上次登录',
  `is_superuser` tinyint(4) NOT NULL COMMENT '超级用户状态:1是,0否',
  `username` varchar(150) NOT NULL COMMENT '用户名',
  `first_name` varchar(30) NOT NULL COMMENT '名,无值',
  `last_name` varchar(150) NOT NULL COMMENT '姓,无值',
  `email` varchar(254) NOT NULL COMMENT '电子邮箱地址',
  `is_staff` tinyint(4) NOT NULL COMMENT '职员状态(是否能管理django后台):1是,0否',
  `is_active` tinyint(4) NOT NULL COMMENT '有效(禁用用户标签):1是,0否',
  `date_joined` datetime(6) NOT NULL COMMENT '加入日期(第一次登录时间)',
  `display` varchar(50) NOT NULL COMMENT '显示的中文名',
  `failed_login_count` int(11) NOT NULL COMMENT '登陆失败次数',
  `last_login_failed_at` datetime DEFAULT NULL COMMENT '上次失败登录时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_uni_username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for sql_users_groups
-- ----------------------------
DROP TABLE IF EXISTS `sql_users_groups`;
CREATE TABLE `sql_users_groups` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `users_id` int(11) NOT NULL,
  `group_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_uni_uid__gid` (`users_id`,`group_id`),
  KEY `idx_gid` (`group_id`),
  CONSTRAINT `fk_gid__auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `fk_usersid__sql_users_id` FOREIGN KEY (`users_id`) REFERENCES `sql_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for sql_users_user_permissions
-- ----------------------------
DROP TABLE IF EXISTS `sql_users_user_permissions`;
CREATE TABLE `sql_users_user_permissions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `users_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_uni_uid__pid` (`users_id`,`permission_id`),
  KEY `idx_pid` (`permission_id`),
  CONSTRAINT `fk_pid__auth_permission_id` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `fk_uid__sql_users_id` FOREIGN KEY (`users_id`) REFERENCES `sql_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for sql_workflow
-- ----------------------------
DROP TABLE IF EXISTS `sql_workflow`;
CREATE TABLE `sql_workflow` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `workflow_name` varchar(50) NOT NULL,
  `group_id` int(11) NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `instance_id` int(11) NOT NULL,
  `db_name` varchar(64) NOT NULL COMMENT '数据库',
  `engineer` varchar(30) NOT NULL,
  `engineer_display` varchar(50) NOT NULL,
  `audit_auth_groups` varchar(255) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `finish_time` datetime(6) DEFAULT NULL,
  `STATUS` varchar(50) NOT NULL,
  `is_backup` tinyint(4) NOT NULL COMMENT '是否备份',
  `is_manual` tinyint(4) NOT NULL,
  `syntax_type` tinyint(4) NOT NULL COMMENT '工单类型 1、DDL，2、DML',
  PRIMARY KEY (`id`),
  KEY `idx_iid` (`instance_id`),
  CONSTRAINT `fk_iid__sql_instance_id` FOREIGN KEY (`instance_id`) REFERENCES `sql_instance` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for sql_workflow_content
-- ----------------------------
DROP TABLE IF EXISTS `sql_workflow_content`;
CREATE TABLE `sql_workflow_content` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `workflow_id` int(11) NOT NULL COMMENT 'SQL工单ID',
  `sql_content` longtext NOT NULL COMMENT '提交的SQL文本',
  `review_content` longtext NOT NULL COMMENT '自动审核内容的JSON格式',
  `execute_result` longtext NOT NULL COMMENT '执行结果的JSON格式',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_uni_workflow_id` (`workflow_id`),
  CONSTRAINT `fk_wfid__sql_workflow_id` FOREIGN KEY (`workflow_id`) REFERENCES `sql_workflow` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for workflow_audit
-- ----------------------------
DROP TABLE IF EXISTS `workflow_audit`;
CREATE TABLE `workflow_audit` (
  `audit_id` int(11) NOT NULL AUTO_INCREMENT,
  `group_id` int(11) NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `workflow_id` bigint(20) NOT NULL,
  `workflow_type` tinyint(4) NOT NULL,
  `workflow_title` varchar(50) NOT NULL,
  `workflow_remark` varchar(140) NOT NULL,
  `audit_auth_groups` varchar(255) NOT NULL,
  `current_audit` varchar(20) NOT NULL,
  `next_audit` varchar(20) NOT NULL,
  `current_status` tinyint(4) NOT NULL,
  `create_user` varchar(30) NOT NULL,
  `create_user_display` varchar(50) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`audit_id`),
  UNIQUE KEY `idx_uni_wfid__workflow_type` (`workflow_id`,`workflow_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for workflow_audit_detail
-- ----------------------------
DROP TABLE IF EXISTS `workflow_audit_detail`;
CREATE TABLE `workflow_audit_detail` (
  `audit_detail_id` int(11) NOT NULL AUTO_INCREMENT,
  `audit_id` int(11) NOT NULL,
  `audit_user` varchar(30) NOT NULL,
  `audit_time` datetime(6) NOT NULL,
  `audit_status` tinyint(4) NOT NULL,
  `remark` varchar(140) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`audit_detail_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for workflow_audit_setting
-- ----------------------------
DROP TABLE IF EXISTS `workflow_audit_setting`;
CREATE TABLE `workflow_audit_setting` (
  `audit_setting_id` int(11) NOT NULL AUTO_INCREMENT,
  `group_id` int(11) NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `workflow_type` tinyint(4) NOT NULL,
  `audit_auth_groups` varchar(255) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`audit_setting_id`),
  UNIQUE KEY `idx_uni_gid__workflow_type` (`group_id`,`workflow_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for workflow_log
-- ----------------------------
DROP TABLE IF EXISTS `workflow_log`;
CREATE TABLE `workflow_log` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `audit_id` bigint(20) NOT NULL COMMENT '工单审批id',
  `operation_type` tinyint(4) NOT NULL COMMENT '操作类型，0提交/待审核、1审核通过、2审核不通过、3审核取消/取消执行、4定时执行、5执行工单、6执行结束',
  `operation_type_desc` char(10) NOT NULL COMMENT '操作类型描述',
  `operation_info` varchar(200) NOT NULL COMMENT '操作信息',
  `operator` varchar(30) NOT NULL COMMENT '操作人',
  `operator_display` varchar(50) NOT NULL COMMENT '操作人中文名',
  `operation_time` datetime(6) NOT NULL COMMENT '操作时间',
  PRIMARY KEY (`id`),
  KEY `idx_aid` (`audit_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

SET FOREIGN_KEY_CHECKS = 1;
