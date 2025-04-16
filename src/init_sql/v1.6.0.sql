-- 增加oracle实例相关字段
ALTER TABLE sql_instance
  ADD `sid` varchar(50) DEFAULT NULL COMMENT 'Oracle sid' AFTER password,
  ADD `service_name` varchar(50) DEFAULT NULL COMMENT 'Oracle Service name' AFTER password;

-- 变更字段名
ALTER TABLE param_history CHANGE update_time create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '参数修改时间';

-- 变更字符集为utf8mb4，本身是utf8mb4的无需执行该语句
ALTER TABLE sql_workflow_content
  modify `sql_content` longtext CHARACTER SET utf8mb4 NOT NULL COMMENT '提交的SQL文本',
  modify `review_content` longtext CHARACTER SET utf8mb4 NOT NULL COMMENT '自动审核内容的JSON格式',
  modify `execute_result` longtext CHARACTER SET utf8mb4 NOT NULL COMMENT '执行结果的JSON格式';

ALTER TABLE query_log
  modify `sqllog` longtext CHARACTER SET utf8mb4 NOT NULL COMMENT '执行的sql查询';

-- 增加实例标签配置
CREATE TABLE `sql_instance_tag` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '标签id',
  `tag_code` varchar(20) NOT NULL COMMENT '标签代码',
  `tag_name` varchar(20) NOT NULL COMMENT '标签名称',
  `active` tinyint(1) NOT NULL COMMENT '激活状态',
  `create_time` datetime(6) NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_tag_code` (`tag_code`),
  UNIQUE KEY `uniq_tag_name` (`tag_name`)
) COMMENT '实例标签配置' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `sql_instance_tag_relations` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '关联id',
  `instance_id` int(11) NOT NULL COMMENT '关联实例ID',
  `instance_tag_id` int(11) NOT NULL COMMENT '关联标签ID',
  `active` tinyint(1) NOT NULL COMMENT '激活状态',
  `create_time` datetime(6) NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_instance_tag_id` (`instance_tag_id`),
  UNIQUE KEY `uniq_instance_id_instance_tag_id` (`instance_id`,`instance_tag_id`),
  CONSTRAINT `fk_itr_instance` FOREIGN KEY (`instance_id`) REFERENCES `sql_instance` (`id`),
  CONSTRAINT `fk_itr_instance_tag` FOREIGN KEY (`instance_tag_id`) REFERENCES `sql_instance_tag` (`id`)
) COMMENT '实例标签关系' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 初始化标签数据
INSERT INTO sql_instance_tag (id, tag_code, tag_name, active, create_time) VALUES (1, 'can_write', '支持上线', 1, '2019-05-03 00:00:00.000000');
INSERT INTO sql_instance_tag (id, tag_code, tag_name, active, create_time) VALUES (2, 'can_read', '支持查询', 1, '2019-05-03 00:00:00.000000');

-- 给原有主从数据增加标签
insert into sql_instance_tag_relations (instance_id, instance_tag_id, active, create_time)
select id,1,1,now() from sql_instance where type='master';
insert into sql_instance_tag_relations (instance_id, instance_tag_id, active, create_time)
select id,2,1,now() from sql_instance where type='slave';

set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('可查询所有实例', @content_type_id, 'query_all_instances');
