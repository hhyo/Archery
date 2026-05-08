CREATE TABLE `redis_slow_query_review` (
  `checksum` char(32) NOT NULL COMMENT '指纹MD5值',
  `fingerprint` text NOT NULL COMMENT '参数化后的命令模板，如 "SET user:* *"',
  `sample` text NOT NULL COMMENT '原始命令示例（首次出现的那条）',
  `first_seen` datetime(6) DEFAULT NULL COMMENT '该指纹首次出现时间',
  `last_seen` datetime(6) DEFAULT NULL COMMENT '该指纹最后出现时间',
  PRIMARY KEY (`checksum`),
  KEY `idx_last_seen` (`last_seen`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Redis慢查询指纹表';

CREATE TABLE `redis_slow_query_review_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `checksum` char(32) NOT NULL COMMENT '关联指纹表',
  `sample` text NOT NULL COMMENT '原始命令示例（首次出现的那条）',
  `hostname` varchar(64) NOT NULL COMMENT 'Redis实例标识（IP:PORT或自定义名称）',
  `ts_min` datetime(6) NOT NULL COMMENT '本窗口内该指纹的最小执行时间',
  `ts_max` datetime(6) NOT NULL COMMENT '本窗口内该指纹的最大执行时间',
  `cnt` int(11) NOT NULL DEFAULT '0' COMMENT '本窗口内出现次数',
  `duration_sum` bigint(20) DEFAULT NULL COMMENT '总耗时（微秒）',
  `duration_min` bigint(20) DEFAULT NULL COMMENT '最小耗时（微秒）',
  `duration_max` bigint(20) DEFAULT NULL COMMENT '最大耗时（微秒）',
  `duration_pct_95` bigint(20) DEFAULT NULL COMMENT '95分位耗时（微秒）',
  `duration_stddev` decimal(20,4) DEFAULT NULL COMMENT '耗时标准差',
  `duration_median` bigint(20) DEFAULT NULL COMMENT '中位数耗时（微秒）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_checksum_window` (`checksum`, `hostname`, `ts_min`, `ts_max`),
  KEY `idx_hostname_ts` (`hostname`, `ts_min`),
  KEY `idx_checksum` (`checksum`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Redis慢查询历史统计表';

CREATE TABLE `redis_slowlog_cursor` (
  `hostname` varchar(64) NOT NULL COMMENT 'Redis实例标识',
  `last_processed_id` bigint(20) NOT NULL DEFAULT '0' COMMENT '已处理的最后一条slowlog ID',
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`hostname`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Redis慢查询游标表';