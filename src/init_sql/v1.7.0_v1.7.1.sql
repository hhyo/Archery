-- 添加钉钉user id
alter table sql_users
  add ding_user_id varchar(50) default null comment '钉钉user_id';

insert into django_q_schedule(func,schedule_type,repeats,task,name) values
  ('sql.tasks.ding.sync_ding_user_id','D',-2,'31144b2144724d7b81fe663e0211094b','同步钉钉用户ID');
