-- 增加登录审计日志
CREATE TABLE `audit_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `user_id` int(11) DEFAULT NULL COMMENT '用户id',
  `user_name` varchar(255) DEFAULT NULL COMMENT '用户名称',
  `ip` varchar(255) DEFAULT NULL COMMENT '登录ip',
  `action` varchar(255) DEFAULT NULL COMMENT '动作',
  `action_time` datetime(6) NOT NULL COMMENT '操作时间',
  PRIMARY KEY (`id`),
  KEY `idx_username` (`user_name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT='登录审计日志表';

-- ssh 隧道功能修改
ALTER TABLE `ssh_tunnel` ADD COLUMN pkey longtext NULL AFTER password DEFAULT CHARSET=utf8mb4 COMMENT='密钥信息';