-- 新增登录失败信息
alter table sql_users
  add failed_login_count tinyint not null default 0 comment '失败计数',
  add last_login_failed_at timestamp comment '上次失败登录时间';

-- 修改资源表名
rename table sql_group to resource_group;
rename table sql_group_relations to resource_group_relations;

-- 使用django_q替换django_apscheduler
drop table django_apscheduler_djangojobexecution;
drop table django_apscheduler_djangojob;
