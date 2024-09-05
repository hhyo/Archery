 
ALTER TABLE sql_instance ADD is_ignore_certificate_error tinyint(1) DEFAULT 0  COMMENT '是否忽略证书错误。1：忽略。0：不忽略，需要验证';
ALTER TABLE sql_instance ADD show_db_name_regex varchar(1024) DEFAULT ''  COMMENT '显示的数据库列表正则';
ALTER TABLE sql_instance ADD denied_db_name_regex varchar(1024) DEFAULT ''  COMMENT '隐藏的数据库列表正则';
 