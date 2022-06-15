alter table sql_config add unique index uniq_item(item),drop primary key,
    add id bigint unsigned not null auto_increment primary key first ;

# 2fa配置表增加phone字段
alter table 2fa_config add column `phone` varchar(64) DEFAULT '' after `auth_type`;
