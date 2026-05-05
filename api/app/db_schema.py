# -*- coding: utf-8 -*-
"""与 deploy/init-app.sql 保持一致的 DDL，供启动时缺表补建（勿单独改此处，需同步 SQL 文件）。"""

APP_USERS_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS `app_users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户主键',
  `username` VARCHAR(64) NOT NULL COMMENT '登录名',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Web 注册用户'
"""
