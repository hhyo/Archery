# -*- coding: UTF-8 -*-

from sql.models import Users, Instance, ResourceGroup


def user_groups(user):
    """
    获取用户关联资源组列表
    :param user:
    :return:
    """
    if user.is_superuser:
        group_list = [group for group in ResourceGroup.objects.filter(is_deleted=0)]
    else:
        group_list = [group for group in Users.objects.get(id=user.id).resourcegroup_set.filter(is_deleted=0)]
    return group_list


def user_instances(user, type='all', db_type='all', tags=None):
    """
    获取用户实例列表（通过资源组间接关联）
    :param user:
    :param type: 实例类型 all：全部，master主库，salve从库
    :param db_type: 数据库类型, mysql，mssql
    :param tags: 标签id列表, [1,2]
    :return:
    """
    # 拥有所有实例权限的用户
    if user.has_perm('sql.query_all_instances'):
        instances = Instance.objects.all()
    else:
        # 先获取用户关联的资源组
        resource_groups = ResourceGroup.objects.filter(users=user)
        # 再获取资源组关联的实例
        instances = Instance.objects.none()
        for resource_group in resource_groups:
            instances = instances | resource_group.instances.all()
        instances = instances.distinct()
    # 过滤type
    if type != 'all':
        instances = instances.filter(type=type)

    # 过滤db_type
    if db_type != 'all':
        if isinstance(db_type, str):
            db_type = [db_type]
        instances = instances.filter(db_type__in=db_type)

    # 过滤tag
    if tags:
        for tag in tags:
            instances = instances.filter(instancetagrelations__instance_tag=tag, instancetagrelations__active=True)

    return instances


def auth_group_users(auth_group_names, group_id):
    """
    获取资源组内关联指定权限组的用户
    :param auth_group_names: 权限组名称list
    :param group_id: 资源组ID
    :return:
    """
    # 获取资源组关联的用户
    users = ResourceGroup.objects.get(group_id=group_id).users.all()
    # 过滤在该权限组中的用户
    users = users.filter(groups__name__in=auth_group_names)
    return users
