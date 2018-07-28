# -*- coding: UTF-8 -*-

from sql.models import Users, Instance, SlaveConfig, SqlGroup, GroupRelations


# 获取用户关联资源组列表
def user_groups(user):
    if user.is_superuser == 1:
        group_list = [group for group in SqlGroup.objects.filter(is_deleted=0)]
    else:
        group_ids = [group['group_id'] for group in
                     GroupRelations.objects.filter(object_id=user.id, object_type=0).values('group_id')]
        group_list = [group for group in SqlGroup.objects.filter(group_id__in=group_ids, is_deleted=0)]
    return group_list


# 获取用户关联主库列表（通过资源组间接关联）
def user_masters(user):
    # 先获取用户关联资源组列表
    group_list = user_groups(user)
    group_ids = [group.group_id for group in group_list]
    if user.is_superuser == 1:
        master_ids = [master['id'] for master in Instance.objects.all().values('id')]
    else:
        # 获取资源组关联的主库列表
        master_ids = [group['object_id'] for group in
                      GroupRelations.objects.filter(group_id__in=group_ids, object_type=2).values('object_id')]
    # 获取主库信息
    masters = Instance.objects.filter(pk__in=master_ids)
    return masters


# 获取用户关联从库列表（通过资源组间接关联）
def user_slaves(user):
    # 先获取用户管理资源组列表
    group_list = user_groups(user)
    group_ids = [group.group_id for group in group_list]
    if user.is_superuser == 1:
        slave_ids = [slave['id'] for slave in SlaveConfig.objects.all().values('id')]

    else:
        # 获取资源组关联的主库列表
        slave_ids = [group['object_id'] for group in
                     GroupRelations.objects.filter(group_id__in=group_ids, object_type=3).values('object_id')]
    # 获取主库信息
    slaves = SlaveConfig.objects.filter(pk__in=slave_ids)
    return slaves


# 获取资源组内关联指定权限组的用户
def auth_group_users(auth_group_names, group_id):
    group_user_ids = [group['object_id'] for group in
                      GroupRelations.objects.filter(group_id=group_id, object_type=0).values('object_id')]
    users = Users.objects.filter(groups__name__in=auth_group_names, id__in=group_user_ids)
    return users
