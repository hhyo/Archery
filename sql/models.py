# -*- coding: UTF-8 -*- 
from django.db import models
from django.contrib.auth.models import AbstractUser
from common.utils.aes_decryptor import Prpcrypt


# 用户信息扩展
class Users(AbstractUser):
    display = models.CharField('显示的中文名', max_length=50, blank=True, null=True)
    failed_login_count = models.IntegerField('失败计数', default=0)
    last_login_failed_at = models.DateTimeField('上次失败登录时间', blank=True, null=True)

    def __str__(self):
        if self.display:
            return self.display
        return self.username

    class Meta:
        managed = True
        db_table = 'sql_users'
        verbose_name = u'用户管理'
        verbose_name_plural = u'用户管理'


# 资源组
class ResourceGroup(models.Model):
    group_id = models.AutoField('组ID', primary_key=True)
    group_name = models.CharField('组名称', max_length=100, unique=True)
    group_parent_id = models.BigIntegerField('父级id', default=0)
    group_sort = models.IntegerField('排序', default=1)
    group_level = models.IntegerField('层级', default=1)
    ding_webhook = models.CharField('钉钉webhook地址', max_length=255, blank=True)
    is_deleted = models.IntegerField('是否删除', choices=((0, '否'), (1, '是')), default=0)
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.group_name

    class Meta:
        managed = True
        db_table = 'resource_group'
        verbose_name = u'资源组管理'
        verbose_name_plural = u'资源组管理'


# 资源组关系表（用户与组、实例与组等）
class ResourceGroupRelations(models.Model):
    object_type = models.IntegerField('关联对象类型', choices=((0, '用户'), (1, '实例')))
    object_id = models.IntegerField('关联对象主键ID', )
    object_name = models.CharField('关联对象描述，用户名、实例名', max_length=100)
    group_id = models.IntegerField('组ID')
    group_name = models.CharField('组名称', max_length=100)
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'resource_group_relations'
        unique_together = ('object_id', 'group_id', 'object_type')
        verbose_name = u'资源组对象管理'
        verbose_name_plural = u'资源组对象管理'


# 各个线上实例配置
class Instance(models.Model):
    instance_name = models.CharField('实例名称', max_length=50, unique=True)
    type = models.CharField('实例类型', max_length=6, choices=(('master', '主库'), ('slave', '从库')))
    db_type = models.CharField('数据库类型', max_length=10, choices=(('mysql', 'mysql'),('mssql','MsSQL')))
    host = models.CharField('实例连接', max_length=200)
    port = models.IntegerField('端口', default=3306)
    user = models.CharField('用户名', max_length=100)
    password = models.CharField('密码', max_length=300)
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    update_time = models.DateTimeField('更新时间', auto_now=True)

    def __str__(self):
        return self.instance_name

    class Meta:
        managed = True
        db_table = 'sql_instance'
        verbose_name = u'实例配置'
        verbose_name_plural = u'实例配置'

    def save(self, *args, **kwargs):
        pc = Prpcrypt()  # 初始化
        self.password = pc.encrypt(self.password)
        super(Instance, self).save(*args, **kwargs)


# 存放各个SQL上线工单的详细内容，可定期归档或清理历史数据，也可通过alter table workflow row_format=compressed; 来进行压缩
class SqlWorkflow(models.Model):
    workflow_name = models.CharField('工单内容', max_length=50)
    group_id = models.IntegerField('组ID')
    group_name = models.CharField('组名称', max_length=100)
    engineer = models.CharField('发起人', max_length=30)
    engineer_display = models.CharField('发起人中文名', max_length=50, default='')
    audit_auth_groups = models.CharField('审批权限组列表', max_length=255)
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    finish_time = models.DateTimeField('结束时间', null=True, blank=True)
    status = models.CharField(max_length=50, choices=(
        ('已正常结束', '已正常结束'), ('人工终止流程', '人工终止流程'), ('等待审核人审核', '等待审核人审核'), ('审核通过', '审核通过'),
        ('定时执行', '定时执行'), ('执行中', '执行中'), ('自动审核不通过', '自动审核不通过'), ('执行有异常', '执行有异常')))
    is_backup = models.CharField('是否备份', choices=(('否', '否'), ('是', '是')), max_length=20)
    review_content = models.TextField('自动审核内容的JSON格式')
    instance_name = models.CharField('实例名称', max_length=50)
    db_name = models.CharField('数据库', max_length=60)
    reviewok_time = models.DateTimeField('人工审核通过的时间', null=True, blank=True)
    sql_content = models.TextField('具体sql内容')
    execute_result = models.TextField('执行结果的JSON格式', blank=True)
    is_manual = models.IntegerField('是否跳过inception执行', choices=((0, '否'), (1, '是')), default=0)
    audit_remark = models.CharField('审核备注', max_length=200, null=True, blank=True)
    sql_syntax = models.IntegerField('SQL语法 1、DDL，2、DML', choices=((1, 'DDL'), (2, 'DML')))

    def __str__(self):
        return self.workflow_name

    class Meta:
        managed = True
        db_table = 'sql_workflow'
        verbose_name = u'SQL工单管理'
        verbose_name_plural = u'SQL工单管理'


# 工作流审核主表
class WorkflowAudit(models.Model):
    audit_id = models.AutoField(primary_key=True)
    group_id = models.IntegerField('组ID')
    group_name = models.CharField('组名称', max_length=100)
    workflow_id = models.BigIntegerField('关联业务id')
    workflow_type = models.IntegerField('申请类型',
                                        choices=((1, '查询权限申请'), (2, 'SQL上线申请')))
    workflow_title = models.CharField('申请标题', max_length=50)
    workflow_remark = models.CharField('申请备注', default='', max_length=140)
    audit_auth_groups = models.CharField('审批权限组列表', max_length=255)
    current_audit = models.CharField('当前审批权限组', max_length=20)
    next_audit = models.CharField('下级审批权限组', max_length=20)
    current_status = models.IntegerField('审核状态', choices=((0, '待审核'), (1, '审核通过'), (2, '审核不通过'), (3, '审核取消')))
    create_user = models.CharField('申请人', max_length=30)
    create_user_display = models.CharField('申请人中文名', max_length=50, default='')
    create_time = models.DateTimeField('申请时间', auto_now_add=True)
    sys_time = models.DateTimeField('系统时间', auto_now=True)

    def __int__(self):
        return self.audit_id

    class Meta:
        managed = True
        db_table = 'workflow_audit'
        unique_together = ('workflow_id', 'workflow_type')
        verbose_name = u'工作流审批列表'
        verbose_name_plural = u'工作流审批列表'


# 审批明细表
class WorkflowAuditDetail(models.Model):
    audit_detail_id = models.AutoField(primary_key=True)
    audit_id = models.IntegerField('审核主表id')
    audit_user = models.CharField('审核人', max_length=30)
    audit_time = models.DateTimeField('审核时间')
    audit_status = models.IntegerField('审核状态', choices=((0, '待审核'), (1, '审核通过'), (2, '审核不通过'), (3, '审核取消')), )
    remark = models.CharField('审核备注', default='', max_length=140)
    sys_time = models.DateTimeField('系统时间', auto_now=True)

    def __int__(self):
        return self.audit_detail_id

    class Meta:
        managed = True
        db_table = 'workflow_audit_detail'
        verbose_name = u'工作流审批明细'
        verbose_name_plural = u'工作流审批明细'


# 审批配置表
class WorkflowAuditSetting(models.Model):
    audit_setting_id = models.AutoField(primary_key=True)
    group_id = models.IntegerField('组ID')
    group_name = models.CharField('组名称', max_length=100)
    workflow_type = models.IntegerField('审批类型', choices=((1, '查询权限申请'), (2, 'SQL上线申请')))
    audit_auth_groups = models.CharField('审批权限组列表', max_length=255)
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    def __int__(self):
        return self.audit_setting_id

    class Meta:
        managed = True
        db_table = 'workflow_audit_setting'
        unique_together = ('group_id', 'workflow_type')
        verbose_name = u'审批流程配置'
        verbose_name_plural = u'审批流程配置'


# 工作流日志表
class WorkflowLog(models.Model):
    id = models.AutoField(primary_key=True)
    audit_id = models.IntegerField('工单审批id', db_index=True)
    operation_type = models.SmallIntegerField('操作类型，0提交/待审核、1审核通过、2审核不通过、3审核取消、4定时、5执行、6执行结束')
    operation_type_desc = models.CharField('操作类型描述', max_length=10)
    operation_info = models.CharField('操作信息', max_length=200)
    operator = models.CharField('操作人', max_length=30)
    operator_display = models.CharField('操作人中文名', max_length=50, default='')
    operation_time = models.DateTimeField(auto_now_add=True)

    def __int__(self):
        return self.audit_id

    class Meta:
        managed = True
        db_table = 'workflow_log'
        verbose_name = u'工作流日志'
        verbose_name_plural = u'工作流日志'


# 查询权限申请记录表
class QueryPrivilegesApply(models.Model):
    apply_id = models.AutoField(primary_key=True)
    group_id = models.IntegerField('组ID')
    group_name = models.CharField('组名称', max_length=100)
    title = models.CharField('申请标题', max_length=50)
    user_name = models.CharField('申请人', max_length=30)
    user_display = models.CharField('申请人中文名', max_length=50, default='')
    instance_name = models.CharField('实例名称', max_length=50)
    db_list = models.TextField('数据库')
    table_list = models.TextField('表')
    valid_date = models.DateField('有效时间')
    limit_num = models.IntegerField('行数限制', default=100)
    priv_type = models.IntegerField('权限类型', choices=((1, 'DATABASE'), (2, 'TABLE'),), default=0)
    status = models.IntegerField('审核状态', choices=((0, '待审核'), (1, '审核通过'), (2, '审核不通过'), (3, '审核取消')), )
    audit_auth_groups = models.CharField('审批权限组列表', max_length=255)
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    def __int__(self):
        return self.apply_id

    class Meta:
        managed = True
        db_table = 'query_privileges_apply'
        verbose_name = u'查询权限申请记录表'
        verbose_name_plural = u'查询权限申请记录表'


# 用户权限关系表
class QueryPrivileges(models.Model):
    privilege_id = models.AutoField(primary_key=True)
    user_name = models.CharField('用户名', max_length=30)
    user_display = models.CharField('申请人中文名', max_length=50, default='')
    instance_name = models.CharField('实例名称', max_length=50)
    db_name = models.CharField('数据库', max_length=200)
    table_name = models.CharField('表', max_length=200)
    valid_date = models.DateField('有效时间')
    limit_num = models.IntegerField('行数限制', default=100)
    priv_type = models.IntegerField('权限类型', choices=((1, 'DATABASE'), (2, 'TABLE'),), default=0)
    is_deleted = models.IntegerField('是否删除', default=0)
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    def __int__(self):
        return self.privilege_id

    class Meta:
        managed = True
        db_table = 'query_privileges'
        verbose_name = u'查询权限记录'
        verbose_name_plural = u'查询权限记录'


# 记录在线查询sql的日志
class QueryLog(models.Model):
    instance_name = models.CharField('实例名称', max_length=50)
    db_name = models.CharField('数据库名称', max_length=30)
    sqllog = models.TextField('执行的sql查询')
    effect_row = models.BigIntegerField('返回行数')
    cost_time = models.CharField('执行耗时', max_length=10, default='')
    username = models.CharField('操作人', max_length=30)
    user_display = models.CharField('操作人中文名', max_length=50, default='')
    priv_check = models.IntegerField('查询权限是否正常校验', choices=((1, ' 正常'), (2, '跳过'),), default=0)
    hit_rule = models.IntegerField('查询是否命中脱敏规则', choices=((0, '未知'), (1, '命中'), (2, '未命中'),), default=0)
    masking = models.IntegerField('查询结果是否正常脱敏', choices=((1, '是'), (2, '否'),), default=0)
    create_time = models.DateTimeField('操作时间', auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'query_log'
        verbose_name = u'查询日志'
        verbose_name_plural = u'查询日志'


# 脱敏字段配置
class DataMaskingColumns(models.Model):
    column_id = models.AutoField('字段id', primary_key=True)
    rule_type = models.IntegerField('规则类型',
                                    choices=((1, '手机号'), (2, '证件号码'), (3, '银行卡'), (4, '邮箱'), (5, '金额'), (6, '其他')))
    active = models.IntegerField('激活状态', choices=((0, '未激活'), (1, '激活')))
    instance_name = models.CharField('实例名称', max_length=50)
    table_schema = models.CharField('字段所在库名', max_length=64)
    table_name = models.CharField('字段所在表名', max_length=64)
    column_name = models.CharField('字段名', max_length=64)
    column_comment = models.CharField('字段描述', max_length=1024, default='', blank=True)
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'data_masking_columns'
        verbose_name = u'脱敏字段配置'
        verbose_name_plural = u'脱敏字段配置'


# 脱敏规则配置
class DataMaskingRules(models.Model):
    rule_type = models.IntegerField('规则类型',
                                    choices=((1, '手机号'), (2, '证件号码'), (3, '银行卡'), (4, '邮箱'), (5, '金额'), (6, '其他')),
                                    unique=True)
    rule_regex = models.CharField('规则脱敏所用的正则表达式，表达式必须分组，隐藏的组会使用****代替', max_length=255)
    hide_group = models.IntegerField('需要隐藏的组')
    rule_desc = models.CharField('规则描述', max_length=100, default='', blank=True)
    sys_time = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'data_masking_rules'
        verbose_name = u'脱敏规则配置'
        verbose_name_plural = u'脱敏规则配置'


# 配置信息表
class Config(models.Model):
    item = models.CharField('配置项', max_length=50, primary_key=True)
    value = models.CharField('配置项值', max_length=200)
    description = models.CharField('描述', max_length=200, default='', blank=True)

    class Meta:
        managed = True
        db_table = 'sql_config'
        verbose_name = u'系统配置'
        verbose_name_plural = u'系统配置'


# 记录阿里云的认证信息
class AliyunAccessKey(models.Model):
    ak = models.CharField(max_length=50)
    secret = models.CharField(max_length=100)
    is_enable = models.IntegerField(choices=((1, '启用'), (2, '禁用')))
    remark = models.CharField(max_length=50, default='', blank=True)

    class Meta:
        managed = True
        db_table = 'aliyun_access_key'
        verbose_name = u'阿里云认证信息'
        verbose_name_plural = u'阿里云认证信息'

    def save(self, *args, **kwargs):
        pc = Prpcrypt()  # 初始化
        self.ak = pc.encrypt(self.ak)
        self.secret = pc.encrypt(self.secret)
        super(AliyunAccessKey, self).save(*args, **kwargs)


# 阿里云rds配置信息
class AliyunRdsConfig(models.Model):
    instance_name = models.OneToOneField(Instance, on_delete=True, db_constraint=False, to_field='instance_name',
                                         db_column='instance_name', verbose_name='实例名称', unique=True)
    rds_dbinstanceid = models.CharField('对应阿里云RDS实例ID', max_length=100)
    is_enable = models.IntegerField('是否启用', choices=((1, '启用'), (2, '禁用')))

    def __int__(self):
        return self.rds_dbinstanceid

    class Meta:
        managed = True
        db_table = 'aliyun_rds_config'
        verbose_name = u'阿里云rds配置'
        verbose_name_plural = u'阿里云rds配置'


# 自定义权限定义
class Permission(models.Model):
    class Meta:
        managed = True
        permissions = (
            ('menu_dashboard', '菜单 Dashboard'),
            ('menu_sqlworkflow', '菜单 SQL上线'),
            ('menu_query', '菜单 SQL查询'),
            ('menu_sqlquery', '菜单 MySQL查询'),
            ('menu_queryapplylist', '菜单 查询权限申请'),
            ('menu_sqloptimize', '菜单 SQL优化'),
            ('menu_sqladvisor', '菜单 优化工具'),
            ('menu_slowquery', '菜单 慢查日志'),
            ('menu_dbdiagnostic', '菜单 会话管理'),
            ('menu_binlog2sql', '菜单 Binlog2SQL'),
            ('menu_schemasync', '菜单 SchemaSync'),
            ('menu_system', '菜单 系统管理'),
            ('menu_instance', '菜单 实例管理'),
            ('menu_document', '菜单 相关文档'),
            ('menu_themis', '菜单 数据库审核'),
            ('sql_submit', '提交SQL上线工单'),
            ('sql_review', '审核SQL上线工单'),
            ('sql_execute', '执行SQL上线工单'),
            ('optimize_sqladvisor', '执行SQLAdvisor'),
            ('optimize_sqltuning', '执行SQLTuning'),
            ('optimize_soar', '执行SOAR'),
            ('query_applypriv', '申请查询权限'),
            ('query_mgtpriv', '管理查询权限'),
            ('query_review', '审核查询权限'),
            ('query_submit', '提交SQL查询'),
            ('process_view', '查看会话'),
            ('process_kill', '终止会话'),
            ('tablespace_view', '查看表空间'),
            ('trxandlocks_view', '查看锁信息'),
        )


# SlowQuery
class SlowQuery(models.Model):
    checksum = models.CharField(max_length=32, primary_key=True)
    fingerprint = models.TextField()
    sample = models.TextField()
    first_seen = models.DateTimeField(blank=True, null=True)
    last_seen = models.DateTimeField(blank=True, null=True, db_index=True)
    reviewed_by = models.CharField(max_length=20, blank=True, null=True)
    reviewed_on = models.DateTimeField(blank=True, null=True)
    comments = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'mysql_slow_query_review'
        verbose_name = u'慢日志统计'
        verbose_name_plural = u'慢日志统计'


# SlowQueryHistory
class SlowQueryHistory(models.Model):
    hostname_max = models.CharField(max_length=64, null=False)
    client_max = models.CharField(max_length=64, null=True)
    user_max = models.CharField(max_length=64, null=False)
    db_max = models.CharField(max_length=64, null=True, default=None)
    bytes_max = models.CharField(max_length=64, null=True)
    checksum = models.ForeignKey(SlowQuery, db_constraint=False, to_field='checksum', db_column='checksum',
                                 on_delete=models.CASCADE)
    sample = models.TextField()
    ts_min = models.DateTimeField(db_index=True)
    ts_max = models.DateTimeField()
    ts_cnt = models.FloatField(blank=True, null=True)
    query_time_sum = models.FloatField(db_column='Query_time_sum', blank=True, null=True)
    query_time_min = models.FloatField(db_column='Query_time_min', blank=True, null=True)
    query_time_max = models.FloatField(db_column='Query_time_max', blank=True, null=True)
    query_time_pct_95 = models.FloatField(db_column='Query_time_pct_95', blank=True, null=True)
    query_time_stddev = models.FloatField(db_column='Query_time_stddev', blank=True, null=True)
    query_time_median = models.FloatField(db_column='Query_time_median', blank=True, null=True)
    lock_time_sum = models.FloatField(db_column='Lock_time_sum', blank=True, null=True)
    lock_time_min = models.FloatField(db_column='Lock_time_min', blank=True, null=True)
    lock_time_max = models.FloatField(db_column='Lock_time_max', blank=True, null=True)
    lock_time_pct_95 = models.FloatField(db_column='Lock_time_pct_95', blank=True, null=True)
    lock_time_stddev = models.FloatField(db_column='Lock_time_stddev', blank=True, null=True)
    lock_time_median = models.FloatField(db_column='Lock_time_median', blank=True, null=True)
    rows_sent_sum = models.FloatField(db_column='Rows_sent_sum', blank=True, null=True)
    rows_sent_min = models.FloatField(db_column='Rows_sent_min', blank=True, null=True)
    rows_sent_max = models.FloatField(db_column='Rows_sent_max', blank=True, null=True)
    rows_sent_pct_95 = models.FloatField(db_column='Rows_sent_pct_95', blank=True, null=True)
    rows_sent_stddev = models.FloatField(db_column='Rows_sent_stddev', blank=True, null=True)
    rows_sent_median = models.FloatField(db_column='Rows_sent_median', blank=True, null=True)
    rows_examined_sum = models.FloatField(db_column='Rows_examined_sum', blank=True, null=True)
    rows_examined_min = models.FloatField(db_column='Rows_examined_min', blank=True, null=True)
    rows_examined_max = models.FloatField(db_column='Rows_examined_max', blank=True, null=True)
    rows_examined_pct_95 = models.FloatField(db_column='Rows_examined_pct_95', blank=True, null=True)
    rows_examined_stddev = models.FloatField(db_column='Rows_examined_stddev', blank=True, null=True)
    rows_examined_median = models.FloatField(db_column='Rows_examined_median', blank=True, null=True)
    rows_affected_sum = models.FloatField(db_column='Rows_affected_sum', blank=True, null=True)
    rows_affected_min = models.FloatField(db_column='Rows_affected_min', blank=True, null=True)
    rows_affected_max = models.FloatField(db_column='Rows_affected_max', blank=True, null=True)
    rows_affected_pct_95 = models.FloatField(db_column='Rows_affected_pct_95', blank=True, null=True)
    rows_affected_stddev = models.FloatField(db_column='Rows_affected_stddev', blank=True, null=True)
    rows_affected_median = models.FloatField(db_column='Rows_affected_median', blank=True, null=True)
    rows_read_sum = models.FloatField(db_column='Rows_read_sum', blank=True, null=True)
    rows_read_min = models.FloatField(db_column='Rows_read_min', blank=True, null=True)
    rows_read_max = models.FloatField(db_column='Rows_read_max', blank=True, null=True)
    rows_read_pct_95 = models.FloatField(db_column='Rows_read_pct_95', blank=True, null=True)
    rows_read_stddev = models.FloatField(db_column='Rows_read_stddev', blank=True, null=True)
    rows_read_median = models.FloatField(db_column='Rows_read_median', blank=True, null=True)
    merge_passes_sum = models.FloatField(db_column='Merge_passes_sum', blank=True, null=True)
    merge_passes_min = models.FloatField(db_column='Merge_passes_min', blank=True, null=True)
    merge_passes_max = models.FloatField(db_column='Merge_passes_max', blank=True, null=True)
    merge_passes_pct_95 = models.FloatField(db_column='Merge_passes_pct_95', blank=True, null=True)
    merge_passes_stddev = models.FloatField(db_column='Merge_passes_stddev', blank=True, null=True)
    merge_passes_median = models.FloatField(db_column='Merge_passes_median', blank=True, null=True)
    innodb_io_r_ops_min = models.FloatField(db_column='InnoDB_IO_r_ops_min', blank=True, null=True)
    innodb_io_r_ops_max = models.FloatField(db_column='InnoDB_IO_r_ops_max', blank=True, null=True)
    innodb_io_r_ops_pct_95 = models.FloatField(db_column='InnoDB_IO_r_ops_pct_95', blank=True, null=True)
    innodb_io_r_ops_stddev = models.FloatField(db_column='InnoDB_IO_r_ops_stddev', blank=True, null=True)
    innodb_io_r_ops_median = models.FloatField(db_column='InnoDB_IO_r_ops_median', blank=True, null=True)
    innodb_io_r_bytes_min = models.FloatField(db_column='InnoDB_IO_r_bytes_min', blank=True, null=True)
    innodb_io_r_bytes_max = models.FloatField(db_column='InnoDB_IO_r_bytes_max', blank=True, null=True)
    innodb_io_r_bytes_pct_95 = models.FloatField(db_column='InnoDB_IO_r_bytes_pct_95', blank=True, null=True)
    innodb_io_r_bytes_stddev = models.FloatField(db_column='InnoDB_IO_r_bytes_stddev', blank=True, null=True)
    innodb_io_r_bytes_median = models.FloatField(db_column='InnoDB_IO_r_bytes_median', blank=True, null=True)
    innodb_io_r_wait_min = models.FloatField(db_column='InnoDB_IO_r_wait_min', blank=True, null=True)
    innodb_io_r_wait_max = models.FloatField(db_column='InnoDB_IO_r_wait_max', blank=True, null=True)
    innodb_io_r_wait_pct_95 = models.FloatField(db_column='InnoDB_IO_r_wait_pct_95', blank=True, null=True)
    innodb_io_r_wait_stddev = models.FloatField(db_column='InnoDB_IO_r_wait_stddev', blank=True, null=True)
    innodb_io_r_wait_median = models.FloatField(db_column='InnoDB_IO_r_wait_median', blank=True, null=True)
    innodb_rec_lock_wait_min = models.FloatField(db_column='InnoDB_rec_lock_wait_min', blank=True, null=True)
    innodb_rec_lock_wait_max = models.FloatField(db_column='InnoDB_rec_lock_wait_max', blank=True, null=True)
    innodb_rec_lock_wait_pct_95 = models.FloatField(db_column='InnoDB_rec_lock_wait_pct_95', blank=True, null=True)
    innodb_rec_lock_wait_stddev = models.FloatField(db_column='InnoDB_rec_lock_wait_stddev', blank=True, null=True)
    innodb_rec_lock_wait_median = models.FloatField(db_column='InnoDB_rec_lock_wait_median', blank=True, null=True)
    innodb_queue_wait_min = models.FloatField(db_column='InnoDB_queue_wait_min', blank=True, null=True)
    innodb_queue_wait_max = models.FloatField(db_column='InnoDB_queue_wait_max', blank=True, null=True)
    innodb_queue_wait_pct_95 = models.FloatField(db_column='InnoDB_queue_wait_pct_95', blank=True, null=True)
    innodb_queue_wait_stddev = models.FloatField(db_column='InnoDB_queue_wait_stddev', blank=True, null=True)
    innodb_queue_wait_median = models.FloatField(db_column='InnoDB_queue_wait_median', blank=True, null=True)
    innodb_pages_distinct_min = models.FloatField(db_column='InnoDB_pages_distinct_min', blank=True, null=True)
    innodb_pages_distinct_max = models.FloatField(db_column='InnoDB_pages_distinct_max', blank=True, null=True)
    innodb_pages_distinct_pct_95 = models.FloatField(db_column='InnoDB_pages_distinct_pct_95', blank=True, null=True)
    innodb_pages_distinct_stddev = models.FloatField(db_column='InnoDB_pages_distinct_stddev', blank=True, null=True)
    innodb_pages_distinct_median = models.FloatField(db_column='InnoDB_pages_distinct_median', blank=True, null=True)
    qc_hit_cnt = models.FloatField(db_column='QC_Hit_cnt', blank=True, null=True)
    qc_hit_sum = models.FloatField(db_column='QC_Hit_sum', blank=True, null=True)
    full_scan_cnt = models.FloatField(db_column='Full_scan_cnt', blank=True, null=True)
    full_scan_sum = models.FloatField(db_column='Full_scan_sum', blank=True, null=True)
    full_join_cnt = models.FloatField(db_column='Full_join_cnt', blank=True, null=True)
    full_join_sum = models.FloatField(db_column='Full_join_sum', blank=True, null=True)
    tmp_table_cnt = models.FloatField(db_column='Tmp_table_cnt', blank=True, null=True)
    tmp_table_sum = models.FloatField(db_column='Tmp_table_sum', blank=True, null=True)
    tmp_table_on_disk_cnt = models.FloatField(db_column='Tmp_table_on_disk_cnt', blank=True, null=True)
    tmp_table_on_disk_sum = models.FloatField(db_column='Tmp_table_on_disk_sum', blank=True, null=True)
    filesort_cnt = models.FloatField(db_column='Filesort_cnt', blank=True, null=True)
    filesort_sum = models.FloatField(db_column='Filesort_sum', blank=True, null=True)
    filesort_on_disk_cnt = models.FloatField(db_column='Filesort_on_disk_cnt', blank=True, null=True)
    filesort_on_disk_sum = models.FloatField(db_column='Filesort_on_disk_sum', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'mysql_slow_query_review_history'
        unique_together = ('checksum', 'ts_min', 'ts_max')
        index_together = ('hostname_max', 'ts_min')
        verbose_name = u'慢日志明细'
        verbose_name_plural = u'慢日志明细'
