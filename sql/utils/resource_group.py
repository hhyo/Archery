# -*- coding: UTF-8 -*-

from sql.models import Users, Instance, ResourceGroup, ResourceGroupRelations


# 获取用户关联资源组列表
def user_groups(user):
    if user.is_superuser == 1:
        group_list = [group for group in ResourceGroup.objects.filter(is_deleted=0)]
    else:
        group_ids = [group['group_id'] for group in
                     ResourceGroupRelations.objects.filter(object_id=user.id, object_type=0).values('group_id')]
        group_list = [group for group in ResourceGroup.objects.filter(group_id__in=group_ids, is_deleted=0)]
    return group_list


# 获取用户实例列表（通过资源组间接关联）
def user_instances(user, type):
    # 先获取用户关联资源组列表
    group_list = user_groups(user)
    group_ids = [group.group_id for group in group_list]
    if user.is_superuser == 1:
        instance_ids = [master['id'] for master in Instance.objects.all().values('id')]
    else:
        # 获取资源组关联的实例列表
        instance_ids = [group['object_id'] for group in
                        ResourceGroupRelations.objects.filter(group_id__in=group_ids, object_type=1).values('object_id')]
    # 获取实例信息
    if type == 'all':
        instances = Instance.objects.filter(pk__in=instance_ids)
    else:
        instances = Instance.objects.filter(pk__in=instance_ids, type=type)
    return instances


# 获取资源组内关联指定权限组的用户
def auth_group_users(auth_group_names, group_id):
    group_user_ids = [group['object_id'] for group in
                      ResourceGroupRelations.objects.filter(group_id=group_id, object_type=0).values('object_id')]
    users = Users.objects.filter(groups__name__in=auth_group_names, id__in=group_user_ids)
    return users
