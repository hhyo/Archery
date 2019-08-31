--  删除Themis权限
delete from auth_group_permissions where permission_id=(select permission_id from auth_permission where codename='menu_themis');
delete from sql_users_user_permissions where permission_id=(select permission_id from auth_permission where codename='menu_themis');
delete from auth_permission where codename='menu_themis';
