CREATE TABLE `ssh_tunnel` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `tunnel_name` varchar(50) NOT NULL,
  `host` varchar(200) NOT NULL,
  `port` int(11) NOT NULL,
  `user` varchar(200) DEFAULT NULL,
  `password` varchar(300) DEFAULT NULL,
  `pkey_address` varchar(300) DEFAULT NULL,
  `pkey_password` varchar(300) DEFAULT NULL,
  `create_time` datetime(6) NOT NULL,
  `update_time` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `tunnel_name` (`tunnel_name`)
) ;

CREATE TABLE `sql_instance` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `instance_name` varchar(50) NOT NULL,
  `type` varchar(6) NOT NULL,
  `db_type` varchar(20) NOT NULL,
  `host` varchar(200) NOT NULL,
  `port` int(11) NOT NULL,
  `user` varchar(200) NOT NULL,
  `password` varchar(300) NOT NULL,
  `db_name` varchar(64) NOT NULL,
  `charset` varchar(20) NOT NULL,
  `service_name` varchar(50) DEFAULT NULL,
  `sid` varchar(50) DEFAULT NULL,
  `create_time` datetime(6) NOT NULL,
  `update_time` datetime(6) NOT NULL,
  `tunnel_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `instance_name` (`instance_name`),
  KEY `sql_instance_tunnel_id_99377638_fk_ssh_tunnel_id` (`tunnel_id`),
  CONSTRAINT `sql_instance_tunnel_id_99377638_fk_ssh_tunnel_id` FOREIGN KEY (`tunnel_id`) REFERENCES `ssh_tunnel` (`id`)
) ;