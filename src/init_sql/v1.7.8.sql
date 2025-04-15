-- 增加工单备注长度
alter table workflow_audit_detail modify remark varchar(1000) NOT NULL DEFAULT '' COMMENT '审核备注';
alter table workflow_log modify operation_info varchar(1000) NOT NULL DEFAULT '' COMMENT '操作信息';

-- 增加飞书信息
alter table sql_users add feishu_open_id varchar(64) not null default '' comment '飞书OpenID';
alter table resource_group add feishu_webhook varchar(255) not null default '' comment '飞书webhook地址';
