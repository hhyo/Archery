 
ALTER TABLE sql_instance ADD is_ignore_certificate_error tinyint(1) DEFAULT 0  COMMENT '是否忽略证书错误。1：忽略。0：不忽略，需要验证';
ALTER TABLE sql_instance ADD allow_db_name_list varchar(1024) DEFAULT ''  COMMENT '允许显示的数据库列表，多个以逗号隔开，支持*和~。';
