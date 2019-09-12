-- 添加钉钉user id
alter table sql_users
  add ding_user_id varchar(50) default null comment '钉钉user_id';
