#!/usr/bin/env bash
# Bootstrap exécuté automatiquement par l'image pgvector au premier démarrage.
# Injecte les mots de passe depuis les variables d'environnement et joue
# les scripts de schémas + audit log.
set -euo pipefail

PSQL=(psql -v ON_ERROR_STOP=1 --username "postgres" --dbname "${POSTGRES_DB}")

echo "[zolaos-init] Application de 01_init_schemas.sql"
"${PSQL[@]}" \
  -v "pwd_migrator=${PWD_MIGRATOR}" \
  -v "pwd_app=${PWD_APP}" \
  -v "pwd_health=${PWD_HEALTH}" \
  -v "pwd_legal=${PWD_LEGAL}" \
  -v "pwd_erp=${PWD_ERP}" \
  -v "pwd_code=${PWD_CODE}" \
  -v "pwd_audit_w=${PWD_AUDIT_W}" \
  -v "pwd_audit_r=${PWD_AUDIT_R}" \
  -f /infra/01_init_schemas.sql

echo "[zolaos-init] Application de 02_audit_log.sql"
"${PSQL[@]}" -f /infra/02_audit_log.sql

echo "[zolaos-init] Initialisation terminée."
