# -*- coding: UTF-8 -*-

from sql.models import Users, Instance, ResourceGroup,ResourceGroup2User,ResourceGroup2Instance


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
    # 先获取用户关联资源组列表
    group_list = user_groups(user)
    group_ids = [group.group_id for group in group_list]
    if user.has_perm('sql.query_all_instances'):
        instances = Instance.objects.all()
    else:
        # 获取资源组关联的实例列表
        instances = ResourceGroup.objects.filter(group_id__in=group_ids).instances.all()
    # 过滤type
    if type != 'all':
        instances = instances.get(type=type)

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
    # 查询制定权限组里的所有用户
    users = Users.objects.filter(groups__name__in=auth_group_names)
    # 查询制定资源组中包含有指定权限的用户
    users = ResourceGroup.objects.filter(group_id=group_id,users=users)
    return users
