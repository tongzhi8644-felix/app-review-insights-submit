CREATE DATABASE IF NOT EXISTS app_review_insights
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE app_review_insights;

-- Tables are also created automatically by SQLAlchemy on first run (db.create_all).
-- This file is for manual DBA setup / inspection.

CREATE TABLE IF NOT EXISTS analysis_runs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  app_id VARCHAR(32) NOT NULL,
  app_url VARCHAR(512) NOT NULL,
  analysis_goal TEXT,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  current_stage VARCHAR(64),
  progress_pct INT NOT NULL DEFAULT 0,
  error_message TEXT,
  data_source VARCHAR(64),
  evidence_sufficient TINYINT(1) DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_runs_app_id (app_id),
  INDEX idx_runs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stage_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id INT NOT NULL,
  stage VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  message TEXT,
  detail_json JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_stage_run (run_id),
  CONSTRAINT fk_stage_run FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reviews_raw (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id INT NOT NULL,
  review_id VARCHAR(64) NOT NULL,
  author VARCHAR(255),
  rating INT,
  title TEXT,
  content TEXT,
  version VARCHAR(64),
  updated_at VARCHAR(64),
  vote_sum INT DEFAULT 0,
  vote_count INT DEFAULT 0,
  raw_json JSON,
  INDEX idx_raw_run (run_id),
  INDEX idx_raw_review (review_id),
  CONSTRAINT fk_raw_run FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reviews_clean (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id INT NOT NULL,
  review_id VARCHAR(64) NOT NULL,
  author VARCHAR(255),
  rating INT,
  title TEXT,
  content TEXT,
  version VARCHAR(64),
  updated_at VARCHAR(64),
  language VARCHAR(16),
  is_duplicate TINYINT(1) DEFAULT 0,
  content_hash VARCHAR(64),
  INDEX idx_clean_run (run_id),
  INDEX idx_clean_review (review_id),
  CONSTRAINT fk_clean_run FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS classifications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id INT NOT NULL,
  review_id VARCHAR(64) NOT NULL,
  topics_json JSON,
  sentiment VARCHAR(32),
  priority_hint VARCHAR(32),
  model_note TEXT,
  INDEX idx_cls_run (run_id),
  CONSTRAINT fk_cls_run FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS findings (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id INT NOT NULL,
  finding_key VARCHAR(64) NOT NULL,
  title VARCHAR(512) NOT NULL,
  summary TEXT,
  source_review_ids_json JSON,
  sample_count INT DEFAULT 0,
  confidence FLOAT,
  uncertainty TEXT,
  conflicting_evidence TEXT,
  is_model_generated TINYINT(1) DEFAULT 1,
  is_assumption TINYINT(1) DEFAULT 0,
  evidence_excerpts_json JSON,
  INDEX idx_find_run (run_id),
  CONSTRAINT fk_find_run FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS prd_documents (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id INT NOT NULL,
  version_plan_json JSON,
  prd_markdown MEDIUMTEXT,
  requirements_json JSON,
  model_meta_json JSON,
  INDEX idx_prd_run (run_id),
  CONSTRAINT fk_prd_run FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS test_cases (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id INT NOT NULL,
  case_id VARCHAR(64) NOT NULL,
  requirement_id VARCHAR(64),
  title VARCHAR(512),
  steps_json JSON,
  expected_result TEXT,
  source_review_ids_json JSON,
  INDEX idx_tc_run (run_id),
  CONSTRAINT fk_tc_run FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS validation_results (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id INT NOT NULL,
  is_valid TINYINT(1) DEFAULT 0,
  issues_json JSON,
  revisions_json JSON,
  summary TEXT,
  INDEX idx_val_run (run_id),
  CONSTRAINT fk_val_run FOREIGN KEY (run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
