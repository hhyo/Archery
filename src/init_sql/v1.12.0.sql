-- 2024-9
ALTER TABLE sql_instance ADD verify_ssl tinyint(1) DEFAULT 1  COMMENT '是否验证服务端SSL证书。1：验证。0：不验证';
ALTER TABLE sql_instance ADD show_db_name_regex varchar(1024) DEFAULT ''  COMMENT '显示的数据库列表正则';
ALTER TABLE sql_instance ADD denied_db_name_regex varchar(1024) DEFAULT ''  COMMENT '隐藏的数据库列表正则';
 