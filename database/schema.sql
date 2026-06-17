-- CreatorPulse MVP MySQL schema.
-- This schema follows 04A_MVP数据Mock与Insight实现SPEC.md and is intentionally
-- data-object oriented, not UI-card oriented.

CREATE DATABASE IF NOT EXISTS creatorpulse
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE creatorpulse;

CREATE TABLE IF NOT EXISTS creators (
  creator_id VARCHAR(64) PRIMARY KEY,
  display_name VARCHAR(128) NOT NULL,
  avatar_url VARCHAR(512) NULL,
  niche_tags JSON NOT NULL,
  timezone VARCHAR(64) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS users (
  user_id VARCHAR(64) PRIMARY KEY,
  creator_id VARCHAR(64) NOT NULL,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  display_name VARCHAR(128) NOT NULL,
  role VARCHAR(32) NOT NULL DEFAULT 'CREATOR',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_users_creator
    FOREIGN KEY (creator_id) REFERENCES creators (creator_id)
    ON DELETE CASCADE,
  UNIQUE KEY uk_users_email (email),
  UNIQUE KEY uk_users_creator (creator_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS platform_accounts (
  account_id VARCHAR(64) PRIMARY KEY,
  creator_id VARCHAR(64) NOT NULL,
  platform VARCHAR(32) NOT NULL,
  platform_display_name VARCHAR(128) NOT NULL,
  binding_status VARCHAR(32) NOT NULL,
  sync_latency_seconds INT NOT NULL,
  collection_interval_seconds INT NOT NULL,
  data_scopes JSON NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_platform_accounts_creator
    FOREIGN KEY (creator_id) REFERENCES creators (creator_id)
    ON DELETE CASCADE,
  UNIQUE KEY uk_platform_accounts_creator_platform (creator_id, platform)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS videos (
  video_id VARCHAR(96) PRIMARY KEY,
  creator_id VARCHAR(64) NOT NULL,
  platform VARCHAR(32) NOT NULL,
  platform_label VARCHAR(32) NULL,
  title VARCHAR(255) NOT NULL,
  content_type VARCHAR(32) NOT NULL,
  content_type_label VARCHAR(32) NULL,
  topic_tags JSON NOT NULL,
  publish_time DATETIME NOT NULL,
  lifecycle_stage VARCHAR(32) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_videos_creator
    FOREIGN KEY (creator_id) REFERENCES creators (creator_id)
    ON DELETE CASCADE,
  KEY idx_videos_creator_platform (creator_id, platform),
  KEY idx_videos_content_type (content_type),
  KEY idx_videos_publish_time (publish_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS video_metric_snapshots (
  snapshot_id VARCHAR(96) PRIMARY KEY,
  video_id VARCHAR(96) NOT NULL,
  creator_id VARCHAR(64) NOT NULL,
  platform VARCHAR(32) NOT NULL,
  views BIGINT NOT NULL,
  likes BIGINT NOT NULL,
  comments BIGINT NOT NULL,
  shares BIGINT NOT NULL,
  saves BIGINT NOT NULL,
  profile_visits BIGINT NOT NULL,
  new_followers BIGINT NOT NULL,
  completion_rate DECIMAL(12, 6) NOT NULL,
  average_watch_seconds INT NOT NULL,
  engagement_rate DECIMAL(12, 6) NOT NULL,
  conversion_rate DECIMAL(12, 6) NOT NULL,
  comment_rate DECIMAL(12, 6) NOT NULL,
  save_rate DECIMAL(12, 6) NOT NULL,
  share_rate DECIMAL(12, 6) NOT NULL,
  collected_at DATETIME NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_video_metric_snapshots_video
    FOREIGN KEY (video_id) REFERENCES videos (video_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_video_metric_snapshots_creator
    FOREIGN KEY (creator_id) REFERENCES creators (creator_id)
    ON DELETE CASCADE,
  KEY idx_video_metric_creator_collected (creator_id, collected_at),
  KEY idx_video_metric_platform (platform)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS video_traffic_source_metrics (
  video_id VARCHAR(96) NOT NULL,
  source VARCHAR(32) NOT NULL,
  views BIGINT NOT NULL,
  new_followers BIGINT NOT NULL,
  conversion_rate DECIMAL(12, 6) NOT NULL,
  save_rate DECIMAL(12, 6) NOT NULL,
  comment_rate DECIMAL(12, 6) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (video_id, source),
  CONSTRAINT fk_video_traffic_source_metrics_video
    FOREIGN KEY (video_id) REFERENCES videos (video_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS creator_metric_snapshots (
  snapshot_id VARCHAR(96) PRIMARY KEY,
  creator_id VARCHAR(64) NOT NULL,
  metric_date DATE NOT NULL,
  total_followers BIGINT NOT NULL,
  new_followers BIGINT NOT NULL,
  lost_followers BIGINT NOT NULL,
  net_followers BIGINT NOT NULL,
  total_views BIGINT NOT NULL,
  total_interactions BIGINT NOT NULL,
  profile_visits BIGINT NOT NULL,
  follower_growth_rate DECIMAL(12, 6) NOT NULL,
  view_to_follower_rate DECIMAL(12, 6) NOT NULL,
  stickiness_score DECIMAL(8, 2) NOT NULL,
  growth_health_score DECIMAL(8, 2) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_creator_metric_snapshots_creator
    FOREIGN KEY (creator_id) REFERENCES creators (creator_id)
    ON DELETE CASCADE,
  UNIQUE KEY uk_creator_metric_snapshots_creator_date (creator_id, metric_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audience_profile_snapshots (
  snapshot_id VARCHAR(96) PRIMARY KEY,
  creator_id VARCHAR(64) NOT NULL,
  gender JSON NOT NULL,
  age_groups JSON NOT NULL,
  regions JSON NOT NULL,
  active_hours JSON NOT NULL,
  interest_tags JSON NOT NULL,
  high_value_segments JSON NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_audience_profile_snapshots_creator
    FOREIGN KEY (creator_id) REFERENCES creators (creator_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS topic_trend_snapshots (
  topic_id VARCHAR(96) PRIMARY KEY,
  topic_name VARCHAR(128) NOT NULL,
  platforms JSON NOT NULL,
  heat_score INT NOT NULL,
  growth_rate DECIMAL(12, 6) NOT NULL,
  audience_fit_score INT NOT NULL,
  creator_fit_score INT NOT NULL,
  risk_level VARCHAR(32) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_topic_trend_heat_score (heat_score),
  KEY idx_topic_trend_creator_fit_score (creator_fit_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS insights (
  insight_id VARCHAR(96) PRIMARY KEY,
  creator_id VARCHAR(64) NOT NULL,
  type VARCHAR(32) NOT NULL,
  scope VARCHAR(32) NOT NULL,
  target_id VARCHAR(96) NOT NULL,
  title VARCHAR(255) NOT NULL,
  summary TEXT NOT NULL,
  priority VARCHAR(32) NOT NULL,
  generated_by VARCHAR(64) NOT NULL,
  generated_at DATETIME NOT NULL,
  page_targets JSON NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_insights_creator
    FOREIGN KEY (creator_id) REFERENCES creators (creator_id)
    ON DELETE CASCADE,
  KEY idx_insights_creator_priority (creator_id, priority),
  KEY idx_insights_scope_target (scope, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS insight_evidence_metrics (
  insight_id VARCHAR(96) NOT NULL,
  position INT NOT NULL,
  label VARCHAR(128) NOT NULL,
  value_json JSON NOT NULL,
  unit VARCHAR(32) NULL,
  direction VARCHAR(32) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (insight_id, position),
  CONSTRAINT fk_insight_evidence_metrics_insight
    FOREIGN KEY (insight_id) REFERENCES insights (insight_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS recommended_actions (
  action_id VARCHAR(96) PRIMARY KEY,
  insight_id VARCHAR(96) NOT NULL,
  position INT NOT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT NOT NULL,
  expected_impact VARCHAR(255) NULL,
  related_page VARCHAR(128) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_recommended_actions_insight
    FOREIGN KEY (insight_id) REFERENCES insights (insight_id)
    ON DELETE CASCADE,
  UNIQUE KEY uk_recommended_actions_insight_position (insight_id, position)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS spark_platform_metric_summaries (
  run_id VARCHAR(96) NOT NULL,
  creator_id VARCHAR(64) NOT NULL,
  platform VARCHAR(32) NOT NULL,
  total_views BIGINT NOT NULL,
  new_followers BIGINT NOT NULL,
  video_count INT NOT NULL,
  conversion_rate DECIMAL(12, 6) NOT NULL,
  calculated_at DATETIME NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (run_id, creator_id, platform),
  CONSTRAINT fk_spark_platform_metric_summaries_creator
    FOREIGN KEY (creator_id) REFERENCES creators (creator_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS spark_video_follower_contributions (
  run_id VARCHAR(96) NOT NULL,
  rank_position INT NOT NULL,
  creator_id VARCHAR(64) NOT NULL,
  video_id VARCHAR(96) NOT NULL,
  platform VARCHAR(32) NOT NULL,
  title VARCHAR(255) NOT NULL,
  views BIGINT NOT NULL,
  new_followers BIGINT NOT NULL,
  conversion_rate DECIMAL(12, 6) NOT NULL,
  calculated_at DATETIME NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (run_id, creator_id, rank_position),
  CONSTRAINT fk_spark_video_follower_contributions_creator
    FOREIGN KEY (creator_id) REFERENCES creators (creator_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_spark_video_follower_contributions_video
    FOREIGN KEY (video_id) REFERENCES videos (video_id)
    ON DELETE CASCADE,
  KEY idx_spark_video_follower_contributions_video (video_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
