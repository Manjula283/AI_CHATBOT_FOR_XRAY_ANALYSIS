-- =============================================================================
-- AI Chest X-ray Analysis Chatbot with Login and Analysis History (PRD v1.0)
-- MySQL 8.0+ Database Schema Definition
-- =============================================================================

CREATE DATABASE IF NOT EXISTS chest_xray_ai_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE chest_xray_ai_db;

-- -----------------------------------------------------------------------------
-- 10.1 Users Table
-- Stores registered user accounts and secure password hashes (FR-01, FR-02)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 10.2 Analyses Table
-- Stores chest X-ray upload references, AI-generated reports, and status (FR-04, FR-07)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Analyses (
    analysis_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    image_path VARCHAR(512) NOT NULL,
    processed_image_path VARCHAR(512) NULL,
    case_label VARCHAR(180) NOT NULL DEFAULT 'Chest Radiograph (PA View)',
    generated_report LONGTEXT NOT NULL,
    structured_metadata LONGTEXT NULL,
    status ENUM('processing', 'completed', 'failed') NOT NULL DEFAULT 'processing',
    model_version VARCHAR(120) NOT NULL DEFAULT 'ThoraxVLM-RadDraft-v2.4 (Ensemble)',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_analyses_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id)
        ON DELETE CASCADE,
    INDEX idx_analyses_user_created (user_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 10.3 ChatMessages Table
-- Stores report-grounded conversation messages between user and assistant (FR-05, FR-07)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ChatMessages (
    message_id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_id INT NOT NULL,
    role ENUM('user', 'assistant') NOT NULL,
    message_text TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_chatmessages_analysis
        FOREIGN KEY (analysis_id) REFERENCES Analyses(analysis_id)
        ON DELETE CASCADE,
    INDEX idx_chatmessages_analysis_created (analysis_id, created_at ASC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
