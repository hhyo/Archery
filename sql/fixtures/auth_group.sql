-- sql_instance_tag
INSERT INTO sql_instance_tag (id, tag_code, tag_name, active, create_time)
VALUES (1, 'can_write', '支持上线', 1, now()),(2, 'can_read', '支持查询', 1, now());

-- auth_group
INSERT INTO auth_group (id, name)
VALUES (1, 'Default'),(2, 'RD'),(3, 'DBA'),(4, 'PM'),(5, 'QA');

SET FOREIGN_KEY_CHECKS=0;
-- Default
insert into auth_group_permissions (group_id, permission_id)
select 1,id
from auth_permission
where codename in ('menu_sqlworkflow', 'menu_query', 'menu_sqlquery', 'menu_queryapplylist', 'menu_document');

-- RD
insert into auth_group_permissions (group_id, permission_id)
select 2,id
from auth_permission
where codename in ('menu_dashboard','menu_sqlcheck','menu_sqlworkflow','menu_sqlanalyze','menu_query','menu_sqlquery','menu_queryapplylist','menu_sqloptimize','menu_sqladvisor','menu_slowquery','menu_data_dictionary','menu_tools','menu_archive','menu_document','sql_submit','sql_execute','sql_analyze','optimize_sqladvisor','optimize_soar','query_applypriv','query_submit','archive_apply');

-- DBA
insert into auth_group_permissions (group_id, permission_id)
select 3,id
from auth_permission
where codename in ('menu_dashboard','menu_sqlcheck','menu_sqlworkflow','menu_sqlanalyze','menu_query','menu_sqlquery','menu_queryapplylist','menu_sqloptimize','menu_sqladvisor','menu_slowquery','menu_instance','menu_instance_list','menu_dbdiagnostic','menu_database','menu_instance_account','menu_param','menu_data_dictionary','menu_tools','menu_archive','menu_binlog2sql','menu_my2sql','menu_schemasync','menu_system','menu_document','menu_openapi','sql_submit','sql_review','sql_execute_for_resource_group','sql_execute','sql_analyze','optimize_sqladvisor','optimize_sqltuning','optimize_soar','query_applypriv','query_mgtpriv','query_review','query_submit','query_all_instances','query_resource_group_instance','process_view','process_kill','tablespace_view','trx_view','trxandlocks_view','instance_account_manage','param_view','param_edit','data_dictionary_export','archive_apply','archive_review','archive_mgt');

-- PM
insert into auth_group_permissions (group_id, permission_id)
select 4,id
from auth_permission
where codename in ('menu_dashboard','menu_sqlcheck','menu_sqlworkflow','menu_sqlanalyze','menu_query','menu_sqlquery','menu_queryapplylist','menu_sqloptimize','menu_sqladvisor','menu_slowquery','menu_data_dictionary','menu_tools','menu_archive','menu_document','sql_submit','sql_review','sql_execute_for_resource_group','sql_execute','sql_analyze','optimize_sqladvisor','optimize_soar','query_applypriv','query_review','query_submit','archive_apply','archive_review');

-- QA
insert into auth_group_permissions (group_id, permission_id)
select 5,id
from auth_permission
where codename in ('menu_dashboard','menu_sqlcheck','menu_sqlworkflow','menu_query','menu_sqlquery','menu_queryapplylist','menu_data_dictionary','menu_document','sql_submit','sql_execute','query_applypriv','query_submit');

SET FOREIGN_KEY_CHECKS=1;
