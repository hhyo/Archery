alter table sql_config add unique index uniq_item(item),drop primary key,
    add id bigint unsigned not null auto_increment primary key first ;
    