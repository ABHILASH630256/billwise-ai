-- ============================================
-- BillWise AI — Enhanced Database Schema
-- Adds new tables for premium features
-- ============================================

USE billwise_ai;

-- ============ ALTER EXISTING TABLES ============

-- Enhance bills table with new fields
ALTER TABLE bills ADD COLUMN IF NOT EXISTS 
    ocr_confidence FLOAT DEFAULT 0.0 AFTER confidence;

ALTER TABLE bills ADD COLUMN IF NOT EXISTS 
    predicted_category VARCHAR(100) AFTER category;

ALTER TABLE bills ADD COLUMN IF NOT EXISTS 
    gst_amount DECIMAL(12,2) DEFAULT 0.00 AFTER amount;

ALTER TABLE bills ADD COLUMN IF NOT EXISTS 
    payment_method VARCHAR(50) AFTER gst_amount;

ALTER TABLE bills ADD COLUMN IF NOT EXISTS 
    is_duplicate BOOLEAN DEFAULT FALSE AFTER payment_method;

ALTER TABLE bills ADD COLUMN IF NOT EXISTS 
    duplicate_of_id INT AFTER is_duplicate;

ALTER TABLE bills ADD COLUMN IF NOT EXISTS 
    is_recurring BOOLEAN DEFAULT FALSE AFTER duplicate_of_id;

ALTER TABLE bills ADD COLUMN IF NOT EXISTS 
    bill_quality VARCHAR(50) DEFAULT 'Good' AFTER is_recurring;

ALTER TABLE bills ADD COLUMN IF NOT EXISTS 
    user_id INT AFTER bill_quality;

-- Enhance users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS 
    email VARCHAR(255) AFTER username;

ALTER TABLE users ADD COLUMN IF NOT EXISTS 
    full_name VARCHAR(255) AFTER email;

ALTER TABLE users ADD COLUMN IF NOT EXISTS 
    joined_date DATETIME DEFAULT CURRENT_TIMESTAMP AFTER full_name;

ALTER TABLE users ADD COLUMN IF NOT EXISTS 
    theme VARCHAR(50) DEFAULT 'dark' AFTER joined_date;

ALTER TABLE users ADD COLUMN IF NOT EXISTS 
    currency VARCHAR(10) DEFAULT 'INR' AFTER theme;

ALTER TABLE users ADD COLUMN IF NOT EXISTS 
    default_budget DECIMAL(12,2) DEFAULT 10000.00 AFTER currency;

-- ============ NEW TABLES ============

-- Budgets table
CREATE TABLE IF NOT EXISTS budgets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    category VARCHAR(100) NOT NULL,
    limit_amount DECIMAL(12,2) NOT NULL,
    spent_amount DECIMAL(12,2) DEFAULT 0.00,
    month_year VARCHAR(20) NOT NULL,
    alert_threshold INT DEFAULT 80,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_category (category),
    INDEX idx_month_year (month_year),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    type VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT,
    data JSON,
    is_read BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_type (type),
    INDEX idx_is_read (is_read),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Achievements table
CREATE TABLE IF NOT EXISTS achievements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    badge_name VARCHAR(100) NOT NULL,
    badge_description TEXT,
    badge_icon VARCHAR(255),
    points INT DEFAULT 10,
    unlocked_at DATETIME,
    
    INDEX idx_user_id (user_id),
    INDEX idx_badge_name (badge_name),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Recurring bills detection table
CREATE TABLE IF NOT EXISTS recurring_bills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    vendor_name VARCHAR(255),
    category VARCHAR(100),
    average_amount DECIMAL(12,2),
    frequency VARCHAR(50), -- 'weekly', 'monthly', 'yearly'
    expected_next_date DATE,
    last_bill_id INT,
    occurrence_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_vendor_name (vendor_name),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (last_bill_id) REFERENCES bills(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Bill analysis details
CREATE TABLE IF NOT EXISTS bill_analysis (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bill_id INT NOT NULL UNIQUE,
    vendor_name VARCHAR(255),
    bill_date DATE,
    total_amount DECIMAL(12,2),
    gst_amount DECIMAL(12,2),
    payment_method VARCHAR(50),
    item_count INT,
    category_prediction VARCHAR(100),
    prediction_confidence FLOAT,
    ocr_confidence FLOAT,
    bill_quality_score INT,
    detected_fields JSON,
    warnings JSON,
    ai_summary TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_bill_id (bill_id),
    INDEX idx_category (category_prediction),
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- AI Recommendations
CREATE TABLE IF NOT EXISTS ai_recommendations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    recommendation_text TEXT NOT NULL,
    category VARCHAR(100),
    priority VARCHAR(50), -- 'high', 'medium', 'low'
    action_type VARCHAR(100), -- 'reduce', 'increase', 'monitor'
    data JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_priority (priority),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Savings challenges
CREATE TABLE IF NOT EXISTS savings_challenges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    challenge_name VARCHAR(255) NOT NULL,
    goal_category VARCHAR(100),
    target_reduction_percent INT,
    baseline_amount DECIMAL(12,2),
    current_amount DECIMAL(12,2),
    month_year VARCHAR(20),
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'completed', 'failed'
    progress_percent INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Financial health score history
CREATE TABLE IF NOT EXISTS financial_scores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    score INT,
    budget_health INT,
    spending_health INT,
    savings_health INT,
    balance_health INT,
    calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_calculated_at (calculated_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Export history
CREATE TABLE IF NOT EXISTS exports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    export_type VARCHAR(50), -- 'pdf', 'excel', 'csv', 'png'
    export_format VARCHAR(100), -- 'dashboard', 'bills', 'report', etc
    file_path VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Add indices for performance
CREATE INDEX idx_bills_user_created ON bills(user_id, created_at);
CREATE INDEX idx_bills_category_date ON bills(category, bill_date);
CREATE INDEX idx_bills_amount ON bills(amount);

-- Add foreign key for bills to users
ALTER TABLE bills ADD CONSTRAINT fk_bills_user 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

SHOW TABLES;
