-- 修改工单状态
UPDATE sql_workflow SET status = 'workflow_finish' WHERE status='已正常结束';
UPDATE sql_workflow SET status = 'workflow_abort' WHERE status='人工终止流程';
UPDATE sql_workflow SET status = 'workflow_manreviewing' WHERE status='等待审核人审核';
UPDATE sql_workflow SET status = 'workflow_review_pass' WHERE status='审核通过';
UPDATE sql_workflow SET status = 'workflow_timingtask' WHERE status='定时执行';
UPDATE sql_workflow SET status = 'workflow_executing' WHERE status='执行中';
UPDATE sql_workflow SET status = 'workflow_autoreviewwrong' WHERE status='自动审核不通过';
UPDATE sql_workflow SET status = 'workflow_exception' WHERE status='执行有异常';

-- display修改为not null
alter table sql_users modify display varchar(50) not null default '' comment '显示的中文名';
