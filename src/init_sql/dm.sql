-- archery.sql_backup_history definition

CREATE TABLE `sql_backup_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `table_name` varchar(128) NOT NULL COMMENT '表名',
  `sql_statement` longtext NOT NULL COMMENT '原始SQL语句',
  `backup_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL COMMENT '备份数据',
  `created_at` datetime(6) NOT NULL COMMENT '备份时间',
  `workflow_id` int(11) NOT NULL COMMENT '关联的工单ID',
  PRIMARY KEY (`id`),
  KEY `sql_backup_history_workflow_id_fk_sql_workflow_id` (`workflow_id`),
  CONSTRAINT `sql_backup_history_workflow_id_fk_sql_workflow_id` FOREIGN KEY (`workflow_id`) REFERENCES `sql_workflow` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COMMENT='SQL备份历史';
