-- ==============================================
-- Itqan CMS - Database Initialization Script
-- ==============================================
-- This script runs automatically when PostgreSQL container starts

-- Create extensions that Strapi might need
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create additional databases for testing if needed
-- CREATE DATABASE itqan_cms_test;

-- Grant necessary permissions
-- GRANT ALL PRIVILEGES ON DATABASE itqan_cms TO cms_user;

-- Set timezone
SET timezone = 'UTC';

-- Log initialization
SELECT 'Itqan CMS database initialized successfully' AS message;
