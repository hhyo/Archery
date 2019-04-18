
---old表上执行的SQL

--workflow_log
alter table workflow_log
	modify operation_time datetime(6) not null comment '操作时间';

--workflow_audit_setting
alter table workflow_audit_setting modify workflow_type tinyint(4) not null;
alter table workflow_audit_setting drop index workflow_audit_setting_group_id_workflow_type_5884053a_uniq,add unique key idx_uni_gid__workflow_type(`group_id`, `workflow_type`);

--workflow_audit_detail
alter table workflow_audit_detail modify audit_status tinyint(4) not null;

--workflow_audit
alter table workflow_audit
	modify workflow_type tinyint(4) not null,
	modify current_status tinyint(4) not null;
alter table workflow_audit drop index workflow_audit_workflow_id_workflow_type_14044a22_uniq, add unique key idx_uni_wfid__workflow_type(`workflow_id`, `workflow_type`);

--sql_workflow_content
alter table sql_workflow_content drop index uniq_workflow_id, add unique key idx_uni_workflow_id(`workflow_id`);
alter table sql_workflow_content drop FOREIGN KEY fk_cont_workflow, add CONSTRAINT fk_wfid__sql_workflow_id FOREIGN KEY fk_wfid__sql_workflow_id (workflow_id) REFERENCES sql_workflow (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--sql_workflow
alter table sql_workflow
	modify is_manual tinyint(4) not null after `is_backup`;
alter table sql_workflow drop index fk_workflow_instance, add CONSTRAINT fk_iid__sql_instance_id FOREIGN KEY fk_iid__sql_instance_id (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--sql_users_user_permissions
alter table sql_users_user_permissions drop index sql_users_user_permissions_users_id_permission_id_5fffb2bb_uniq ,add unique key idx_uni_uid__pid(`users_id`, `permission_id`);
alter table sql_users_user_permissions drop index sql_users_user_permi_permission_id_e990caab_fk_auth_perm, add index idx_pid(`permission_id`);
alter table sql_users_user_permissions drop FOREIGN KEY sql_users_user_permi_permission_id_e990caab_fk_auth_perm, add CONSTRAINT fk_pid__auth_permission_id FOREIGN KEY fk_pid__auth_permission_id (permission_id) REFERENCES auth_permission (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
alter table sql_users_user_permissions drop FOREIGN KEY sql_users_user_permissions_users_id_efad14b0_fk_sql_users_id, add CONSTRAINT fk_uid__sql_users_id FOREIGN KEY fk_uid__sql_users_id (users_id) REFERENCES sql_users (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--sql_users_groups
alter table sql_users_groups drop index sql_users_groups_users_id_group_id_4540dddc_uniq, add unique key idx_uni_uid__gid(`users_id`, `group_id`);
alter table sql_users_groups drop index sql_users_groups_group_id_d572a82e_fk_auth_group_id, add index idx_gid(group_id);
alter table sql_users_groups drop FOREIGN KEY sql_users_groups_group_id_d572a82e_fk_auth_group_id, add CONSTRAINT fk_gid__auth_group_id FOREIGN KEY fk_gid__auth_group_id (group_id) REFERENCES auth_group (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
alter table sql_users_groups drop FOREIGN KEY sql_users_groups_users_id_d674bacf_fk_sql_users_id, add CONSTRAINT fk_usid__sql_users_id FOREIGN KEY fk_usid__sql_users_id (users_id) REFERENCES sql_users (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--sql_users
alter table sql_users
	modify is_superuser tinyint(4) not null comment '超级用户状态:1是,0否' after `last_login`,
	modify is_staff tinyint(4) not null comment '职员状态(是否能管理django后台):1是,0否' after `email`,
	modify is_active tinyint(4) not null comment '有效(禁用用户标签):1是,0否' after `is_staff`,
	modify last_login_failed_at datetime(6) comment '上次失败登录时间' after `failed_login_count`;
alter table sql_users drop index username, add unique key idx_uni_username(username);

--sql_instance
alter table sql_instance
	modify user varchar(100) not null comment '用户名' after `port`,
	modify password varchar(300) not null comment '密码' after `user`;
alter table sql_instance drop index instance_name, add unique key idx_uni_instance_name(instance_name);

--resource_group_relations
alter table resource_group_relations
	modify object_type tinyint(4) not null;
alter table resource_group_relations drop index sql_group_relations_object_id_group_id_object_type_398f04d1_uniq, add unique key idx_uni_oid__gid__object_type(`object_id`, `group_id`, `object_type`);

--resource_group
alter table resource_group
	modify is_deleted tinyint(4) not null;
alter table resource_group drop index group_name,add unique key idx_uni_group_name(group_name);

--query_privileges_apply
alter table query_privileges_apply
	modify instance_id int(11) not null after `user_display`,
	modify priv_type tinyint(4) not null,
	modify status tinyint(4) not null;
#alter table query_privileges_apply drop FOREIGN KEY fk_query_priv_apply_instance, add CONSTRAINT fk_inst_id__sql_instance_id FOREIGN KEY fk_inst_id__sql_instance_id (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--query_privileges
alter table query_privileges
	modify priv_type tinyint(4) not null comment '权限级别' after `limit_num`,
	modify is_deleted tinyint(4) not null comment '删除标记' after `priv_type`;
#alter table query_privileges drop FOREIGN KEY fk_query_priv_instance, add CONSTRAINT fk_instanid__sql_instance_id FOREIGN KEY fk_instanid__sql_instance_id (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--param_template
alter table param_template
 	modify create_time datetime(6) not null comment '创建时间' after `description`,
 	modify sys_time datetime(6) not null comment '创建时间' after `create_time`;
 alter table param_template drop index uniq_db_type_variable_name, add unique key idx_uni_db_type__variable_name(`db_type`, `variable_name`);

--param_history
alter table param_history
 	modify update_time datetime(6) not null comment '修改时间' after `user_display`;
alter table param_history drop index fk_param_instance, add index idx_iid(instance_id);
alter table param_history drop FOREIGN KEY fk_param_instance, add CONSTRAINT fk_iid__sql_instance_id FOREIGN KEY fk_iid__sql_instance_id (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--mysql_slow_query_review_history
alter table mysql_slow_query_review_history drop index checksum, add unique key idx_uni_checksum__ts_min__ts_max(`checksum`, `ts_min`, `ts_max`);

--django_session
alter table django_session drop index django_session_expire_date_a5c62663, add index idx_expire_date(expire_date);

--django_content_type
alter table django_content_type drop index django_content_type_app_label_model_76bd3d3b_uniq, add unique key idx_uni_app_label__model(`app_label`, `model`);

--django_admin_log
alter table django_admin_log drop index django_admin_log_content_type_id_c4bce8eb_fk_django_co, add index idx_ctid(content_type_id);
alter table django_admin_log drop index django_admin_log_user_id_c564eba6_fk_sql_users_id, add index idx_uid(user_id);
alter table django_admin_log drop FOREIGN KEY django_admin_log_content_type_id_c4bce8eb_fk_django_co, add CONSTRAINT fk_ctid__django_content_type_id FOREIGN KEY fk_ctid__django_content_type_id (content_type_id) REFERENCES django_content_type (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
alter table django_admin_log drop FOREIGN KEY django_admin_log_user_id_c564eba6_fk_sql_users_id, add CONSTRAINT fk_users_id__sql_users_id FOREIGN KEY fk_users_id__sql_users_id (user_id) REFERENCES sql_users (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--data_masking_rules
alter table data_masking_rules
	modify rule_type tinyint(4) not null;
alter table data_masking_rules drop index rule_type, add unique key idx_uni_rule_type(rule_type);

--data_masking_columns
#alter table data_masking_columns drop FOREIGN KEY fk_data_mask_instance, add CONSTRAINT fk_iid__sql_instance_id FOREIGN KEY fk_iid__sql_instance_id (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--auth_permission
alter table auth_permission drop index auth_permission_content_type_id_codename_01ab375a_uniq, add unique key idx_uni_ctid(`content_type_id`, `codename`);
#alter table auth_permission drop FOREIGN KEY auth_permission_content_type_id_2f476e4b_fk_django_co, add CONSTRAINT fk_ctid__django_content_type_id FOREIGN KEY fk_ctid__django_content_type_id (content_type_id) REFERENCES django_content_type (id) ON DELETE RESTRICT ON UPDATE RESTRICT;

--auth_group_permissions
alter table auth_group_permissions drop index auth_group_permissions_group_id_permission_id_0cd325b0_uniq, add unique key idx_uni_gid_pid(`group_id`, `permission_id`);
alter table auth_group_permissions drop index auth_group_permissio_permission_id_84c5c92e_fk_auth_perm, add index idx_pid(permission_id);
#alter table auth_group_permissions drop FOREIGN KEY auth_group_permissio_permission_id_84c5c92e_fk_auth_perm, ADD CONSTRAINT fk_pid__auth_permission_id FOREIGN KEY fk_pid__auth_permission_id (permission_id) REFERENCES auth_permission (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
alter table auth_group_permissions drop FOREIGN KEY auth_group_permissions_group_id_b120cbf9_fk_auth_group_id, ADD CONSTRAINT fk_pid__auth_group_id FOREIGN KEY fk_gid__auth_group_id (group_id) REFERENCES auth_group (id) ON DELETE RESTRICT ON UPDATE RESTRICT;


--auth_group
alter table auth_group drop index name, add unique key idx_name(name);

--aliyun_rds_config
alter table aliyun_rds_config drop index rds_dbinstanceid, add unique key idx_rds_dbinstanceid(rds_dbinstanceid);
#alter table aliyun_rds_config drop FOREIGN KEY fk_rds_instance, add CONSTRAINT fk_iid__sql_instance_id FOREIGN KEY fk_iid__sql_instance_id (instance_id) REFERENCES sql_instance (id) ON DELETE RESTRICT ON UPDATE RESTRICT;
