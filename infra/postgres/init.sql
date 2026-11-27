-- Local development bootstrap: databases, roles, and extensions.
-- Runs once when the Postgres data volume is empty.

CREATE ROLE redliner LOGIN PASSWORD 'redliner';
CREATE ROLE relay LOGIN PASSWORD 'relay';

CREATE DATABASE redliner OWNER redliner;
CREATE DATABASE relay OWNER relay;

\connect redliner
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
GRANT ALL ON SCHEMA public TO redliner;

\connect relay
CREATE EXTENSION IF NOT EXISTS pg_trgm;
GRANT ALL ON SCHEMA public TO relay;