-- 数据库：chat_bi_case
-- 表：stock_daily（与 tushare daily 字段对应，便于从脚本导入）

CREATE DATABASE IF NOT EXISTS `chat_bi_case`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `chat_bi_case`;

CREATE TABLE IF NOT EXISTS `stock_daily` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `stock_name` VARCHAR(32) NOT NULL COMMENT '股票名称',
  `ts_code` VARCHAR(16) NOT NULL COMMENT '证券代码',
  `trade_date` DATE NOT NULL COMMENT '交易日期',
  `open_price` DECIMAL(16,4) NOT NULL COMMENT '开盘价',
  `high_price` DECIMAL(16,4) NOT NULL COMMENT '最高价',
  `low_price` DECIMAL(16,4) NOT NULL COMMENT '最低价',
  `close_price` DECIMAL(16,4) NOT NULL COMMENT '收盘价',
  `pre_close` DECIMAL(16,4) NOT NULL COMMENT '昨收价',
  `price_change` DECIMAL(16,4) NOT NULL COMMENT '涨跌额',
  `pct_chg` DECIMAL(12,4) NOT NULL COMMENT '涨跌幅(%)',
  `vol` BIGINT UNSIGNED NOT NULL COMMENT '成交量(手)',
  `amount` DECIMAL(20,4) NOT NULL COMMENT '成交额(千元)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ts_code_trade_date` (`ts_code`, `trade_date`),
  KEY `idx_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='A股日线行情';

-- 与 deploy/init-app.sql 一致；initdb 仅首次执行，此处保证仅挂载 01 时也有用户表定义
CREATE TABLE IF NOT EXISTS `app_users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户主键',
  `username` VARCHAR(64) NOT NULL COMMENT '登录名',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Web 注册用户';
