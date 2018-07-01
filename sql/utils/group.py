# -*- coding: UTF-8 -*-

from sql.models import Group, GroupRelations
from sql.models import users, master_config, slave_config


# 获取用户关联组列表
def user_groups(user):
    if user.is_superuser == 1:
        group_list = [group for group in Group.objects.filter(is_deleted=0)]
    else:
        group_ids = [group['group_id'] for group in
                     GroupRelations.objects.filter(object_id=user.id, object_type=0).values('group_id')]
        group_list = [group for group in Group.objects.filter(group_id__in=group_ids, is_deleted=0)]
    return group_list


# 获取用户关联主库列表（通过组间接关联）
def user_masters(user):
    # 先获取用户管理组列表
    group_list = user_groups(user)
    group_ids = [group.group_id for group in group_list]
    # 获取组关联的主库列表
    master_ids = [group['object_id'] for group in
                  GroupRelations.objects.filter(group_id__in=group_ids, object_type=2).values('object_id')]
    # 获取主库信息
    masters = master_config.objects.filter(pk__in=master_ids)
    return masters


# 获取用户关联从库列表（通过组间接关联）
def user_slaves(user):
    # 先获取用户管理组列表
    group_list = user_groups(user)
    group_ids = [group.group_id for group in group_list]
    # 获取组关联的主库列表
    slave_ids = [group['object_id'] for group in
                 GroupRelations.objects.filter(group_id__in=group_ids, object_type=3).values('object_id')]
    # 获取主库信息
    slaves = slave_config.objects.filter(pk__in=slave_ids)
    return slaves


# 获取组内DBA角色的用户
def group_dbas(group_id):
    # 获取组关联的用户列表
    dba_ids = [group['object_id'] for group in
               GroupRelations.objects.filter(group_id=group_id, object_type=0).values('object_id')]
    # 获取用户信息
    dbas = users.objects.filter(pk__in=dba_ids)
    return dbas

