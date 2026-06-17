-- ZolaOS — Schéma de journalisation d'audit
-- Append-only, chaîne de hachage, immutable.

\set ON_ERROR_STOP on

SET ROLE zolaos_migrator;
SET search_path TO audit, public;

-- =========================================================================
-- Table principale du journal
-- =========================================================================
CREATE TABLE IF NOT EXISTS audit.log (
  id              BIGSERIAL PRIMARY KEY,
  occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  category        TEXT NOT NULL CHECK (category IN (
                    'auth','query','agent_call','rag_access',
                    'tool_call','security','fallback','config'
                  )),
  event           TEXT NOT NULL,          -- ex: 'login_success', 'rag_read'
  actor_type      TEXT NOT NULL CHECK (actor_type IN ('user','agent','system')),
  actor_id        TEXT,                   -- user_id, agent_name, 'system'
  tenant_id       TEXT,                   -- multi-tenant
  request_id      UUID,                   -- corrèle les événements d'une requête
  severity        TEXT NOT NULL DEFAULT 'info'
                    CHECK (severity IN ('debug','info','warning','error','critical')),
  payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
  payload_hash    TEXT NOT NULL,          -- SHA-256 hex de payload (intégrité ligne)
  prev_hash       TEXT,                   -- chaîne de hachage avec la ligne précédente
  row_hash        TEXT NOT NULL           -- SHA-256(id || prev_hash || payload_hash || occurred_at)
);

CREATE INDEX IF NOT EXISTS idx_audit_log_occurred_at ON audit.log (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_category    ON audit.log (category, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor       ON audit.log (actor_type, actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_request_id  ON audit.log (request_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_payload_gin ON audit.log USING gin (payload);

-- =========================================================================
-- Trigger : calcule prev_hash et row_hash automatiquement à l'INSERT
-- =========================================================================
CREATE OR REPLACE FUNCTION audit.compute_hashes()
RETURNS TRIGGER AS $$
DECLARE
  last_hash TEXT;
BEGIN
  -- payload_hash : intégrité du contenu de la ligne
  NEW.payload_hash := encode(digest(NEW.payload::text, 'sha256'), 'hex');

  -- prev_hash : récupère le row_hash de la dernière ligne insérée
  SELECT row_hash INTO last_hash
  FROM audit.log
  ORDER BY id DESC
  LIMIT 1;

  NEW.prev_hash := COALESCE(last_hash, 'GENESIS');

  -- row_hash : chaîne (id n'est pas encore connu, donc on chaîne sur le reste)
  NEW.row_hash := encode(
    digest(
      NEW.prev_hash || '|' || NEW.payload_hash || '|' || NEW.occurred_at::text,
      'sha256'
    ),
    'hex'
  );

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_compute_hashes ON audit.log;
CREATE TRIGGER trg_audit_compute_hashes
BEFORE INSERT ON audit.log
FOR EACH ROW EXECUTE FUNCTION audit.compute_hashes();

-- =========================================================================
-- Immutabilité : empêcher UPDATE et DELETE même pour le superuser applicatif
-- (le migrator peut toujours intervenir pour les ops, mais pas l'app)
-- =========================================================================
CREATE OR REPLACE FUNCTION audit.forbid_mutation()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'audit.log is append-only — % forbidden', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_no_update ON audit.log;
CREATE TRIGGER trg_audit_no_update
BEFORE UPDATE ON audit.log
FOR EACH ROW EXECUTE FUNCTION audit.forbid_mutation();

DROP TRIGGER IF EXISTS trg_audit_no_delete ON audit.log;
CREATE TRIGGER trg_audit_no_delete
BEFORE DELETE ON audit.log
FOR EACH ROW EXECUTE FUNCTION audit.forbid_mutation();

-- =========================================================================
-- Vue de vérification d'intégrité (à appeler périodiquement)
-- =========================================================================
CREATE OR REPLACE VIEW audit.integrity_check AS
SELECT
  cur.id,
  cur.occurred_at,
  cur.row_hash,
  cur.prev_hash,
  LAG(cur.row_hash) OVER (ORDER BY cur.id) AS expected_prev_hash,
  CASE
    WHEN cur.id = 1 THEN cur.prev_hash = 'GENESIS'
    ELSE cur.prev_hash = LAG(cur.row_hash) OVER (ORDER BY cur.id)
  END AS chain_ok
FROM audit.log cur;

GRANT SELECT ON audit.integrity_check TO zolaos_audit_reader;

RESET ROLE;
