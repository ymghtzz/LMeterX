SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
-- 确保数据库存在并使用该数据库
CREATE DATABASE IF NOT EXISTS lmeterx;
USE lmeterx;

-- ----------------------------
-- Table structure for tasks
-- ----------------------------
DROP TABLE IF EXISTS `tasks`;
CREATE TABLE `tasks` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT 'idle',
  `target_host` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `model` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `system_prompt` longtext COLLATE utf8mb4_unicode_ci,
  `user_prompt` longtext COLLATE utf8mb4_unicode_ci,
  `stream_mode` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT 'True',
  `concurrent_users` int(11) DEFAULT '1',
  `spawn_rate` int(11) DEFAULT '0',
  `duration` int(11) DEFAULT '60',
  `chat_type` int(11) DEFAULT '0',
  `log_file` longtext COLLATE utf8mb4_unicode_ci,
  `result_file` longtext COLLATE utf8mb4_unicode_ci,
  `cert_file` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `key_file` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `headers` json DEFAULT NULL,
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `api_path` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'API路径',
  PRIMARY KEY (`id`),
  KEY `idx_status_created` (`status`,`created_at`),
  KEY `idx_updated_at` (`updated_at`),
  KEY `idx_name` (`name`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for task_results
-- ----------------------------
DROP TABLE IF EXISTS `task_results`;
CREATE TABLE `task_results` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `task_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '任务ID',
  `metric_type` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '指标类型',
  `num_requests` int(11) DEFAULT '0' COMMENT '请求总数量',
  `num_failures` int(11) DEFAULT '0' COMMENT '请求失败数量',
  `avg_latency` float DEFAULT '0' COMMENT '请求平均响应时间',
  `min_latency` float DEFAULT '0' COMMENT '请求最小响应时间',
  `max_latency` float DEFAULT '0' COMMENT '请求最大响应时间',
  `median_latency` float DEFAULT '0' COMMENT '请求中位响应时间',
  `p90_latency` float DEFAULT '0' COMMENT '请求90%响应时间',
  `rps` float DEFAULT '0' COMMENT '每秒请求数',
  `avg_content_length` float DEFAULT '0' COMMENT '平均输出的字符长度',
  `completion_tps` float DEFAULT '0' COMMENT '每秒输出的token数量',
  `total_tps` float DEFAULT '0' COMMENT '每秒输入输出的总token数量',
  `avg_total_tokens_per_req` float DEFAULT '0' COMMENT '每个请求的平均输入输出的总token数量',
  `avg_completion_tokens_per_req` float DEFAULT '0' COMMENT '每个请求的平均输出token数量',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_task_id` (`task_id`)
) ENGINE=InnoDB AUTO_INCREMENT=262 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for test_insights (AI Analysis)
-- ----------------------------
DROP TABLE IF EXISTS `test_insights`;
CREATE TABLE `test_insights` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `task_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `eval_prompt` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `analysis_report` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT 'pending, processing, completed, failed',
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `task_id` (`task_id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for analysis_jobs (Background Analysis Jobs)
-- ----------------------------
DROP TABLE IF EXISTS `analysis_jobs`;
CREATE TABLE `analysis_jobs` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `task_ids` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'JSON string of task IDs',
  `analysis_type` int(11) NOT NULL COMMENT '0=single task, 1=multiple tasks',
  `language` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'en',
  `eval_prompt` text COLLATE utf8mb4_unicode_ci,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT 'pending, processing, completed, failed',
  `result_data` longtext COLLATE utf8mb4_unicode_ci COMMENT 'JSON string of analysis result',
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_analysis_type` (`analysis_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 最后重新启用外键检查
SET FOREIGN_KEY_CHECKS = 1;
