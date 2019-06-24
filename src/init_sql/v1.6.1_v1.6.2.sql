-- 资源组和用户关联表
CREATE TABLE `resource_group_user` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `resource_group_id` int(11) NOT NULL COMMENT '资源组',
  `user_id` int(11) NOT NULL COMMENT '用户',
  `create_time` datetime(6) NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  UNIQUE uniq_resource_group_id_instance_id(`resource_group_id`,`user_id`),
  CONSTRAINT `fk_resource_group_user_resource_group` FOREIGN KEY (`resource_group_id`) REFERENCES `resource_group` (`group_id`),
  CONSTRAINT `fk_resource_group_user` FOREIGN KEY (`user_id`) REFERENCES `sql_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 资源组和实例关联表
CREATE TABLE `resource_group_instance` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `resource_group_id` int(11) NOT NULL COMMENT '资源组',
  `instance_id` int(11) NOT NULL COMMENT '实例',
  `create_time` datetime(6) NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_instance_id` (`instance_id`),
  UNIQUE uniq_resource_group_id_instance_id(`resource_group_id`,`instance_id`),
  CONSTRAINT `fk_resource_group_instance_resource_group` FOREIGN KEY (`resource_group_id`) REFERENCES `resource_group` (`group_id`),
  CONSTRAINT `fk_resource_group_instance` FOREIGN KEY (`instance_id`) REFERENCES `sql_instance` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 数据清洗
set foreign_key_checks = 0;
-- 用户关系数据
insert into resource_group_user (resource_group_id, user_id, create_time)
select group_id,object_id,create_time from resource_group_relations where object_type=0;
-- 实例关系数据
insert into resource_group_instance (resource_group_id, instance_id, create_time)
select group_id,object_id,create_time from resource_group_relations where object_type=1;
set foreign_key_checks = 1;

-- 删除旧表
drop table resource_group_relations;

-- SQL上线工单增加可执行时间选择
ALTER TABLE sql_workflow
  ADD run_date_start datetime(6) DEFAULT NULL COMMENT '可执行起始时间',
  ADD run_date_end datetime(6) DEFAULT NULL COMMENT '可执行结束时间';

-- 实例配置增加默认字符集信息
ALTER TABLE sql_instance
  ADD `charset` varchar(20) DEFAULT NULL COMMENT '字符集' after `password`;
