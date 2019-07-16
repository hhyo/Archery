-- 用于删除非自定义权限，如果不需要使用model权限管理，可以执行该脚本，仅保留自定义权限
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');

-- delete auth_group_permissions
delete a
from auth_group_permissions a
       join auth_permission b on a.permission_id = b.id
where (b.content_type_id <> @content_type_id or
       (b.content_type_id = @content_type_id and
        codename in ('add_permission', 'change_permission', 'delete_permission')));

-- delete sql_users_user_permissions
delete a
from sql_users_user_permissions a
       join auth_permission b on a.permission_id = b.id
where (b.content_type_id <> @content_type_id or
       (b.content_type_id = @content_type_id and
        codename in ('add_permission', 'change_permission', 'delete_permission')));

-- delete auth_permission
delete
from auth_permission
where (content_type_id <> @content_type_id or
       (content_type_id = @content_type_id and
        codename in ('add_permission', 'change_permission', 'delete_permission')));
