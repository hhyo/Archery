-- 增加查询语句收藏/置顶功能
alter table query_log
  add favorite tinyint not null default 0 comment '是否收藏',
  add alias varchar(100) not null default '' comment '语句标识/别名';
