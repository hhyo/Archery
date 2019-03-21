# -*- coding: UTF-8 -*-

from sql.models import Users, Instance, ResourceGroup, ResourceGroupRelations


def user_groups(user):
    """
    获取用户关联资源组列表
    :param user:
    :return:
    """
    if user.is_superuser:
        group_list = [group for group in ResourceGroup.objects.filter(is_deleted=0)]
    else:
        group_ids = [group['group_id'] for group in
                     ResourceGroupRelations.objects.filter(object_id=user.id, object_type=0).values('group_id')]
        group_list = [group for group in ResourceGroup.objects.filter(group_id__in=group_ids, is_deleted=0)]
    return group_list


def user_instances(user, type='all', db_type='all'):
    """
    获取用户实例列表（通过资源组间接关联）
    :param user:
    :param type: 实例类型 all：全部，master主库，salve从库
    :param db_type: 数据库类型, mysql，mssql
    :return:
    """
    # 先获取用户关联资源组列表
    group_list = user_groups(user)
    group_ids = [group.group_id for group in group_list]
    if user.is_superuser == 1:
        instance_ids = [master['id'] for master in Instance.objects.all().values('id')]
    else:
        # 获取资源组关联的实例列表
        instance_ids = [group['object_id'] for group in
                        ResourceGroupRelations.objects.filter(group_id__in=group_ids, object_type=1).values('object_id')]
    # 过滤type
    if type == 'all':
        instances = Instance.objects.filter(pk__in=instance_ids)
    else:
        instances = Instance.objects.filter(pk__in=instance_ids, type=type)

    # 过滤db_type
    if db_type != 'all':
        instances = instances.filter(db_type=db_type)

    return instances


def auth_group_users(auth_group_names, group_id):
    """
    获取资源组内关联指定权限组的用户
    :param auth_group_names: 权限组名称list
    :param group_id: 资源组ID
    :return:
    """
    group_user_ids = [group['object_id'] for group in
                      ResourceGroupRelations.objects.filter(group_id=group_id, object_type=0).values('object_id')]
    users = Users.objects.filter(groups__name__in=auth_group_names, id__in=group_user_ids)
    return users
