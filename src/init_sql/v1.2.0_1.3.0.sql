-- 增加工单日志表
CREATE TABLE `workflow_log` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `audit_id` bigint(20) NOT NULL DEFAULT '0' COMMENT '工单审批id',
  `operation_type` tinyint(4) NOT NULL DEFAULT '0' COMMENT '操作类型，0提交/待审核、1审核通过、2审核不通过、3审核取消/取消执行、4定时执行、5执行工单、6执行结束',
  `operation_type_desc` char(10) NOT NULL DEFAULT '' COMMENT '操作类型描述',
  `operation_info` varchar(200) NOT NULL DEFAULT '' COMMENT '操作信息',
  `operator` varchar(30) NOT NULL DEFAULT '' COMMENT '操作人',
  `operator_display` varchar(50) NOT NULL DEFAULT '' COMMENT '操作人中文名',
  `operation_time` timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '操作时间',
  PRIMARY KEY (`id`),
  index idx_audit_id(audit_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 增加菜单权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 数据库审核', @content_type_id, 'menu_themis');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 实例管理', @content_type_id, 'menu_instance');
INSERT INTO auth_permission (name, content_type_id, codename) VALUES ('菜单 Binlog2SQL', @content_type_id, 'menu_binlog2sql');
