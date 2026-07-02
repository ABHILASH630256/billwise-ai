-- ============================================
-- BillWise AI — Complete Database Schema (Aiven Compatible)
-- ============================================

-- ============================================
-- BILLS TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS bills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_name VARCHAR(255) NOT NULL,
    shop_name VARCHAR(255) DEFAULT 'Unknown',
    bill_date VARCHAR(50) DEFAULT NULL,
    amount DECIMAL(12,2) DEFAULT 0.00,
    extracted_text LONGTEXT DEFAULT NULL,
    category VARCHAR(100) DEFAULT 'Other',
    confidence FLOAT DEFAULT 0.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_category (category),
    INDEX idx_created_at (created_at),
    INDEX idx_shop_name (shop_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- USERS TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- OPTIONAL TEST QUERIES
-- ============================================

SHOW TABLES;

DESCRIBE bills;

DESCRIBE users;

SELECT COUNT(*) AS total_bills FROM bills;

SELECT COUNT(*) AS total_users FROM users;