-- https://github.com/hhyo/Archery/pull/2108
alter table instance_account
    add db_name varchar(128) default '' not null comment '数据库名（mongodb）' after host;
