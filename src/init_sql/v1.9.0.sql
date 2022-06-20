alter table sql_config add unique index uniq_item(item),drop primary key,
    add id bigint unsigned not null auto_increment primary key first ;

# 2fa配置表重构
CREATE TABLE `2fa_config_new` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(200) NOT NULL,
  `auth_type` varchar(128) NOT NULL,
  `phone` varchar(64) DEFAULT '',
  `secret_key` varchar(256) DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `2fa_config_user_id_auth_type_303171fc_uniq` (`user_id`,`auth_type`),
  KEY `2fa_config_user_id_a0d1d7c2` (`user_id`),
  CONSTRAINT `2fa_config_user_id_new_fk_sql_users_id` FOREIGN KEY (`user_id`) REFERENCES `sql_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
insert into `2fa_config_new`(id,username,auth_type,secret_key,user_id) select id,username,auth_type,secret_key,user_id from 2fa_config;
rename table `2fa_config` to `2fa_config_old`, `2fa_config_new` to `2fa_config`;
drop table `2fa_config_old`;
