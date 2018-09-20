-- 修改查询日志表
ALTER TABLE query_log
  ADD priv_check TINYINT NOT NULL DEFAULT 0
COMMENT '查询权限是否正常校验，1, 正常, 2, 跳过'
  AFTER user_display,
  ADD hit_rule TINYINT NOT NULL DEFAULT 0
COMMENT '查询是否命中脱敏规则，0,未知, 1, 命中, 2,未命中'
  AFTER priv_check,
  ADD masking TINYINT NOT NULL DEFAULT 0
COMMENT '查询结果是否正常脱敏，1, 是, 2, 否'
  AFTER hit_rule;