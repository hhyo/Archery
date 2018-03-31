# -*- coding: UTF-8 -*- 
from django.db import models
from django.contrib.auth.models import AbstractUser
from .aes_decryptor import Prpcrypt

# Create your models here.

#角色分两种：
#1.工程师：可以提交SQL上线单的工程师们，username字段为登录用户名，display字段为展示的中文名。
#2.审核人：可以审核并执行SQL上线单的管理者、高级工程师、系统管理员们。
class users(AbstractUser):
    display = models.CharField('显示的中文名', max_length=50)
    role = models.CharField('角色', max_length=20, choices=(('工程师','工程师'),('审核人','审核人')), default='工程师')
    is_ldapuser = models.BooleanField('ldap用戶', default=False)

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = u'用户配置'
        verbose_name_plural = u'用户配置'
users._meta.get_field('is_active').default = False # ldap default can't login, need admin to control

#各个线上主库地址。
class master_config(models.Model):
    cluster_name = models.CharField('集群名称', max_length=50)
    master_host = models.CharField('主库地址', max_length=200)
    master_port = models.IntegerField('主库端口', default=3306)
    master_user = models.CharField('登录主库的用户名', max_length=100)
    master_password = models.CharField('登录主库的密码', max_length=300)
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    update_time = models.DateTimeField('更新时间', auto_now=True)

    def __str__(self):
        return self.cluster_name
    class Meta:
        verbose_name = u'主库地址'
        verbose_name_plural = u'主库地址'

    def save(self, *args, **kwargs):
        pc = Prpcrypt() #初始化
        self.master_password = pc.encrypt(self.master_password)
        super(master_config, self).save(*args, **kwargs)


#存放各个SQL上线工单的详细内容，可定期归档或清理历史数据，也可通过alter table workflow row_format=compressed; 来进行压缩
class workflow(models.Model):
    workflow_name = models.CharField('工单内容', max_length=50)
    engineer = models.CharField('发起人', max_length=50)
    review_man = models.CharField('审核人', max_length=50)
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    finish_time = models.DateTimeField('结束时间', null=True, blank=True)
    status = models.CharField(max_length=50, choices=(('已正常结束','已正常结束'),('人工终止流程','人工终止流程'),('自动审核中','自动审核中'),('等待审核人审核','等待审核人审核'),('审核通过','审核通过'),('执行中','执行中'),('自动审核不通过','自动审核不通过'),('执行有异常','执行有异常')))
    #is_backup = models.IntegerField('是否备份，0为否，1为是', choices=((0,0),(1,1)))
    is_backup = models.CharField('是否备份', choices=(('否','否'),('是','是')), max_length=20)
    review_content = models.TextField('自动审核内容的JSON格式')
    cluster_name = models.CharField('集群名称', max_length=50)     #master_config表的cluster_name列的外键
    reviewok_time = models.DateTimeField('人工审核通过的时间', null=True, blank=True)
    sql_content = models.TextField('具体sql内容')
    execute_result = models.TextField('执行结果的JSON格式')
    is_manual = models.IntegerField('是否手工执行', choices=((0, '否'), (1, '是')),default=0)
    audit_remark = models.TextField('审核备注', null=True)

    def __str__(self):
        return self.workflow_name
    class Meta:
        verbose_name = u'工单管理'
        verbose_name_plural = u'工单管理'


# 各个线上从库地址
class slave_config(models.Model):
    cluster_id = models.IntegerField('对应集群id', unique=True)
    cluster_name = models.CharField('对应集群名称', unique=True, max_length=50)
    slave_host = models.CharField('从库地址', max_length=200)
    slave_port = models.IntegerField('从库端口', default=3306)
    slave_user = models.CharField('登录从库的用户名', max_length=100)
    slave_password = models.CharField('登录从库的密码', max_length=300)
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    update_time = models.DateTimeField('更新时间', auto_now=True)

    def __str__(self):
        return self.cluster_name

    class Meta:
        verbose_name = u'从库地址'
        verbose_name_plural = u'从库地址'

    def save(self, *args, **kwargs):
        pc = Prpcrypt()  # 初始化
        self.slave_password = pc.encrypt(self.slave_password)
        super(slave_config, self).save(*args, **kwargs)


# 工作流审核主表
class WorkflowAudit(models.Model):
    audit_id = models.AutoField(primary_key=True)
    workflow_id = models.BigIntegerField('关联业务id')
    workflow_type = models.IntegerField('申请类型',
                                        choices=((1, '查询权限申请'),))
    workflow_title = models.CharField('申请标题', max_length=50)
    workflow_remark = models.CharField('申请备注', default='', max_length=140)
    audit_users = models.CharField('审核人列表', max_length=255)
    current_audit_user = models.CharField('当前审核人', max_length=20)
    next_audit_user = models.CharField('下级审核人', max_length=20)
    current_status = models.IntegerField('审核状态', choices=((0, '待审核'), (1, '审核通过'), (2, '审核不通过'), (3, '审核取消')))
    create_user = models.CharField('申请人', max_length=20)
    create_time = models.DateTimeField('申请时间', auto_now_add=True)
    sys_time = models.DateTimeField('系统时间', auto_now=True)

    def __int__(self):
        return self.audit_id

    class Meta:
        db_table = 'workflow_audit'
        unique_together = ('workflow_id', 'workflow_type')
        verbose_name = u'工作流列表'
        verbose_name_plural = u'工作流列表'


# 审批明细表
class WorkflowAuditDetail(models.Model):
    audit_detail_id = models.AutoField(primary_key=True)
    audit_id = models.IntegerField('审核主表id')
    audit_user = models.CharField('审核人', max_length=20)
    audit_time = models.DateTimeField('审核时间')
    audit_status = models.IntegerField('审核状态', choices=((0, '待审核'), (1, '审核通过'), (2, '审核不通过'), (3, '审核取消')), )
    remark = models.CharField('审核备注', default='', max_length=140)
    sys_time = models.DateTimeField('系统时间', auto_now=True)

    def __int__(self):
        return self.audit_detail_id

    class Meta:
        db_table = 'workflow_audit_detail'
        verbose_name = u'审批明细表'
        verbose_name_plural = u'审批明细表'


# 审批配置表
class WorkflowAuditSetting(models.Model):
    audit_setting_id = models.AutoField(primary_key=True)
    workflow_type = models.IntegerField('申请类型,',choices=((1, '查询权限申请'),), unique=True)
    audit_users = models.CharField('审核人，单人审核格式为：user1，多级审核格式为：user1,user2', max_length=255)
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    def __int__(self):
        return self.audit_setting_id

    class Meta:
        db_table = 'workflow_audit_setting'
        verbose_name = u'工作流配置'
        verbose_name_plural = u'工作流配置'


# 查询权限申请记录表
class QueryPrivilegesApply(models.Model):
    apply_id = models.AutoField(primary_key=True)
    title = models.CharField('申请标题', max_length=50)
    user_name = models.CharField('申请人', max_length=30)
    cluster_id = models.IntegerField('集群id')
    cluster_name = models.CharField('集群名称', max_length=50)
    db_list = models.CharField('数据库', max_length=200)
    table_list = models.TextField('表')
    valid_date = models.CharField('有效时间', max_length=30)
    limit_num = models.IntegerField('行数限制', default=100)
    priv_type = models.IntegerField('权限类型', choices=((1, 'DATABASE'), (2, 'TABLE'),), default=0)
    status = models.IntegerField('审核状态', choices=((0, '待审核'), (1, '审核通过'), (2, '审核不通过'), (3, '审核取消')), )
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    def __int__(self):
        return self.apply_id

    class Meta:
        db_table = 'query_privileges_apply'
        verbose_name = u'查询权限申请记录表'
        verbose_name_plural = u'查询权限申请记录表'


# 用户权限关系表
class QueryPrivileges(models.Model):
    privilege_id = models.AutoField(primary_key=True)
    user_name = models.CharField('用户名', max_length=30)
    cluster_id = models.IntegerField('集群id')
    cluster_name = models.CharField('集群名称', max_length=50)
    db_name = models.CharField('数据库', max_length=200)
    table_name = models.CharField('表', max_length=200)
    valid_date = models.CharField('有效时间', max_length=30)
    limit_num = models.IntegerField('行数限制', default=100)
    priv_type = models.IntegerField('权限类型', choices=((1, 'DATABASE'), (2, 'TABLE'),), default=0)
    is_deleted = models.IntegerField('是否删除', default=0)
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    def __int__(self):
        return self.privilege_id

    class Meta:
        db_table = 'query_privileges'
        verbose_name = u'查询权限记录表'
        verbose_name_plural = u'查询权限记录表'


# 记录在线查询sql的日志
class QueryLog(models.Model):
    id = models.AutoField(primary_key=True)
    cluster_id = models.IntegerField('集群id')
    cluster_name = models.CharField('集群名称', max_length=50)
    db_name = models.CharField('数据库名称', max_length=30)
    sqllog = models.TextField('执行的sql查询')
    effect_row = models.BigIntegerField('返回行数')
    cost_time = models.CharField('执行耗时', max_length=10, default='')
    username = models.CharField('操作人', max_length=30)
    create_time = models.DateTimeField('操作时间', auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    def __int__(self):
        return self.id

    class Meta:
        db_table = 'query_log'
        verbose_name = u'sql查询日志'
        verbose_name_plural = u'sql查询日志'

# 脱敏字段配置
class DataMaskingColumns(models.Model):
    column_id = models.AutoField('字段id', primary_key=True)
    rule_type = models.IntegerField('规则类型',
                                    choices=((1, '手机号'), (2, '证件号码'), (3, '银行卡'), (4, '邮箱'), (5, '金额')))
    active = models.IntegerField('激活状态', choices=((0, '未激活'), (1, '激活')))
    cluster_id = models.IntegerField('字段所在集群id')
    cluster_name = models.CharField('字段所在集群名称', max_length=50)
    table_schema = models.CharField('字段所在库名', max_length=64)
    table_name = models.CharField('字段所在表名', max_length=64)
    column_name = models.CharField('字段名', max_length=64)
    column_comment = models.CharField('字段描述', max_length=1024)
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'data_masking_columns'
        verbose_name = u'脱敏字段配置'
        verbose_name_plural = u'脱敏字段配置'

# 脱敏规则配置
class DataMaskingRules(models.Model):
    rule_type = models.IntegerField('规则类型',
                                    choices=((1, '手机号'), (2, '证件号码'), (3, '银行卡'), (4, '邮箱'), (5, '金额')), unique=True)
    rule_regex = models.CharField('规则脱敏所用的正则表达式，表达式必须分组，隐藏的组会使用****代替', max_length=255)
    hide_group = models.IntegerField('需要隐藏的组')
    rule_desc = models.CharField('规则描述', max_length=100)
    sys_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'data_masking_rules'
        verbose_name = u'脱敏规则配置'
        verbose_name_plural = u'脱敏规则配置'

# 记录阿里云的认证信息
class AliyunAccessKey(models.Model):
    id = models.AutoField(primary_key=True)
    ak = models.CharField(max_length=50)
    secret = models.CharField(max_length=100)
    is_enable = models.IntegerField(choices=((1, '启用'), (2, '禁用')))
    remark = models.CharField(max_length=50, default='')

    def __int__(self):
        return self.id

    class Meta:
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
    cluster_id = models.IntegerField('对应集群id', unique=True)
    cluster_name = models.CharField('对应集群名称', unique=True, max_length=50)
    rds_dbinstanceid = models.CharField('阿里云RDS实例ID', max_length=100)

    def __int__(self):
        return self.rds_dbinstanceid

    class Meta:
        db_table = 'aliyun_rds_config'
        verbose_name = u'阿里云rds配置信息'
        verbose_name_plural = u'阿里云rds配置信息'

