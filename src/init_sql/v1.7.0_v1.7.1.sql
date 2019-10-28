-- 增加资源组粒度的查询权限，v1.7.0的model中遗漏，全新安装的需要补充
set @content_type_id=(select id from django_content_type where app_label='sql' and model='permission');
INSERT IGNORE INTO auth_permission (name, content_type_id, codename) VALUES ('可查询所在资源组内的所有实例', @content_type_id, 'query_resource_group_instance');

-- 记录企业微信userid
alter table sql_users add wx_user_id varchar(64) default null comment '企业微信UserID';

-- 删除阿里云AK配置表，转移到系统配置中，扩大系统配置项长度
drop table aliyun_access_key;
alter table sql_config modify `item` varchar(200) NOT NULL comment '配置项',
 modify `value` varchar(500) NOT NULL DEFAULT '' comment '配置项值';

-- 使用django-mirage-field加密实例信息，扩大字段长度
alter table sql_instance modify `user` varchar(200) DEFAULT NULL COMMENT '用户名';
