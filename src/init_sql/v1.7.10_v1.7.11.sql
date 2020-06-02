-- 云服务认证信息配置
create table cloud_access_key(
  id int not null auto_increment primary key comment 'id',
  type varchar(20) not null default '' comment 'type',
  key_id varchar(200) not null default '' comment 'key_id',
  key_secret varchar(200) not null default '' comment 'key_secret',
  remark varchar(50) not null default '' comment 'remark'
) comment '云服务认证信息配置';

-- 阿里云RDS配置关联认证信息
set foreign_key_checks=0;
alter table aliyun_rds_config add ak_id int not null default 0 comment 'ak_id',
  add  CONSTRAINT `fk_aliyun_rds_ak_id` FOREIGN KEY (`ak_id`) REFERENCES `cloud_access_key` (`id`);
set foreign_key_checks=1;
