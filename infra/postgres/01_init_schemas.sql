-- ZolaOS — Initialisation des schémas et des rôles
-- À exécuter par le superutilisateur PostgreSQL, une seule fois.
-- Idempotent.

\set ON_ERROR_STOP on

-- =========================================================================
-- 1. Extensions
-- =========================================================================
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =========================================================================
-- 2. Schémas
-- =========================================================================
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS memory;
CREATE SCHEMA IF NOT EXISTS rag_health;
CREATE SCHEMA IF NOT EXISTS rag_legal;
CREATE SCHEMA IF NOT EXISTS rag_erp;
CREATE SCHEMA IF NOT EXISTS rag_code;
CREATE SCHEMA IF NOT EXISTS audit;

-- =========================================================================
-- 3. Rôles (mots de passe injectés depuis .env via psql -v)
-- Les variables psql (:'var') ne fonctionnent pas dans les blocs DO/PL-pgSQL
-- (côté serveur). On utilise \gexec : génère le CREATE ROLE côté client,
-- l'envoie au serveur uniquement si le rôle n'existe pas encore.
-- =========================================================================
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', 'zolaos_migrator',    :'pwd_migrator')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zolaos_migrator')
\gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', 'zolaos_app',          :'pwd_app')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zolaos_app')
\gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', 'zolaos_health_agent', :'pwd_health')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zolaos_health_agent')
\gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', 'zolaos_legal_agent',  :'pwd_legal')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zolaos_legal_agent')
\gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', 'zolaos_erp_agent',    :'pwd_erp')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zolaos_erp_agent')
\gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', 'zolaos_code_agent',   :'pwd_code')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zolaos_code_agent')
\gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', 'zolaos_audit_writer', :'pwd_audit_w')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zolaos_audit_writer')
\gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', 'zolaos_audit_reader', :'pwd_audit_r')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zolaos_audit_reader')
\gexec

-- =========================================================================
-- 4. Propriété des schémas (migrator = owner unique)
-- =========================================================================
ALTER SCHEMA core       OWNER TO zolaos_migrator;
ALTER SCHEMA memory     OWNER TO zolaos_migrator;
ALTER SCHEMA rag_health OWNER TO zolaos_migrator;
ALTER SCHEMA rag_legal  OWNER TO zolaos_migrator;
ALTER SCHEMA rag_erp    OWNER TO zolaos_migrator;
ALTER SCHEMA rag_code   OWNER TO zolaos_migrator;
ALTER SCHEMA audit      OWNER TO zolaos_migrator;

-- =========================================================================
-- 5. Révocation par défaut (zero-trust)
-- =========================================================================
REVOKE ALL ON SCHEMA core, memory, rag_health, rag_legal, rag_erp, rag_code, audit FROM PUBLIC;

-- =========================================================================
-- 6. Privilèges fins par rôle
-- =========================================================================

-- zolaos_app : R/W core + memory, R sur rag_*, INSERT audit
GRANT USAGE ON SCHEMA core, memory, rag_health, rag_legal, rag_erp, rag_code, audit TO zolaos_app;
ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA core, memory
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO zolaos_app;
ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA core, memory
  GRANT USAGE, SELECT ON SEQUENCES TO zolaos_app;
ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA rag_health, rag_legal, rag_erp, rag_code
  GRANT SELECT ON TABLES TO zolaos_app;

-- Agents RAG : lecture seule sur leur schéma
GRANT USAGE ON SCHEMA rag_health TO zolaos_health_agent;
ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA rag_health
  GRANT SELECT ON TABLES TO zolaos_health_agent;

GRANT USAGE ON SCHEMA rag_legal TO zolaos_legal_agent;
ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA rag_legal
  GRANT SELECT ON TABLES TO zolaos_legal_agent;

GRANT USAGE ON SCHEMA rag_erp TO zolaos_erp_agent;
ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA rag_erp
  GRANT SELECT ON TABLES TO zolaos_erp_agent;

-- Agent Code : R sur son schéma, mais aussi écriture pour indexation incrémentale du codebase
GRANT USAGE ON SCHEMA rag_code TO zolaos_code_agent;
ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA rag_code
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO zolaos_code_agent;
ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA rag_code
  GRANT USAGE, SELECT ON SEQUENCES TO zolaos_code_agent;

-- Audit : writer = INSERT only, reader = SELECT only
GRANT USAGE ON SCHEMA audit TO zolaos_audit_writer, zolaos_audit_reader, zolaos_app;
ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA audit
  GRANT INSERT ON TABLES TO zolaos_audit_writer, zolaos_app;
ALTER DEFAULT PRIVILEGES FOR ROLE zolaos_migrator IN SCHEMA audit
  GRANT SELECT ON TABLES TO zolaos_audit_reader;
