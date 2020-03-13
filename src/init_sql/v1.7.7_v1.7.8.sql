-- 增加工单备注长度
alter table workflow_audit_detail modify remark varchar(1000) NOT NULL DEFAULT '' COMMENT '审核备注';
alter table workflow_log modify operation_info varchar(1000) NOT NULL DEFAULT '' COMMENT '操作信息';
