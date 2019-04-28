# -*- coding: UTF-8 -*-
from django.db import models

# Create your models here.
class UpdateLog(models.Model):
    instance_name = models.CharField('实例名称', max_length=50)
    db_name = models.CharField('数据库名称', max_length=30)
    sqllog = models.TextField('执行的sql更新')
    effect_row = models.TextField('执行信息')
    cost_time = models.CharField('执行耗时', max_length=10, default='')
    username = models.CharField('操作人', max_length=30)
    user_display = models.CharField('操作人中文名', max_length=50, default='')
    priv_check = models.IntegerField('更新权限是否正常校验', choices=((1, ' 正常'), (2, '跳过'),), default=0)
    hit_rule = models.IntegerField('更新是否命中脱敏规则', choices=((0, '未知'), (1, '命中'), (2, '未命中'),), default=0)
    masking = models.IntegerField('更新结果是否正常脱敏', choices=((1, '是'), (2, '否'),), default=0)
    create_time = models.DateTimeField('操作时间', auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'update_log'
        verbose_name = u'更新日志'
        verbose_name_plural = u'更新日志'

class Permission(models.Model):
    """
    自定义业务权限
    """

    class Meta:
        managed = True
        permissions = (
            ('menu_sqlupdate', '菜单 数据库更新'),
        )