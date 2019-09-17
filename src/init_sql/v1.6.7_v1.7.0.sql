--  删除Themis权限
set @perm_id=(select id from auth_permission where codename='menu_themis');
delete from auth_group_permissions where permission_id=@perm_id;
delete from sql_users_user_permissions where permission_id=@perm_id;
delete from auth_permission where codename='menu_themis';

-- 添加钉钉user id
alter table sql_users
  add ding_user_id varchar(50) default null comment '钉钉user_id';

insert into django_q_schedule(func,schedule_type,repeats,task,name) values
  ('sql.tasks.ding.sync_ding_user_id','D',-2,'31144b2144724d7b81fe663e0211094b','同步钉钉用户ID');
