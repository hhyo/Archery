-- 此SQL语句仅完善注释信息，不做任何定义变更，请按需使用
ALTER TABLE
  aliyun_access_key COMMENT '阿里云认证信息',
    MODIFY  `ak` VARCHAR (50) NOT NULL COMMENT 'AccessKey',
    MODIFY  `secret` VARCHAR (100) NOT NULL COMMENT '口令',
    MODIFY  `is_enable` TINYINT (4) NOT NULL COMMENT '是否启用',
    MODIFY  `remark` VARCHAR (50) NOT NULL COMMENT '备注';


ALTER TABLE
  aliyun_rds_config COMMENT '阿里云rds配置',
    MODIFY  `instance_id` INT (11) NOT NULL COMMENT '实例ID',
    MODIFY  `rds_dbinstanceid` VARCHAR (100) NOT NULL COMMENT '对应阿里云RDS实例ID',
    MODIFY  `is_enable` TINYINT (4) NOT NULL COMMENT '是否启用';


ALTER TABLE
  auth_group COMMENT '权限组',
    MODIFY  `name` VARCHAR (80) NOT NULL COMMENT '组';


ALTER TABLE
  auth_group_permissions COMMENT '权限组已选中授权',
    MODIFY  `group_id` INT (11) NOT NULL COMMENT '组ID',
    MODIFY  `permission_id` INT (11) NOT NULL COMMENT '选中的权限';


ALTER TABLE
  auth_permission COMMENT '权限组可用权限-自定义业务权限',
    MODIFY  `name` VARCHAR (255) NOT NULL COMMENT '权限组可用权限名',
    MODIFY  `content_type_id` INT (11) NOT NULL COMMENT '权限类别ID',
    MODIFY  `codename` VARCHAR (100) NOT NULL COMMENT 'ORM名';


ALTER TABLE
  data_masking_columns COMMENT '脱敏字段配置',
    MODIFY  `column_id` INT (11) NOT NULL AUTO_INCREMENT COMMENT '字段id',
    MODIFY  `rule_type` INT (11) NOT NULL COMMENT '规则类型',
    MODIFY  `active` TINYINT (4) NOT NULL COMMENT '激活状态',
    MODIFY  `instance_id` INT (11) NOT NULL COMMENT '实例ID',
    MODIFY  `table_schema` VARCHAR (64) NOT NULL COMMENT '字段所在库名',
    MODIFY  `table_name` VARCHAR (64) NOT NULL COMMENT '字段所在表名',
    MODIFY  `column_name` VARCHAR (64) NOT NULL COMMENT '字段名',
    MODIFY  `column_comment` VARCHAR (1024) NOT NULL COMMENT '字段描述',
    MODIFY  `create_time` datetime (6) NOT NULL COMMENT '创建时间',
    MODIFY  `sys_time` datetime (6) NOT NULL COMMENT '系统时间';


ALTER TABLE
  data_masking_rules COMMENT '脱敏规则配置',
    MODIFY  `rule_type` INT (11) NOT NULL COMMENT '规则类型',
    MODIFY  `rule_regex` VARCHAR (255) NOT NULL COMMENT '规则脱敏所用的正则表达式,表达式必须分组,隐藏的组会使用****代替',
    MODIFY  `hide_group` INT (11) NOT NULL COMMENT '需要隐藏的组',
    MODIFY  `rule_desc` VARCHAR (100) NOT NULL COMMENT '规则描述',
    MODIFY  `sys_time` datetime (6) NOT NULL COMMENT '系统时间';


ALTER TABLE
  mysql_slow_query_review COMMENT '慢日志统计',
    MODIFY  `checksum` CHAR (32) NOT NULL COMMENT '校验和',
    MODIFY  `fingerprint` LONGTEXT NOT NULL COMMENT '指纹',
    MODIFY  `sample` LONGTEXT NOT NULL COMMENT '样例',
    MODIFY  `first_seen` datetime (6) DEFAULT NULL COMMENT '最早发现时间',
    MODIFY  `last_seen` datetime (6) DEFAULT NULL COMMENT '最后发现时间',
    MODIFY  `comments` LONGTEXT COMMENT '备注';


ALTER TABLE
  mysql_slow_query_review_history COMMENT '慢日志明细',
    MODIFY  `hostname_max` VARCHAR (64) NOT NULL COMMENT 'IP:端口',
    MODIFY  `client_max` VARCHAR (64) DEFAULT NULL COMMENT '客户端IP',
    MODIFY  `user_max` VARCHAR (64) NOT NULL COMMENT '用户名',
    MODIFY  `db_max` VARCHAR (64) DEFAULT NULL COMMENT '数据库',
    MODIFY  `checksum` CHAR (32) NOT NULL COMMENT '校验和',
    MODIFY  `sample` LONGTEXT NOT NULL COMMENT '样例',
    MODIFY  `ts_min` datetime (6) NOT NULL COMMENT '最早发现时间',
    MODIFY  `ts_max` datetime (6) NOT NULL COMMENT '最后发现时间',
    MODIFY  `ts_cnt` FLOAT DEFAULT NULL COMMENT '次数',
    MODIFY  `Query_time_sum` FLOAT DEFAULT NULL COMMENT '总查询时间',
    MODIFY  `Query_time_min` FLOAT DEFAULT NULL COMMENT '最小查询时间',
    MODIFY  `Query_time_max` FLOAT DEFAULT NULL COMMENT '最大查询时间',
    MODIFY  `Query_time_pct_95` FLOAT DEFAULT NULL COMMENT '95%查询的时间',
    MODIFY  `Query_time_stddev` FLOAT DEFAULT NULL COMMENT '平均查询时间',
    MODIFY  `Query_time_median` FLOAT DEFAULT NULL COMMENT '中位数查询时间',
    MODIFY  `Lock_time_sum` FLOAT DEFAULT NULL COMMENT '总锁定时间',
    MODIFY  `Lock_time_min` FLOAT DEFAULT NULL COMMENT '最小锁定时间',
    MODIFY  `Lock_time_max` FLOAT DEFAULT NULL COMMENT '最大锁定时间',
    MODIFY  `Lock_time_pct_95` FLOAT DEFAULT NULL COMMENT '95%锁定的时间',
    MODIFY  `Lock_time_stddev` FLOAT DEFAULT NULL COMMENT '平均锁定时间',
    MODIFY  `Lock_time_median` FLOAT DEFAULT NULL COMMENT '中位数锁定时间',
    MODIFY  `Rows_sent_sum` FLOAT DEFAULT NULL COMMENT '总返回行数',
    MODIFY  `Rows_sent_min` FLOAT DEFAULT NULL COMMENT '最小返回行数',
    MODIFY  `Rows_sent_max` FLOAT DEFAULT NULL COMMENT '最大返回行数',
    MODIFY  `Rows_sent_pct_95` FLOAT DEFAULT NULL COMMENT '95%返回行数',
    MODIFY  `Rows_sent_stddev` FLOAT DEFAULT NULL COMMENT '平均返回行数',
    MODIFY  `Rows_sent_median` FLOAT DEFAULT NULL COMMENT '中位数返回行数',
    MODIFY  `Rows_examined_sum` FLOAT DEFAULT NULL COMMENT '总检索行数',
    MODIFY  `Rows_examined_min` FLOAT DEFAULT NULL COMMENT '最小检索行数',
    MODIFY  `Rows_examined_max` FLOAT DEFAULT NULL COMMENT '最大检索行数',
    MODIFY  `Rows_examined_pct_95` FLOAT DEFAULT NULL COMMENT '95%检索行数',
    MODIFY  `Rows_examined_stddev` FLOAT DEFAULT NULL COMMENT '标准检索行数',
    MODIFY  `Rows_examined_median` FLOAT DEFAULT NULL COMMENT '中位数检索行数',
    MODIFY  `Rows_affected_sum` FLOAT DEFAULT NULL COMMENT '总影响行数',
    MODIFY  `Rows_affected_min` FLOAT DEFAULT NULL COMMENT '最小影响行数',
    MODIFY  `Rows_affected_max` FLOAT DEFAULT NULL COMMENT '最大影响行数',
    MODIFY  `Rows_affected_pct_95` FLOAT DEFAULT NULL COMMENT '95%影响行数',
    MODIFY  `Rows_affected_stddev` FLOAT DEFAULT NULL COMMENT '平均影响行数',
    MODIFY  `Rows_affected_median` FLOAT DEFAULT NULL COMMENT '中位数影响行数',
    MODIFY  `Rows_read_sum` FLOAT DEFAULT NULL COMMENT '总读取行数',
    MODIFY  `Rows_read_min` FLOAT DEFAULT NULL COMMENT '最小读取行数',
    MODIFY  `Rows_read_max` FLOAT DEFAULT NULL COMMENT '最大读取行数',
    MODIFY  `Rows_read_pct_95` FLOAT DEFAULT NULL COMMENT '95%读取行数',
    MODIFY  `Rows_read_stddev` FLOAT DEFAULT NULL COMMENT '平均读取行数',
    MODIFY  `Rows_read_median` FLOAT DEFAULT NULL COMMENT '中位数读取行数';


ALTER TABLE
  param_history COMMENT '实例参数修改历史-可在线修改的动态参数配置',
    MODIFY  `instance_id` INT (11) NOT NULL COMMENT '实例ID',
    MODIFY  `variable_name` VARCHAR (64) NOT NULL COMMENT '参数名',
    MODIFY  `old_var` VARCHAR (1024) NOT NULL COMMENT '修改前参数值',
    MODIFY  `new_var` VARCHAR (1024) NOT NULL COMMENT '修改后参数值',
    MODIFY  `set_sql` VARCHAR (1024) NOT NULL COMMENT '在线变更配置执行的SQL语句',
    MODIFY  `user_name` VARCHAR (30) NOT NULL COMMENT '修改人',
    MODIFY  `user_display` VARCHAR (50) NOT NULL COMMENT '修改人中文名',
    MODIFY  `update_time` datetime (6) NOT NULL COMMENT '修改时间';


ALTER TABLE
  param_template COMMENT '实例参数模板配置',
    MODIFY  `db_type` VARCHAR (10) NOT NULL COMMENT '数据库类型',
    MODIFY  `variable_name` VARCHAR (64) NOT NULL COMMENT '参数名',
    MODIFY  `default_value` VARCHAR (1024) NOT NULL COMMENT '默认参数值',
    MODIFY  `editable` TINYINT (4) NOT NULL COMMENT '是否支持修改',
    MODIFY  `valid_values` VARCHAR (1024) NOT NULL COMMENT '有效参数值,范围参数[1-65535],值参数[ON|OFF]',
    MODIFY  `description` VARCHAR (1024) NOT NULL COMMENT '参数描述',
    MODIFY  `create_time` datetime (6) NOT NULL COMMENT '创建时间',
    MODIFY  `sys_time` datetime (6) NOT NULL COMMENT '系统时间修改';


ALTER TABLE
  query_log COMMENT '查询日志-记录在线查询sql的日志',
    MODIFY  `instance_name` VARCHAR (50) NOT NULL COMMENT '实例名称',
    MODIFY  `db_name` VARCHAR (64) NOT NULL COMMENT '数据库名称',
    MODIFY  `sqllog` LONGTEXT NOT NULL COMMENT '执行的sql查询',
    MODIFY  `effect_row` BIGINT (20) NOT NULL COMMENT '返回行数',
    MODIFY  `cost_time` VARCHAR (10) NOT NULL COMMENT '执行耗时',
    MODIFY  `username` VARCHAR (30) NOT NULL COMMENT '操作人',
    MODIFY  `user_display` VARCHAR (50) NOT NULL COMMENT '操作人中文名',
    MODIFY  `priv_check` TINYINT (4) NOT NULL COMMENT '查询权限是否正常校验',
    MODIFY  `hit_rule` TINYINT (4) NOT NULL COMMENT '查询是否命中脱敏规则',
    MODIFY  `masking` TINYINT (4) NOT NULL COMMENT '查询结果是否正常脱敏',
    MODIFY  `create_time` datetime (6) NOT NULL COMMENT '操作时间',
    MODIFY  `sys_time` datetime (6) NOT NULL COMMENT '系统时间';


ALTER TABLE
  query_privileges COMMENT '查询权限记录-用户权限关系表',
    MODIFY  `privilege_id` INT (11) NOT NULL AUTO_INCREMENT COMMENT '权限id',
    MODIFY  `user_name` VARCHAR (30) NOT NULL COMMENT '用户名',
    MODIFY  `user_display` VARCHAR (50) NOT NULL COMMENT '申请人中文名',
    MODIFY  `instance_id` INT (11) NOT NULL COMMENT '实例ID',
    MODIFY  `table_name` VARCHAR (64) NOT NULL COMMENT '表',
    MODIFY  `db_name` VARCHAR (64) NOT NULL COMMENT '数据库',
    MODIFY  `valid_date` date NOT NULL COMMENT '有效时间',
    MODIFY  `limit_num` INT (11) NOT NULL COMMENT '行数限制',
    MODIFY  `priv_type` TINYINT (4) NOT NULL COMMENT '权限级别',
    MODIFY  `is_deleted` TINYINT (4) NOT NULL COMMENT '删除标记',
    MODIFY  `create_time` datetime (6) NOT NULL COMMENT '申请时间',
    MODIFY  `sys_time` datetime (6) NOT NULL COMMENT '系统时间';


ALTER TABLE
  query_privileges_apply COMMENT '查询权限申请记录表',
    MODIFY  `group_id` INT (11) NOT NULL COMMENT '组ID',
    MODIFY  `group_name` VARCHAR (100) NOT NULL COMMENT '组名称',
    MODIFY  `title` VARCHAR (50) NOT NULL COMMENT '申请标题',
    MODIFY  `user_name` VARCHAR (30) NOT NULL COMMENT '申请人',
    MODIFY  `user_display` VARCHAR (50) NOT NULL COMMENT '申请人中文名',
    MODIFY  `instance_id` INT (11) NOT NULL COMMENT '实例ID',
    MODIFY  `db_list` LONGTEXT NOT NULL COMMENT '数据库',
    MODIFY  `table_list` LONGTEXT NOT NULL COMMENT '表',
    MODIFY  `valid_date` date NOT NULL COMMENT '有效时间',
    MODIFY  `limit_num` INT (11) NOT NULL COMMENT '行数限制',
    MODIFY  `priv_type` TINYINT (4) NOT NULL COMMENT '权限类型',
    MODIFY  `status` INT (11) NOT NULL COMMENT '审核状态',
    MODIFY  `audit_auth_groups` VARCHAR (255) NOT NULL COMMENT '审批权限组列表',
    MODIFY  `create_time` datetime (6) NOT NULL COMMENT '创建时间',
    MODIFY  `sys_time` datetime (6) NOT NULL COMMENT '系统时间';


ALTER TABLE
  resource_group COMMENT '资源组管理-资源组',
    MODIFY  `group_id` INT (11) NOT NULL AUTO_INCREMENT COMMENT '组ID',
    MODIFY  `group_name` VARCHAR (100) NOT NULL COMMENT '组名称',
    MODIFY  `group_parent_id` BIGINT (20) NOT NULL COMMENT '父级ID',
    MODIFY  `group_sort` INT (11) NOT NULL COMMENT '排序',
    MODIFY  `group_level` INT (11) NOT NULL COMMENT '层级',
    MODIFY  `ding_webhook` VARCHAR (255) NOT NULL COMMENT '钉钉webhook地址',
    MODIFY  `is_deleted` TINYINT (4) NOT NULL COMMENT '是否删除',
    MODIFY  `create_time` datetime (6) NOT NULL COMMENT '创建时间',
    MODIFY  `sys_time` datetime (6) NOT NULL COMMENT '系统时间';


ALTER TABLE
  resource_group_relations COMMENT '资源组对象管理-资源组关系表（用户与组、实例与组等）',
    MODIFY  `object_type` TINYINT (4) NOT NULL COMMENT '关联对象类型',
    MODIFY  `object_id` INT (11) NOT NULL COMMENT '关联对象主键ID',
    MODIFY  `object_name` VARCHAR (100) NOT NULL COMMENT '关联对象描述,用户名、实例名',
    MODIFY  `group_id` INT (11) NOT NULL COMMENT '组ID',
    MODIFY  `group_name` VARCHAR (100) NOT NULL COMMENT '组名称',
    MODIFY  `create_time` datetime (6) NOT NULL COMMENT '创建时间',
    MODIFY  `sys_time` datetime (6) NOT NULL COMMENT '系统时间';


ALTER TABLE
  sql_config COMMENT '系统配置',
    MODIFY  `item` VARCHAR (50) NOT NULL COMMENT '配置项',
    MODIFY  `value` VARCHAR (200) NOT NULL COMMENT '配置项值',
    MODIFY  `description` VARCHAR (200) NOT NULL COMMENT '描述';


ALTER TABLE
  sql_instance COMMENT '实例配置-各个线上实例配置',
    MODIFY  `instance_name` VARCHAR (50) NOT NULL COMMENT '实例名',
    MODIFY  `type` VARCHAR (6) NOT NULL COMMENT '主从角色',
    MODIFY  `db_type` VARCHAR (10) NOT NULL COMMENT '数据库类型',
    MODIFY  `host` VARCHAR (200) NOT NULL COMMENT '主机',
    MODIFY  `port` INT (11) NOT NULL COMMENT '端口',
    MODIFY  `user` VARCHAR (100) NOT NULL COMMENT '用户',
    MODIFY  `password` VARCHAR (300) NOT NULL COMMENT '密码',
    MODIFY  `create_time` datetime (6) NOT NULL COMMENT '创建时间',
    MODIFY  `update_time` datetime (6) NOT NULL COMMENT '更新时间';


ALTER TABLE
  sql_users COMMENT '用户管理-用户信息',
    MODIFY  `password` VARCHAR (128) NOT NULL COMMENT '密码',
    MODIFY  `last_login` datetime (6) DEFAULT NULL COMMENT '上次登录',
    MODIFY  `is_superuser` TINYINT (4) NOT NULL COMMENT '超级用户状态:1是,0否',
    MODIFY  `username` VARCHAR (150) NOT NULL COMMENT '用户名',
    MODIFY  `first_name` VARCHAR (30) NOT NULL COMMENT '名,无值',
    MODIFY  `last_name` VARCHAR (150) NOT NULL COMMENT '姓,无值',
    MODIFY  `email` VARCHAR (254) NOT NULL COMMENT '电子邮箱地址',
    MODIFY  `is_staff` TINYINT (4) NOT NULL COMMENT '职员状态(是否能管理django后台):1是,0否',
    MODIFY  `is_active` TINYINT (4) NOT NULL COMMENT '有效(禁用用户标签):1是,0否',
    MODIFY  `date_joined` datetime (6) NOT NULL COMMENT '加入日期(第一次登录时间)',
    MODIFY  `display` VARCHAR (50) NOT NULL COMMENT '显示的中文名',
    MODIFY  `failed_login_count` INT (11) NOT NULL COMMENT '登陆失败次数',
    MODIFY  `last_login_failed_at` datetime DEFAULT NULL COMMENT '上次失败登录时间';


ALTER TABLE
  sql_workflow COMMENT 'SQL工单—存放各个SQL上线工单的基础内容',
    MODIFY  `workflow_name` VARCHAR (50) NOT NULL COMMENT '工单内容',
    MODIFY  `group_id` INT (11) NOT NULL COMMENT '组ID',
    MODIFY  `group_name` VARCHAR (100) NOT NULL COMMENT '组名称',
    MODIFY  `instance_id` INT (11) NOT NULL COMMENT '实例ID',
    MODIFY  `db_name` VARCHAR (64) NOT NULL COMMENT '数据库',
    MODIFY  `engineer` VARCHAR (30) NOT NULL COMMENT '发起人',
    MODIFY  `engineer_display` VARCHAR (50) NOT NULL COMMENT '发起人中文名',
    MODIFY  `audit_auth_groups` VARCHAR (255) NOT NULL COMMENT '审批权限组列表',
    MODIFY  `create_time` datetime (6) NOT NULL COMMENT '创建时间',
    MODIFY  `finish_time` datetime (6) DEFAULT NULL COMMENT '结束时间',
    MODIFY  `status` VARCHAR (50) NOT NULL COMMENT '工单状态',
    MODIFY  `is_backup` TINYINT (4) NOT NULL COMMENT '是否备份',
    MODIFY  `is_manual` TINYINT (4) NOT NULL COMMENT '是否原生执行',
    MODIFY  `syntax_type` TINYINT (4) NOT NULL COMMENT '工单类型 1、DDL,2、DML';


ALTER TABLE
  sql_workflow_content COMMENT 'SQL工单内容-存放各个SQL上线工单的SQL|审核|执行内容,可定期归档或清理历史数据,也可通过 alter table sql_workflow_content row_format=compressed 来进行压缩',
    MODIFY  `workflow_id` INT (11) NOT NULL COMMENT 'SQL工单ID',
    MODIFY  `sql_content` LONGTEXT NOT NULL COMMENT '提交的SQL文本',
    MODIFY  `review_content` LONGTEXT NOT NULL COMMENT '自动审核内容的JSON格式',
    MODIFY  `execute_result` LONGTEXT NOT NULL COMMENT '执行结果的JSON格式';


ALTER TABLE
  workflow_audit COMMENT '工作流审批列表-工作流审核状态表',
    MODIFY  `group_id` INT (11) NOT NULL COMMENT '组ID',
    MODIFY  `group_name` VARCHAR (100) NOT NULL COMMENT '组名称',
    MODIFY  `workflow_id` BIGINT (20) NOT NULL COMMENT '关联业务id',
    MODIFY  `workflow_type` TINYINT (4) NOT NULL COMMENT '申请类型',
    MODIFY  `workflow_title` VARCHAR (50) NOT NULL COMMENT '申请标题',
    MODIFY  `workflow_remark` VARCHAR (140) NOT NULL COMMENT '申请备注',
    MODIFY  `audit_auth_groups` VARCHAR (255) NOT NULL COMMENT '审批权限组列表',
    MODIFY  `current_audit` VARCHAR (20) NOT NULL COMMENT '当前审批权限组',
    MODIFY  `next_audit` VARCHAR (20) NOT NULL COMMENT '下级审批权限组',
    MODIFY  `current_status` TINYINT (4) NOT NULL COMMENT '审核状态',
    MODIFY  `create_user` VARCHAR (30) NOT NULL COMMENT '申请人',
    MODIFY  `create_user_display` VARCHAR (50) NOT NULL COMMENT '申请人中文名',
    MODIFY  `create_time` datetime (6) NOT NULL COMMENT '申请时间',
    MODIFY  `sys_time` datetime (6) NOT NULL COMMENT '系统时间';


ALTER TABLE
  workflow_audit_detail COMMENT '工作流审批明细-审批明细表',
    MODIFY  `audit_id` INT (11) NOT NULL COMMENT '审核主表id',
    MODIFY  `audit_user` VARCHAR (30) NOT NULL COMMENT '审核人',
    MODIFY  `audit_time` datetime (6) NOT NULL COMMENT '审核时间',
    MODIFY  `audit_status` TINYINT (4) NOT NULL COMMENT '审核状态',
    MODIFY  `remark` VARCHAR (140) NOT NULL COMMENT '审核备注',
    MODIFY  `sys_time` datetime (6) NOT NULL COMMENT '系统时间';


ALTER TABLE
  workflow_audit_setting COMMENT '审批流程配置-审批配置表',
    MODIFY  `group_id` INT (11) NOT NULL COMMENT '组ID',
    MODIFY  `group_name` VARCHAR (100) NOT NULL COMMENT '组名称',
    MODIFY  `workflow_type` TINYINT (4) NOT NULL COMMENT '审批类型',
    MODIFY  `audit_auth_groups` VARCHAR (255) NOT NULL COMMENT '审批权限组列表',
    MODIFY  `create_time` datetime (6) NOT NULL COMMENT '创建时间',
    MODIFY  `sys_time` datetime (6) NOT NULL COMMENT '系统时间';


ALTER TABLE
  workflow_log COMMENT '工作流日志',
    MODIFY  `audit_id` BIGINT (20) NOT NULL COMMENT '工单审批id',
    MODIFY  `operation_type` TINYINT (4) NOT NULL COMMENT '操作类型,0提交/待审核、1审核通过、2审核不通过、3审核取消/取消执行、4定时执行、5执行工单、6执行结束',
    MODIFY  `operation_type_desc` CHAR (10) NOT NULL COMMENT '操作类型描述',
    MODIFY  `operation_info` VARCHAR (200) NOT NULL COMMENT '操作信息',
    MODIFY  `operator` VARCHAR (30) NOT NULL COMMENT '操作人',
    MODIFY  `operator_display` VARCHAR (50) NOT NULL COMMENT '操作人中文名',
    MODIFY  `operation_time` datetime (6) NOT NULL COMMENT '操作时间';
