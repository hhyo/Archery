-- 修改阿里云配置信息表
alter table aliyun_rds_config add is_enable tinyint not null default 0 comment '是否启用';
