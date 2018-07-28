-- 主从表合并相关修改
-- 表名修改
rename table sql_master_config to sql_instance;

-- 字段定义修改
alter table sql_instance
  change cluster_name instance_name varchar(50) NOT NULL ,
  change master_host host varchar(200) NOT NULL ,
  change master_port port varchar(200) NOT NULL,
  change master_user user varchar(200) NOT NULL,
  change master_password password varchar(200) NOT NULL,
  add type char(6) NOT NULL after instance_name,
  add db_type varchar(10) NOT NULL after type;

-- 更新信息
update sql_instance set db_type='mysql',type='master';

-- 从库数据添加到实例信息表（如果原主从实例存在相同实例名的请先修改，并且修改相关关联表的数据）
insert into sql_instance (instance_name, db_type, type, host, port, user, password, create_time, update_time)
  select
    cluster_name,
    'mysql',
    'slave',
    slave_host,
    slave_port,
    slave_user,
    slave_password,
    create_time,
    update_time
  from sql_slave_config;

-- 重新修改资源组实例关联信息，单独一个类型定义实例，不区分主从库
update sql_group_relations a
  join sql_instance b on a.object_name = b.instance_name
set a.object_id = b.id, a.object_type = 1
where a.object_type in (2, 3);

-- 变更关联字段信息
alter table sql_workflow change cluster_name instance_name varchar(50) NOT NULL ;
alter table query_privileges_apply change cluster_name instance_name varchar(50) NOT NULL ;
alter table query_privileges change cluster_name instance_name varchar(50) NOT NULL ;
alter table query_log change cluster_name instance_name varchar(50) NOT NULL ;
alter table data_masking_columns change cluster_name instance_name varchar(50) NOT NULL ;
alter table aliyun_rds_config change cluster_name instance_name varchar(50) NOT NULL ;





-- 权限管理相关修改
-- 删除角色字段
alter table sql_users drop role;

-- 变更字段信息
alter table sql_workflow
  change review_man audit_auth_groups varchar(255) NOT NULL;
alter table query_privileges_apply
  change audit_users audit_auth_groups varchar(255) NOT NULL;
alter table workflow_audit_setting
  change audit_users audit_auth_groups varchar(255) NOT NULL;
alter table workflow_audit
  change audit_users audit_auth_groups varchar(255) NOT NULL,
  change current_audit_user  current_audit varchar(20) NOT NULL,
  change next_audit_user next_audit varchar(20) NOT NULL;

-- 清空权限和权限组数据
set foreign_key_checks =0;
truncate table auth_group_permissions;
truncate table sql_users_user_permissions;
truncate table auth_permission;
truncate table auth_group;
truncate table sql_users_groups;
set foreign_key_checks =1;

-- 插入权限和默认权限组
INSERT INTO auth_group (id, name) VALUES (1, '默认组'); # 用户注册默认关联id=1的组,请勿删除
INSERT INTO django_content_type (id, app_label, model) VALUES (27, 'sql', 'permission');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (1, '菜单 Dashboard', 27, 'menu_dashboard');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (2, '菜单 SQL上线', 27, 'menu_sqlworkflow');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (3, '菜单 SQL查询', 27, 'menu_query');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (4, '菜单 MySQL查询', 27, 'menu_sqlquery');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (5, '菜单 查询权限申请', 27, 'menu_queryapplylist');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (6, '菜单 SQL优化', 27, 'menu_sqloptimize');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (7, '菜单 优化工具', 27, 'menu_sqladvisor');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (8, '菜单 慢查日志', 27, 'menu_slowquery');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (9, '菜单 会话管理', 27, 'menu_dbdiagnostic');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (10, '菜单 系统管理', 27, 'menu_system');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (11, '菜单 相关文档', 27, 'menu_document');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (12, '提交SQL上线工单', 27, 'sql_submit');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (13, '审核SQL上线工单', 27, 'sql_review');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (14, '执行SQL上线工单', 27, 'sql_execute');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (15, '执行SQLAdvisor', 27, 'optimize_sqladvisor');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (16, '执行SQLTuning', 27, 'optimize_sqltuning');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (17, '申请查询权限', 27, 'query_applypriv');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (18, '管理查询权限', 27, 'query_mgtpriv');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (19, '审核查询权限', 27, 'query_review');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (20, '提交SQL查询', 27, 'query_submit');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (21, '查看会话', 27, 'process_view');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (22, '终止会话', 27, 'process_kill');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (23, '查看表空间', 27, 'tablespace_view');
INSERT INTO auth_permission (id, name, content_type_id, codename) VALUES (24, '查看锁信息', 27, 'trxandlocks_view');

-- 给默认组赋予默认权限
INSERT INTO auth_group_permissions (id, group_id, permission_id) VALUES (1, 1, 1);
INSERT INTO auth_group_permissions (id, group_id, permission_id) VALUES (2, 1, 2);
INSERT INTO auth_group_permissions (id, group_id, permission_id) VALUES (3, 1, 3);
INSERT INTO auth_group_permissions (id, group_id, permission_id) VALUES (4, 1, 4);
INSERT INTO auth_group_permissions (id, group_id, permission_id) VALUES (5, 1, 5);
INSERT INTO auth_group_permissions (id, group_id, permission_id) VALUES (6, 1, 11);
INSERT INTO auth_group_permissions (id, group_id, permission_id) VALUES (7, 1, 12);
INSERT INTO auth_group_permissions (id, group_id, permission_id) VALUES (8, 1, 17);
INSERT INTO auth_group_permissions (id, group_id, permission_id) VALUES (9, 1, 20);

-- 全部用户都关联默认组，
insert into sql_users_groups(users_id, group_id)
select id,1
from sql_users;

