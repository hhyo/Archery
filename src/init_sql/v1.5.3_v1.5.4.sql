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
  KEY `idx_instance_id` (`instance_id`),
  KEY `idx_instance_tag_id` (`instance_tag_id`),
  CONSTRAINT `fk_itr_instance` FOREIGN KEY (`instance_id`) REFERENCES `sql_instance` (`id`),
  CONSTRAINT `fk_itr_instance_tag` FOREIGN KEY (`instance_tag_id`) REFERENCES `sql_instance_tag` (`id`)
) COMMENT '实例标签关系' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
