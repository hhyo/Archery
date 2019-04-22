--disable foreign key check
SET FOREIGN_KEY_CHECKS = 0;
--workflow_log
alter table workflow_log
	modify id bigint(20) not null auto_increment comment '主键',
	modify audit_id bigint(20) not null comment '工单审批id',
	modify operation_type tinyint(4) not null comment '操作类型，0提交/待审核、1审核通过、2审核不通过、3审核取消/取消执行、4定时执行、5执行工单、6执行结束',
	modify operation_type_desc char(10) not null comment '操作类型描述',
	modify operation_info varchar(200) not null comment '操作信息',
	modify operator varchar(30) not null comment '操作人',
	modify operator_display varchar(50) not null comment '操作人中文名',
	modify operation_time datetime(6) not null comment '操作时间';
alter table workflow_log drop index workflow_log_audit_id_71ad84b7 ,add index idx_aid(`audit_id`);

--workflow_audit_setting
alter table workflow_audit_setting modify workflow_type tinyint(4) not null;
alter table workflow_audit_setting drop index workflow_audit_setting_group_id_workflow_type_5884053a_uniq,add unique key idx_uni_gid__workflow_type(`group_id`, `workflow_type`);

--workflow_audit_detail
alter table workflow_audit_detail modify audit_status tinyint(4) not null;

--workflow_audit
alter table workflow_audit modify workflow_type tinyint(4) not null, modify current_status tinyint(4) not null;
alter table workflow_audit drop index workflow_audit_workflow_id_workflow_type_14044a22_uniq, add unique key idx_uni_wfid__workflow_type(`workflow_id`, `workflow_type`);

--sql_workflow_content
alter table sql_workflow_content
	modify workflow_id int(11) not null comment 'SQL工单ID' after `id`,
	modify sql_content longtext not null comment '提交的SQL文本',
	modify review_content longtext not null comment '自动审核内容的JSON格式',
	modify execute_result longtext not null comment '执行结果的JSON格式';
alter table sql_workflow_content drop index workflow_id, add unique key idx_uni_workflow_id(`workflow_id`);
alter table sql_workflow_content drop FOREIGN KEY sql_workflow_content_workflow_id_3af79b62_fk_sql_workflow_id, add CONSTRAINT fk_wfid__sql_workflow_id FOREIGN KEY fk_wfid__sql_workflow_id (workflow_id) REFERENCES sql_workflow (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--sql_workflow
alter table sql_workflow
	modify instance_id int not null after `group_name`,
	modify db_name varchar(64) not null comment '数据库' after `instance_id`,
	modify engineer varchar(30) not null after `db_name`,
	modify engineer_display varchar(50) not null after `engineer`,
	modify audit_auth_groups varchar(255) not null after `engineer_display`,
	modify create_time datetime(6) not null after `audit_auth_groups`,
	modify finish_time datetime(6) after `create_time`,
	modify status varchar(50) not null after `finish_time`,
	modify is_backup tinyint(4) not null comment '是否备份' after `status`,
	modify is_manual tinyint(4) not null after `is_backup`,
	modify syntax_type tinyint(4) not null comment '工单类型 1、DDL，2、DML' after `is_manual`;
alter table sql_workflow drop index sql_workflow_instance_id_ad34809b_fk_sql_instance_id, add index idx_iid(`instance_id`);
alter table sql_workflow drop FOREIGN KEY sql_workflow_instance_id_ad34809b_fk_sql_instance_id, add CONSTRAINT fk_iid__sql_instance_id FOREIGN KEY fk_iid__sql_instance_id (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--sql_users_user_permissions
alter table sql_users_user_permissions drop index sql_users_user_permissions_users_id_permission_id_5fffb2bb_uniq ,add unique key idx_uni_uid__pid(`users_id`, `permission_id`);
alter table sql_users_user_permissions drop index sql_users_user_permi_permission_id_e990caab_fk_auth_perm, add index idx_pid(`permission_id`);
alter table sql_users_user_permissions drop FOREIGN KEY sql_users_user_permi_permission_id_e990caab_fk_auth_perm, add CONSTRAINT fk_pid__auth_permission_id FOREIGN KEY fk_pid__auth_permission_id (permission_id) REFERENCES auth_permission (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
alter table sql_users_user_permissions drop FOREIGN KEY sql_users_user_permissions_users_id_efad14b0_fk_sql_users_id, add CONSTRAINT fk_uid__sql_users_id FOREIGN KEY fk_uid__sql_users_id (users_id) REFERENCES sql_users (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--sql_users_groups
alter table sql_users_groups drop index sql_users_groups_users_id_group_id_4540dddc_uniq, add unique key idx_uni_uid__gid(`users_id`, `group_id`);
alter table sql_users_groups drop index sql_users_groups_group_id_d572a82e_fk_auth_group_id, add index idx_gid(group_id);
alter table sql_users_groups drop FOREIGN KEY sql_users_groups_group_id_d572a82e_fk_auth_group_id, add CONSTRAINT fk_gid__auth_group_id FOREIGN KEY fk_gid__auth_group_id (group_id) REFERENCES auth_group (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
alter table sql_users_groups drop FOREIGN KEY sql_users_groups_users_id_d674bacf_fk_sql_users_id, add CONSTRAINT fk_usersid__sql_users_id FOREIGN KEY fk_usersid__sql_users_id (users_id) REFERENCES sql_users (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--sql_users
alter table sql_users
	modify password varchar(128) not null comment '密码' after `id`,
	modify last_login datetime(6) not null comment '上次登录' after `password`,
	modify is_superuser tinyint(4) not null comment '超级用户状态:1是,0否' after `last_login`,
	modify username varchar(150) not null comment '用户名' after `is_superuser`,
	modify first_name varchar(30) not null comment '名,无值' after `username`,
	modify last_name varchar(150) not null comment '姓,无值' after `first_name`,
	modify email varchar(254) not null comment '电子邮箱地址' after `last_name`,
	modify is_staff tinyint(4) not null comment '职员状态(是否能管理django后台):1是,0否' after `email`,
	modify is_active tinyint(4) not null comment '有效(禁用用户标签):1是,0否' after `is_staff`,
	modify date_joined datetime(6) not null comment '加入日期(第一次登录时间)' after `is_active`,
	modify display varchar(50) not null comment '显示的中文名' after `date_joined`,
	modify failed_login_count int(11) not null comment '登陆失败次数' after `display`,
	modify last_login_failed_at datetime comment '上次失败登录时间' after `failed_login_count`;
alter table sql_users drop index username, add unique key idx_uni_username(username);

--sql_instance
alter table sql_instance drop index instance_name, add unique key idx_uni_instance_name(instance_name);

--resource_group_relations
alter table resource_group_relations modify object_type tinyint(4) not null;
alter table resource_group_relations drop index resource_group_relations_object_id_group_id_objec_48843c4f_uniq, add unique key idx_uni_oid__gid__object_type(`object_id`, `group_id`, `object_type`);

--resource_group
alter table resource_group modify is_deleted tinyint(4) not null;
alter table resource_group drop index group_name,add unique key idx_uni_group_name(`group_name`);

--query_privileges_apply
alter table query_privileges_apply
	modify priv_type tinyint(4) not null,
	modify instance_id int(11) not null after `user_display`;
alter table query_privileges_apply drop index query_privileges_apply_instance_id_bc03347f_fk_sql_instance_id, add index idx_iid(`instance_id`);
alter table query_privileges_apply drop FOREIGN KEY query_privileges_apply_instance_id_bc03347f_fk_sql_instance_id, add CONSTRAINT fk_insid__sql_instance_id FOREIGN KEY fk_insid__sql_instance_id (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--query_privileges
alter table query_privileges
	modify privilege_id int(11) not null auto_increment comment '权限id' first,
	modify user_name varchar(30) not null comment '用户' after `privilege_id`,
	modify user_display varchar(50) not null comment '下拉菜单筛选名' after `user_name`,
	modify instance_id int(11) not null comment '' after `user_display`,
	modify table_name varchar(64) not null comment '表' after `instance_id`,
	modify db_name varchar(64) not null comment '数据库' after `table_name`,
	modify valid_date date not null comment '有效时间' after `db_name`,
	modify limit_num int(11) not null comment '结果集' after `valid_date`,
	modify priv_type tinyint(4) not null comment '权限级别' after `limit_num`,
	modify is_deleted tinyint(4) not null comment '删除标记' after `priv_type`,
 	modify create_time datetime(6) not null comment '申请时间' after `is_deleted`,
 	modify sys_time datetime(6) not null comment '系统时间' after `create_time`;
alter table query_privileges drop index query_privileges_user_name_instance_id_db__ed2ad8a3_idx, add index idx_uname__iid__db_name__vdate(`user_name`, `instance_id`, `db_name`, `valid_date`);
alter table query_privileges drop index query_privileges_instance_id_047fcde2_fk_sql_instance_id, add index idx_iid(`instance_id`);
alter table query_privileges drop FOREIGN KEY query_privileges_instance_id_047fcde2_fk_sql_instance_id, add CONSTRAINT fk_instid__sql_instance_id FOREIGN KEY fk_instid__sql_instance_id (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--query_log
alter table query_log
	modify priv_check tinyint(4) not null comment '查询权限是否正常校验' after `user_display`,
	modify hit_rule tinyint(4) not null comment '查询是否命中脱敏规则' after `priv_check`,
	modify masking tinyint(4) not null comment '查询结果是否正常脱敏' after `hit_rule`;

--param_template
alter table param_template
	modify id int(11) not null auto_increment comment '主键' first,
	modify db_type varchar(10) not null comment '数据库类型，mysql、mssql、redis、pgsql' after `id`,
	modify variable_name varchar(64) not null comment '参数名' after `db_type`,
	modify default_value varchar(1024) not null comment '默认参数值' after `variable_name`,
	modify editable tinyint(4) not null comment '是否支持修改' after `default_value`,
 	modify valid_values varchar(1024) not null comment '有效参数值' after `editable`,
 	modify description varchar(1024) not null comment '参数描述' after `valid_values`,
 	modify create_time datetime(6) not null comment '创建时间' after `description`,
 	modify sys_time datetime(6) not null comment '创建时间' after `create_time`;
 alter table param_template drop index param_template_db_type_variable_name_139c76a6_uniq, add unique key idx_uni_db_type__variable_name(`db_type`, `variable_name`);

--param_history
alter table param_history
	modify id int(11) not null auto_increment comment '主键' first,
	modify instance_id int(11) not null comment '实例ID' after `id`,
	modify variable_name varchar(64) not null comment '参数名' after `instance_id`,
	modify old_var varchar(1024) not null comment '修改前参数值' after `variable_name`,
	modify new_var varchar(1024) not null comment '修改后参数值' after `old_var`,
	modify set_sql varchar(1024) not null comment '在线变更配置执行的SQL语句' after `new_var`,
 	modify user_name varchar(30) not null comment '修改人' after `set_sql`,
 	modify user_display varchar(50) not null comment '修改人中文名' after `user_name`,
 	modify update_time datetime(6) not null comment '修改时间' after `user_display`;
 alter table param_history drop index param_history_instance_id_601e8d3f_fk_sql_instance_id, add index idx_iid(instance_id);
 alter table param_history drop FOREIGN KEY param_history_instance_id_601e8d3f_fk_sql_instance_id, add CONSTRAINT fk_instanceid__sql_instance_id FOREIGN KEY fk_instanceid__sql_instance_id (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--django_session
alter table django_session drop index django_session_expire_date_a5c62663, add index idx_expire_date(expire_date);

--django_q_task
alter table django_q_task
	modify success tinyint(4) not null;

--django_content_type
alter table django_content_type drop index django_content_type_app_label_model_76bd3d3b_uniq, add unique key idx_uni_app_label__model(`app_label`, `model`);

--django_admin_log
alter table django_admin_log drop index django_admin_log_content_type_id_c4bce8eb_fk_django_co, add index idx_ctid(content_type_id);
alter table django_admin_log drop index django_admin_log_user_id_c564eba6_fk_sql_users_id, add index idx_uid(user_id);
alter table django_admin_log drop FOREIGN KEY django_admin_log_content_type_id_c4bce8eb_fk_django_co, add CONSTRAINT fk_ctid__django_content_type_id FOREIGN KEY fk_ctid__django_content_type_id (content_type_id) REFERENCES django_content_type (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
alter table django_admin_log drop FOREIGN KEY django_admin_log_user_id_c564eba6_fk_sql_users_id, add CONSTRAINT fk_users_id__sql_users_id FOREIGN KEY fk_users_id__sql_users_id (user_id) REFERENCES sql_users (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--data_masking_rules
alter table data_masking_rules drop index rule_type, add unique key idx_uni_rule_type(rule_type);

--data_masking_columns
alter table data_masking_columns
	modify active tinyint(4) not null comment '激活状态' after `rule_type`,
	modify instance_id int(11) not null after `active`;
alter table data_masking_columns drop index data_masking_columns_instance_id_470661d3_fk_sql_instance_id, add index idx_iid(`instance_id`);
alter table data_masking_columns drop FOREIGN KEY data_masking_columns_instance_id_470661d3_fk_sql_instance_id, add CONSTRAINT fk_instance_id__sql_instance_id FOREIGN KEY fk_instance_id__sql_instance_id (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--auth_permission
alter table auth_permission drop index auth_permission_content_type_id_codename_01ab375a_uniq, add unique key idx_uni_ctid(`content_type_id`, `codename`);
alter table auth_permission drop FOREIGN KEY auth_permission_content_type_id_2f476e4b_fk_django_co, add CONSTRAINT fk_ctypeid__django_content_type_id FOREIGN KEY fk_ctypeid__django_content_type_id (content_type_id) REFERENCES django_content_type (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--auth_group_permissions
alter table auth_group_permissions drop index auth_group_permissions_group_id_permission_id_0cd325b0_uniq, add unique key idx_uni_gid_pid(`group_id`, `permission_id`);
alter table auth_group_permissions drop index auth_group_permissio_permission_id_84c5c92e_fk_auth_perm, add index idx_pid(permission_id);
alter table auth_group_permissions drop FOREIGN KEY auth_group_permissio_permission_id_84c5c92e_fk_auth_perm, ADD CONSTRAINT fk_perid__auth_permission_id FOREIGN KEY fk_perid__auth_permission_id (permission_id) REFERENCES auth_permission (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
alter table auth_group_permissions drop FOREIGN KEY auth_group_permissions_group_id_b120cbf9_fk_auth_group_id, ADD CONSTRAINT fk_groupid__auth_group_id FOREIGN KEY fk_groupid__auth_group_id (group_id) REFERENCES auth_group (id) ON DELETE RESTRICT ON UPDATE RESTRICT;


--auth_group
alter table auth_group
	modify id int(11) not null auto_increment comment '主键' first,
	modify name varchar(80) not null comment '组' after `id`,
	comment '权限组';
alter table auth_group drop index name, add unique key idx_name(name);

--aliyun_rds_config
alter table aliyun_rds_config
	modify instance_id int(11) not null after `id`,
	modify is_enable tinyint(4) not null comment '是否启用' after `rds_dbinstanceid`;
alter table aliyun_rds_config add unique key idx_uni_iid(instance_id), drop index idx_iid;
alter table aliyun_rds_config drop FOREIGN KEY aliyun_rds_config_instance_id_4ad756cc_fk_sql_instance_id, add CONSTRAINT fk_instanid__sql_instance_id FOREIGN KEY fk_instanid__sql_instance_id (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--aliyun_access_key
alter table aliyun_access_key
	modify is_enable tinyint(4) not null comment '是否启用' after `secret`;

--mysql_slow_query_review_history
alter table mysql_slow_query_review_history drop index checksum, add unique key idx_uni_checksum__ts_min__ts_max(`checksum`, `ts_min`, `ts_max`);
