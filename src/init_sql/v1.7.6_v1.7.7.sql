--  修改多对多的中间表
alter table resource_group_user
  rename to sql_users_resource_group,
  drop create_time,
  change user_id users_id int(11) NOT NULL COMMENT '用户',
  change resource_group_id resourcegroup_id int(11) NOT NULL COMMENT '资源组';

alter table resource_group_instance
  rename to sql_instance_resource_group,
  drop create_time,
  change resource_group_id resourcegroup_id int(11) NOT NULL COMMENT '资源组';

alter table sql_instance_tag_relations
  rename to sql_instance_instance_tag,
  drop `active`,
  drop create_time,
  change instance_tag_id instancetag_id int(11) NOT NULL COMMENT '关联标签ID';

-- 实例配置表新增默认数据库字段
ALTER TABLE sql_instance ADD `db_name` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '数据库';
