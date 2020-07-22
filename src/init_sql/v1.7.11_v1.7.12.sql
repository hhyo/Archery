-- 增加ssh_tunnel配置表
CREATE TABLE `ssh_tunnel` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `tunnel_name` varchar(50) NOT NULL,
  `host` varchar(200) NOT NULL,
  `port` int(11) NOT NULL,
  `user` varchar(200) DEFAULT NULL,
  `password` varchar(300) DEFAULT NULL,
  `pkey_path` varchar(300) DEFAULT NULL,
  `pkey_password` varchar(300) DEFAULT NULL,
  `create_time` datetime(6) NOT NULL,
  `update_time` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `tunnel_name` (`tunnel_name`)
) ;

alter table sql_instance add `tunnel_id` int(11) DEFAULT NULL,
add index `idx_ssh_tunnel_id` (`tunnel_id`),
add CONSTRAINT `sql_instance_tunnel_id_99377638_fk_ssh_tunnel_id` FOREIGN KEY (`tunnel_id`) REFERENCES `ssh_tunnel` (`id`);

-- 增加企业微信信息
alter table resource_group add qywx_webhook varchar(255) not null default '' comment '企业微信webhook地址';
