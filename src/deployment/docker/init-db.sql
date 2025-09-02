-- Initialize the database for Itqan CMS
-- This file is executed when the PostgreSQL container starts for the first time

-- Create the database if it doesn't exist (handled by POSTGRES_DB environment variable)
-- Create additional schemas or initial data here if needed

-- Example: Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- You can add more initialization SQL here
