-- MySQL dump 10.13  Distrib 5.7.22, for osx10.13 (x86_64)
--
-- Host: 127.0.0.1    Database: archer
-- ------------------------------------------------------
-- Server version	5.7.22

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `aliyun_access_key`
--

DROP TABLE IF EXISTS `aliyun_access_key`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `aliyun_access_key` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ak` varchar(50) NOT NULL,
  `secret` varchar(100) NOT NULL,
  `is_enable` int(11) NOT NULL,
  `remark` varchar(50) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `aliyun_access_key`
--

LOCK TABLES `aliyun_access_key` WRITE;
/*!40000 ALTER TABLE `aliyun_access_key` DISABLE KEYS */;
/*!40000 ALTER TABLE `aliyun_access_key` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `aliyun_rds_config`
--

DROP TABLE IF EXISTS `aliyun_rds_config`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `aliyun_rds_config` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `rds_dbinstanceid` varchar(100) NOT NULL,
  `cluster_name` varchar(50) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `rds_dbinstanceid` (`rds_dbinstanceid`),
  UNIQUE KEY `cluster_name` (`cluster_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `aliyun_rds_config`
--

LOCK TABLES `aliyun_rds_config` WRITE;
/*!40000 ALTER TABLE `aliyun_rds_config` DISABLE KEYS */;
/*!40000 ALTER TABLE `aliyun_rds_config` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group`
--

DROP TABLE IF EXISTS `auth_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `auth_group` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(80) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group`
--

LOCK TABLES `auth_group` WRITE;
/*!40000 ALTER TABLE `auth_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group_permissions`
--

DROP TABLE IF EXISTS `auth_group_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `auth_group_permissions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `group_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group_permissions`
--

LOCK TABLES `auth_group_permissions` WRITE;
/*!40000 ALTER TABLE `auth_group_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_permission`
--

DROP TABLE IF EXISTS `auth_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `auth_permission` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int(11) NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=79 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_permission`
--

LOCK TABLES `auth_permission` WRITE;
/*!40000 ALTER TABLE `auth_permission` DISABLE KEYS */;
INSERT INTO `auth_permission` VALUES (1,'Can add log entry',1,'add_logentry'),(2,'Can change log entry',1,'change_logentry'),(3,'Can delete log entry',1,'delete_logentry'),(4,'Can add permission',2,'add_permission'),(5,'Can change permission',2,'change_permission'),(6,'Can delete permission',2,'delete_permission'),(7,'Can add group',3,'add_group'),(8,'Can change group',3,'change_group'),(9,'Can delete group',3,'delete_group'),(10,'Can add content type',4,'add_contenttype'),(11,'Can change content type',4,'change_contenttype'),(12,'Can delete content type',4,'delete_contenttype'),(13,'Can add session',5,'add_session'),(14,'Can change session',5,'change_session'),(15,'Can delete session',5,'delete_session'),(16,'Can add django job',6,'add_djangojob'),(17,'Can change django job',6,'change_djangojob'),(18,'Can delete django job',6,'delete_djangojob'),(19,'Can add django job execution',7,'add_djangojobexecution'),(20,'Can change django job execution',7,'change_djangojobexecution'),(21,'Can delete django job execution',7,'delete_djangojobexecution'),(22,'Can add 系统配置',8,'add_config'),(23,'Can change 系统配置',8,'change_config'),(24,'Can delete 系统配置',8,'delete_config'),(25,'Can add 慢日志统计',9,'add_slowquery'),(26,'Can change 慢日志统计',9,'change_slowquery'),(27,'Can delete 慢日志统计',9,'delete_slowquery'),(28,'Can add 慢日志明细',10,'add_slowqueryhistory'),(29,'Can change 慢日志明细',10,'change_slowqueryhistory'),(30,'Can delete 慢日志明细',10,'delete_slowqueryhistory'),(31,'Can add 用户管理',11,'add_users'),(32,'Can change 用户管理',11,'change_users'),(33,'Can delete 用户管理',11,'delete_users'),(34,'Can add 阿里云认证信息',12,'add_aliyunaccesskey'),(35,'Can change 阿里云认证信息',12,'change_aliyunaccesskey'),(36,'Can delete 阿里云认证信息',12,'delete_aliyunaccesskey'),(37,'Can add 阿里云rds配置',13,'add_aliyunrdsconfig'),(38,'Can change 阿里云rds配置',13,'change_aliyunrdsconfig'),(39,'Can delete 阿里云rds配置',13,'delete_aliyunrdsconfig'),(40,'Can add 脱敏字段配置',14,'add_datamaskingcolumns'),(41,'Can change 脱敏字段配置',14,'change_datamaskingcolumns'),(42,'Can delete 脱敏字段配置',14,'delete_datamaskingcolumns'),(43,'Can add 脱敏规则配置',15,'add_datamaskingrules'),(44,'Can change 脱敏规则配置',15,'change_datamaskingrules'),(45,'Can delete 脱敏规则配置',15,'delete_datamaskingrules'),(46,'Can add 组配置',16,'add_group'),(47,'Can change 组配置',16,'change_group'),(48,'Can delete 组配置',16,'delete_group'),(49,'Can add 组关系配置',17,'add_grouprelations'),(50,'Can change 组关系配置',17,'change_grouprelations'),(51,'Can delete 组关系配置',17,'delete_grouprelations'),(52,'Can add 主库连接配置',18,'add_master_config'),(53,'Can change 主库连接配置',18,'change_master_config'),(54,'Can delete 主库连接配置',18,'delete_master_config'),(55,'Can add sql查询日志',19,'add_querylog'),(56,'Can change sql查询日志',19,'change_querylog'),(57,'Can delete sql查询日志',19,'delete_querylog'),(58,'Can add 查询权限记录表',20,'add_queryprivileges'),(59,'Can change 查询权限记录表',20,'change_queryprivileges'),(60,'Can delete 查询权限记录表',20,'delete_queryprivileges'),(61,'Can add 查询权限申请记录表',21,'add_queryprivilegesapply'),(62,'Can change 查询权限申请记录表',21,'change_queryprivilegesapply'),(63,'Can delete 查询权限申请记录表',21,'delete_queryprivilegesapply'),(64,'Can add 查询从库配置',22,'add_slave_config'),(65,'Can change 查询从库配置',22,'change_slave_config'),(66,'Can delete 查询从库配置',22,'delete_slave_config'),(67,'Can add SQL工单管理',23,'add_workflow'),(68,'Can change SQL工单管理',23,'change_workflow'),(69,'Can delete SQL工单管理',23,'delete_workflow'),(70,'Can add 工作流列表',24,'add_workflowaudit'),(71,'Can change 工作流列表',24,'change_workflowaudit'),(72,'Can delete 工作流列表',24,'delete_workflowaudit'),(73,'Can add 工作流审批明细表',25,'add_workflowauditdetail'),(74,'Can change 工作流审批明细表',25,'change_workflowauditdetail'),(75,'Can delete 工作流审批明细表',25,'delete_workflowauditdetail'),(76,'Can add 审批流程配置',26,'add_workflowauditsetting'),(77,'Can change 审批流程配置',26,'change_workflowauditsetting'),(78,'Can delete 审批流程配置',26,'delete_workflowauditsetting');
/*!40000 ALTER TABLE `auth_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `data_masking_columns`
--

DROP TABLE IF EXISTS `data_masking_columns`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `data_masking_columns` (
  `column_id` int(11) NOT NULL AUTO_INCREMENT,
  `rule_type` int(11) NOT NULL,
  `active` int(11) NOT NULL,
  `cluster_name` varchar(50) NOT NULL,
  `table_schema` varchar(64) NOT NULL,
  `table_name` varchar(64) NOT NULL,
  `column_name` varchar(64) NOT NULL,
  `column_comment` varchar(1024) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`column_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `data_masking_columns`
--

LOCK TABLES `data_masking_columns` WRITE;
/*!40000 ALTER TABLE `data_masking_columns` DISABLE KEYS */;
/*!40000 ALTER TABLE `data_masking_columns` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `data_masking_rules`
--

DROP TABLE IF EXISTS `data_masking_rules`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `data_masking_rules` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `rule_type` int(11) NOT NULL,
  `rule_regex` varchar(255) NOT NULL,
  `hide_group` int(11) NOT NULL,
  `rule_desc` varchar(100) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `rule_type` (`rule_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `data_masking_rules`
--

LOCK TABLES `data_masking_rules` WRITE;
/*!40000 ALTER TABLE `data_masking_rules` DISABLE KEYS */;
/*!40000 ALTER TABLE `data_masking_rules` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_admin_log`
--

DROP TABLE IF EXISTS `django_admin_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `django_admin_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint(5) unsigned NOT NULL,
  `change_message` longtext NOT NULL,
  `content_type_id` int(11) DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_sql_users_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_sql_users_id` FOREIGN KEY (`user_id`) REFERENCES `sql_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_admin_log`
--

LOCK TABLES `django_admin_log` WRITE;
/*!40000 ALTER TABLE `django_admin_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_admin_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_apscheduler_djangojob`
--

DROP TABLE IF EXISTS `django_apscheduler_djangojob`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `django_apscheduler_djangojob` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `next_run_time` datetime(6) DEFAULT NULL,
  `job_state` longblob NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `django_apscheduler_djangojob_next_run_time_2f022619` (`next_run_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_apscheduler_djangojob`
--

LOCK TABLES `django_apscheduler_djangojob` WRITE;
/*!40000 ALTER TABLE `django_apscheduler_djangojob` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_apscheduler_djangojob` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_apscheduler_djangojobexecution`
--

DROP TABLE IF EXISTS `django_apscheduler_djangojobexecution`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `django_apscheduler_djangojobexecution` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `status` varchar(50) NOT NULL,
  `run_time` datetime(6) NOT NULL,
  `duration` decimal(15,2) DEFAULT NULL,
  `started` decimal(15,2) DEFAULT NULL,
  `finished` decimal(15,2) DEFAULT NULL,
  `exception` varchar(1000) DEFAULT NULL,
  `traceback` longtext,
  `job_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_apscheduler_d_job_id_daf5090a_fk_django_ap` (`job_id`),
  KEY `django_apscheduler_djangojobexecution_run_time_16edd96b` (`run_time`),
  CONSTRAINT `django_apscheduler_d_job_id_daf5090a_fk_django_ap` FOREIGN KEY (`job_id`) REFERENCES `django_apscheduler_djangojob` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_apscheduler_djangojobexecution`
--

LOCK TABLES `django_apscheduler_djangojobexecution` WRITE;
/*!40000 ALTER TABLE `django_apscheduler_djangojobexecution` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_apscheduler_djangojobexecution` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_content_type`
--

DROP TABLE IF EXISTS `django_content_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `django_content_type` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_content_type`
--

LOCK TABLES `django_content_type` WRITE;
/*!40000 ALTER TABLE `django_content_type` DISABLE KEYS */;
INSERT INTO `django_content_type` VALUES (1,'admin','logentry'),(3,'auth','group'),(2,'auth','permission'),(4,'contenttypes','contenttype'),(6,'django_apscheduler','djangojob'),(7,'django_apscheduler','djangojobexecution'),(5,'sessions','session'),(12,'sql','aliyunaccesskey'),(13,'sql','aliyunrdsconfig'),(8,'sql','config'),(14,'sql','datamaskingcolumns'),(15,'sql','datamaskingrules'),(16,'sql','group'),(17,'sql','grouprelations'),(18,'sql','master_config'),(19,'sql','querylog'),(20,'sql','queryprivileges'),(21,'sql','queryprivilegesapply'),(22,'sql','slave_config'),(9,'sql','slowquery'),(10,'sql','slowqueryhistory'),(11,'sql','users'),(23,'sql','workflow'),(24,'sql','workflowaudit'),(25,'sql','workflowauditdetail'),(26,'sql','workflowauditsetting');
/*!40000 ALTER TABLE `django_content_type` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_migrations`
--

DROP TABLE IF EXISTS `django_migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `django_migrations` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_migrations`
--

LOCK TABLES `django_migrations` WRITE;
/*!40000 ALTER TABLE `django_migrations` DISABLE KEYS */;
INSERT INTO `django_migrations` VALUES (1,'contenttypes','0001_initial','2018-07-04 17:42:10.444289'),(2,'contenttypes','0002_remove_content_type_name','2018-07-04 17:42:10.554077'),(3,'auth','0001_initial','2018-07-04 17:42:11.101036'),(4,'auth','0002_alter_permission_name_max_length','2018-07-04 17:42:11.176087'),(5,'auth','0003_alter_user_email_max_length','2018-07-04 17:42:11.199448'),(6,'auth','0004_alter_user_username_opts','2018-07-04 17:42:11.223569'),(7,'auth','0005_alter_user_last_login_null','2018-07-04 17:42:11.252727'),(8,'auth','0006_require_contenttypes_0002','2018-07-04 17:42:11.271967'),(9,'auth','0007_alter_validators_add_error_messages','2018-07-04 17:42:11.297598'),(10,'auth','0008_alter_user_username_max_length','2018-07-04 17:42:11.326265'),(11,'auth','0009_alter_user_last_name_max_length','2018-07-04 17:42:11.354239'),(12,'sql','0001_initial','2018-07-04 17:42:15.921050'),(13,'admin','0001_initial','2018-07-04 17:42:16.322627'),(14,'admin','0002_logentry_remove_auto_add','2018-07-04 17:42:16.390647'),(15,'django_apscheduler','0001_initial','2018-07-04 17:42:16.948398'),(16,'django_apscheduler','0002_auto_20180412_0758','2018-07-04 17:42:17.057118'),(17,'sessions','0001_initial','2018-07-04 17:42:17.244175');
/*!40000 ALTER TABLE `django_migrations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_session`
--

DROP TABLE IF EXISTS `django_session`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_session`
--

LOCK TABLES `django_session` WRITE;
/*!40000 ALTER TABLE `django_session` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_session` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `query_log`
--

DROP TABLE IF EXISTS `query_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `query_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cluster_name` varchar(50) NOT NULL,
  `db_name` varchar(30) NOT NULL,
  `sqllog` longtext NOT NULL,
  `effect_row` bigint(20) NOT NULL,
  `cost_time` varchar(10) NOT NULL,
  `username` varchar(30) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `query_log`
--

LOCK TABLES `query_log` WRITE;
/*!40000 ALTER TABLE `query_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `query_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `query_privileges`
--

DROP TABLE IF EXISTS `query_privileges`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `query_privileges` (
  `privilege_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_name` varchar(30) NOT NULL,
  `cluster_name` varchar(50) NOT NULL,
  `db_name` varchar(200) NOT NULL,
  `table_name` varchar(200) NOT NULL,
  `valid_date` date NOT NULL,
  `limit_num` int(11) NOT NULL,
  `priv_type` int(11) NOT NULL,
  `is_deleted` int(11) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`privilege_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `query_privileges`
--

LOCK TABLES `query_privileges` WRITE;
/*!40000 ALTER TABLE `query_privileges` DISABLE KEYS */;
/*!40000 ALTER TABLE `query_privileges` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `query_privileges_apply`
--

DROP TABLE IF EXISTS `query_privileges_apply`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `query_privileges_apply` (
  `apply_id` int(11) NOT NULL AUTO_INCREMENT,
  `group_id` int(11) NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `title` varchar(50) NOT NULL,
  `user_name` varchar(30) NOT NULL,
  `cluster_name` varchar(50) NOT NULL,
  `db_list` longtext NOT NULL,
  `table_list` longtext NOT NULL,
  `valid_date` date NOT NULL,
  `limit_num` int(11) NOT NULL,
  `priv_type` int(11) NOT NULL,
  `status` int(11) NOT NULL,
  `audit_users` varchar(255) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`apply_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `query_privileges_apply`
--

LOCK TABLES `query_privileges_apply` WRITE;
/*!40000 ALTER TABLE `query_privileges_apply` DISABLE KEYS */;
/*!40000 ALTER TABLE `query_privileges_apply` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sql_config`
--

DROP TABLE IF EXISTS `sql_config`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sql_config` (
  `item` varchar(50) NOT NULL,
  `value` varchar(200) NOT NULL DEFAULT '',
  `type` tinyint(4) NOT NULL DEFAULT '0',
  `description` varchar(200) NOT NULL DEFAULT '',
  PRIMARY KEY (`item`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sql_config`
--

LOCK TABLES `sql_config` WRITE;
/*!40000 ALTER TABLE `sql_config` DISABLE KEYS */;
/*!40000 ALTER TABLE `sql_config` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sql_group`
--

DROP TABLE IF EXISTS `sql_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sql_group` (
  `group_id` int(11) NOT NULL AUTO_INCREMENT,
  `group_name` varchar(100) NOT NULL,
  `group_parent_id` bigint(20) NOT NULL,
  `group_sort` int(11) NOT NULL,
  `group_level` int(11) NOT NULL,
  `is_deleted` int(11) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`group_id`),
  UNIQUE KEY `group_name` (`group_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sql_group`
--

LOCK TABLES `sql_group` WRITE;
/*!40000 ALTER TABLE `sql_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `sql_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sql_group_relations`
--

DROP TABLE IF EXISTS `sql_group_relations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sql_group_relations` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `object_type` int(11) NOT NULL,
  `object_id` int(11) NOT NULL,
  `object_name` varchar(100) NOT NULL,
  `group_id` int(11) NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `sql_group_relations_object_id_group_id_object_type_398f04d1_uniq` (`object_id`,`group_id`,`object_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sql_group_relations`
--

LOCK TABLES `sql_group_relations` WRITE;
/*!40000 ALTER TABLE `sql_group_relations` DISABLE KEYS */;
/*!40000 ALTER TABLE `sql_group_relations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sql_master_config`
--

DROP TABLE IF EXISTS `sql_master_config`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sql_master_config` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cluster_name` varchar(50) NOT NULL,
  `master_host` varchar(200) NOT NULL,
  `master_port` int(11) NOT NULL,
  `master_user` varchar(100) NOT NULL,
  `master_password` varchar(300) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `update_time` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `cluster_name` (`cluster_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sql_master_config`
--

LOCK TABLES `sql_master_config` WRITE;
/*!40000 ALTER TABLE `sql_master_config` DISABLE KEYS */;
/*!40000 ALTER TABLE `sql_master_config` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sql_slave_config`
--

DROP TABLE IF EXISTS `sql_slave_config`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sql_slave_config` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cluster_name` varchar(50) NOT NULL,
  `slave_host` varchar(200) NOT NULL,
  `slave_port` int(11) NOT NULL,
  `slave_user` varchar(100) NOT NULL,
  `slave_password` varchar(300) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `update_time` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `cluster_name` (`cluster_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sql_slave_config`
--

LOCK TABLES `sql_slave_config` WRITE;
/*!40000 ALTER TABLE `sql_slave_config` DISABLE KEYS */;
/*!40000 ALTER TABLE `sql_slave_config` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sql_users`
--

DROP TABLE IF EXISTS `sql_users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sql_users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(30) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  `display` varchar(50) NOT NULL,
  `role` varchar(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sql_users`
--

LOCK TABLES `sql_users` WRITE;
/*!40000 ALTER TABLE `sql_users` DISABLE KEYS */;
/*!40000 ALTER TABLE `sql_users` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sql_users_groups`
--

DROP TABLE IF EXISTS `sql_users_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sql_users_groups` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `users_id` int(11) NOT NULL,
  `group_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `sql_users_groups_users_id_group_id_4540dddc_uniq` (`users_id`,`group_id`),
  KEY `sql_users_groups_group_id_d572a82e_fk_auth_group_id` (`group_id`),
  CONSTRAINT `sql_users_groups_group_id_d572a82e_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `sql_users_groups_users_id_d674bacf_fk_sql_users_id` FOREIGN KEY (`users_id`) REFERENCES `sql_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sql_users_groups`
--

LOCK TABLES `sql_users_groups` WRITE;
/*!40000 ALTER TABLE `sql_users_groups` DISABLE KEYS */;
/*!40000 ALTER TABLE `sql_users_groups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sql_users_user_permissions`
--

DROP TABLE IF EXISTS `sql_users_user_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sql_users_user_permissions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `users_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `sql_users_user_permissions_users_id_permission_id_5fffb2bb_uniq` (`users_id`,`permission_id`),
  KEY `sql_users_user_permi_permission_id_e990caab_fk_auth_perm` (`permission_id`),
  CONSTRAINT `sql_users_user_permi_permission_id_e990caab_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `sql_users_user_permissions_users_id_efad14b0_fk_sql_users_id` FOREIGN KEY (`users_id`) REFERENCES `sql_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sql_users_user_permissions`
--

LOCK TABLES `sql_users_user_permissions` WRITE;
/*!40000 ALTER TABLE `sql_users_user_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `sql_users_user_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sql_workflow`
--

DROP TABLE IF EXISTS `sql_workflow`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sql_workflow` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `workflow_name` varchar(50) NOT NULL,
  `group_id` int(11) NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `engineer` varchar(50) NOT NULL,
  `review_man` varchar(50) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `finish_time` datetime(6) DEFAULT NULL,
  `status` varchar(50) NOT NULL,
  `is_backup` varchar(20) NOT NULL,
  `review_content` longtext NOT NULL,
  `cluster_name` varchar(50) NOT NULL,
  `db_name` varchar(60) NOT NULL,
  `reviewok_time` datetime(6) DEFAULT NULL,
  `sql_content` longtext NOT NULL,
  `execute_result` longtext NOT NULL,
  `is_manual` int(11) NOT NULL,
  `audit_remark` varchar(200) DEFAULT NULL,
  `sql_syntax` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sql_workflow`
--

LOCK TABLES `sql_workflow` WRITE;
/*!40000 ALTER TABLE `sql_workflow` DISABLE KEYS */;
/*!40000 ALTER TABLE `sql_workflow` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `workflow_audit`
--

DROP TABLE IF EXISTS `workflow_audit`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `workflow_audit` (
  `audit_id` int(11) NOT NULL AUTO_INCREMENT,
  `group_id` int(11) NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `workflow_id` bigint(20) NOT NULL,
  `workflow_type` int(11) NOT NULL,
  `workflow_title` varchar(50) NOT NULL,
  `workflow_remark` varchar(140) NOT NULL,
  `audit_users` varchar(255) NOT NULL,
  `current_audit_user` varchar(20) NOT NULL,
  `next_audit_user` varchar(20) NOT NULL,
  `current_status` int(11) NOT NULL,
  `create_user` varchar(20) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`audit_id`),
  UNIQUE KEY `workflow_audit_workflow_id_workflow_type_14044a22_uniq` (`workflow_id`,`workflow_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `workflow_audit`
--

LOCK TABLES `workflow_audit` WRITE;
/*!40000 ALTER TABLE `workflow_audit` DISABLE KEYS */;
/*!40000 ALTER TABLE `workflow_audit` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `workflow_audit_detail`
--

DROP TABLE IF EXISTS `workflow_audit_detail`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `workflow_audit_detail` (
  `audit_detail_id` int(11) NOT NULL AUTO_INCREMENT,
  `audit_id` int(11) NOT NULL,
  `audit_user` varchar(20) NOT NULL,
  `audit_time` datetime(6) NOT NULL,
  `audit_status` int(11) NOT NULL,
  `remark` varchar(140) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`audit_detail_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `workflow_audit_detail`
--

LOCK TABLES `workflow_audit_detail` WRITE;
/*!40000 ALTER TABLE `workflow_audit_detail` DISABLE KEYS */;
/*!40000 ALTER TABLE `workflow_audit_detail` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `workflow_audit_setting`
--

DROP TABLE IF EXISTS `workflow_audit_setting`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `workflow_audit_setting` (
  `audit_setting_id` int(11) NOT NULL AUTO_INCREMENT,
  `group_id` int(11) NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `workflow_type` int(11) NOT NULL,
  `audit_users` varchar(255) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `sys_time` datetime(6) NOT NULL,
  PRIMARY KEY (`audit_setting_id`),
  UNIQUE KEY `workflow_audit_setting_group_id_workflow_type_5884053a_uniq` (`group_id`,`workflow_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `workflow_audit_setting`
--

LOCK TABLES `workflow_audit_setting` WRITE;
/*!40000 ALTER TABLE `workflow_audit_setting` DISABLE KEYS */;
/*!40000 ALTER TABLE `workflow_audit_setting` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2018-07-05  9:22:45
