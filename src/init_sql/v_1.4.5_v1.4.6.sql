-- 用户名和密码增加默认值
ALTER TABLE sql_instance
  MODIFY `user` VARCHAR(200) NOT NULL DEFAULT '' COMMENT '用户名',
  MODIFY `password` VARCHAR(200)  NOT NULL DEFAULT '' COMMENT '密码';

-- 用户权限表增加索引
ALTER TABLE query_privileges
  ADD INDEX  idx_user_name_instance_id_db_name_valid_date(user_name,instance_id,db_name,valid_date);
