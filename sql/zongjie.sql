/*
 Navicat Premium Data Transfer

 Source Server         : docker_mysql8
 Source Server Type    : MySQL
 Source Server Version : 80406
 Source Host           : 127.0.0.1:3306
 Source Schema         : zongjie

 Target Server Type    : MySQL
 Target Server Version : 80406
 File Encoding         : 65001

 Date: 23/02/2026 11:57:47
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for app_config
-- ----------------------------
DROP TABLE IF EXISTS `app_config`;
CREATE TABLE `app_config`  (
  `id` int NOT NULL,
  `config_json` json NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for media_artifacts
-- ----------------------------
DROP TABLE IF EXISTS `media_artifacts`;
CREATE TABLE `media_artifacts`  (
  `id` bigint UNSIGNED NOT NULL AUTO_INCREMENT,
  `asset_id` bigint UNSIGNED NOT NULL,
  `artifact_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `artifact_version` int NOT NULL DEFAULT 1,
  `content_text` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `content_json` json NULL,
  `meta_json` json NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uq_media_artifacts_asset_type_ver`(`asset_id` ASC, `artifact_type` ASC, `artifact_version` ASC) USING BTREE,
  INDEX `idx_media_artifacts_asset_id`(`asset_id` ASC) USING BTREE,
  CONSTRAINT `fk_media_artifacts_asset_id` FOREIGN KEY (`asset_id`) REFERENCES `media_assets` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 305 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for media_assets
-- ----------------------------
DROP TABLE IF EXISTS `media_assets`;
CREATE TABLE `media_assets`  (
  `id` bigint UNSIGNED NOT NULL AUTO_INCREMENT,
  `md5` char(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `asset_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT '',
  `mime_type` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `display_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `is_read` tinyint(1) NOT NULL DEFAULT 0,
  `folder_id` bigint UNSIGNED NULL DEFAULT NULL,
  `media_type` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT '',
  `source_kind` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT '',
  `source_ref` varchar(1024) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `meta_json` json NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uq_media_assets_md5`(`md5` ASC) USING BTREE,
  INDEX `fk_media_assets_folder_id`(`folder_id` ASC) USING BTREE,
  CONSTRAINT `fk_media_assets_folder_id` FOREIGN KEY (`folder_id`) REFERENCES `media_folders` (`id`) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 305 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for media_folders
-- ----------------------------
DROP TABLE IF EXISTS `media_folders`;
CREATE TABLE `media_folders`  (
  `id` bigint UNSIGNED NOT NULL AUTO_INCREMENT,
  `parent_id` bigint UNSIGNED NULL DEFAULT NULL,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_media_folders_parent_id`(`parent_id` ASC) USING BTREE,
  CONSTRAINT `fk_media_folders_parent_id` FOREIGN KEY (`parent_id`) REFERENCES `media_folders` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 6 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for task_queue
-- ----------------------------
DROP TABLE IF EXISTS `task_queue`;
CREATE TABLE `task_queue`  (
  `id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `url` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `task_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'video',
  `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'pending',
  `progress` int NOT NULL DEFAULT 0,
  `created_at` double NOT NULL,
  `result_json` json NULL,
  `error_msg` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `config_json` json NULL,
  `logs_json` json NULL,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;
