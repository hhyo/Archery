-- 扩充数据库类型字段
alter table sql_instance modify db_type varchar(20) not null default '' comment '数据库类型';
