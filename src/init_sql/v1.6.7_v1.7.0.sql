--  删除Themis权限
set @perm_id=(select id from auth_permission where codename='menu_themis');
delete from auth_group_permissions where permission_id=@perm_id;
delete from sql_users_user_permissions where permission_id=@perm_id;
delete from auth_permission where codename='menu_themis';
