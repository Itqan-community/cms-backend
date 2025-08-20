-- Itqan CMS Database Initialization Script
-- This script sets up the initial database configuration

-- Ensure UUID extension is available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create additional schemas if needed
-- CREATE SCHEMA IF NOT EXISTS content;
-- CREATE SCHEMA IF NOT EXISTS analytics;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE itqan_cms TO itqan_user;
GRANT USAGE ON SCHEMA public TO itqan_user;
GRANT CREATE ON SCHEMA public TO itqan_user;

-- Set default permissions for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO itqan_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO itqan_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO itqan_user;

-- Configure PostgreSQL for Django
ALTER ROLE itqan_user SET client_encoding TO 'utf8';
ALTER ROLE itqan_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE itqan_user SET timezone TO 'UTC';

-- Log successful initialization
INSERT INTO pg_catalog.pg_description (objoid, classoid, objsubid, description)
VALUES (
    (SELECT oid FROM pg_database WHERE datname = 'itqan_cms'),
    (SELECT oid FROM pg_class WHERE relname = 'pg_database'),
    0,
    'Itqan CMS Database - Initialized at ' || NOW()::text
)
ON CONFLICT DO NOTHING;
