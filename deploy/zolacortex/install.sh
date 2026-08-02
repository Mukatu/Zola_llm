#!/bin/sh
# ============================================================================
# Installation du cortex Polaris (Zolacortex). Idempotent.
# Prérequis : Docker + Compose v2, openssl, GPU recommandé (70B), export du dépôt.
# Usage : ./install.sh [email-admin]
# ============================================================================
set -eu
cd "$(dirname "$0")"

# Lit une variable du .env. Retire un éventuel commentaire inline (« valeur # note »)
# et les espaces de fin : Docker Compose ne les retire pas, la détection doit être sûre.
getenv() { grep "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]][[:space:]]*#.*$//;s/[[:space:]]*$//' || true; }

if [ ! -f .env ]; then
  cp .env.zolacortex.example .env
  echo "→ .env créé. Renseigne CORTEX_DOMAIN et CORTEX_TUNNEL_DOMAIN, puis relance."
  exit 1
fi
for v in CORTEX_DOMAIN CORTEX_TUNNEL_DOMAIN; do
  [ -n "$(getenv "$v")" ] || { echo "✗ $v manquant dans .env"; exit 1; }
done

for v in JWT_SECRET API_KEY_PEPPER ENCRYPTION_KEY_AUDIT \
  POSTGRES_PASSWORD_MIGRATIONS POSTGRES_PASSWORD_APP POSTGRES_PASSWORD_HEALTH \
  POSTGRES_PASSWORD_LEGAL POSTGRES_PASSWORD_ERP POSTGRES_PASSWORD_CODE \
  POSTGRES_PASSWORD_AUDIT_W POSTGRES_PASSWORD_AUDIT_R REDIS_PASSWORD MINIO_ROOT_PASSWORD \
  GF_ADMIN_PASSWORD; do
  [ -z "$(getenv "$v")" ] && sed -i "s|^$v=.*|$v=$(openssl rand -hex 32)|" .env && echo "  secret généré : $v" || true
done

# CA Polaris (une fois) — indispensable au mTLS du tunnel.
if [ ! -f pki/certs/polaris-ca.crt ]; then
  echo "→ Aucune CA Polaris : elle sera créée à la première émission de certificat."
  echo "  (Après l'install : ./pki/issue_box_cert.sh <tenant_id> pour chaque box.)"
fi

ROUTER="$(getenv LLM_MODEL_BRIGADE)"; ROUTER="${ROUTER:-llama3:8b}"
CORE="$(getenv LLM_MODEL_CORE)"; CORE="${CORE:-llama3:70b}"

echo "→ Build de l'image cortex (overlays conservés)…"
docker compose build
echo "→ Démarrage de la pile…"
docker compose up -d

echo "→ Attente d'Ollama…"
i=0; while [ $i -lt 30 ]; do docker compose exec -T ollama ollama list >/dev/null 2>&1 && break; i=$((i+1)); sleep 3; done
echo "→ Téléchargement des modèles ($ROUTER puis $CORE — le 70B est long)…"
docker compose exec -T ollama ollama pull "$ROUTER"
docker compose exec -T ollama ollama pull "$CORE"

echo "→ Attente de l'application…"
i=0; while [ $i -lt 30 ]; do docker compose exec -T app curl -fsS http://localhost:8000/health >/dev/null 2>&1 && break; i=$((i+1)); sleep 3; done
ADMIN_EMAIL="${1:-admin@polaris.cg}"
ADMIN_PW="$(openssl rand -base64 12)"
docker compose exec -T -e ADMIN_PASSWORD="$ADMIN_PW" app python scripts/create_admin.py --email "$ADMIN_EMAIL" --role admin

echo ""
echo "✓ Zolacortex installé."
echo "  Cockpit : https://$(getenv CORTEX_DOMAIN)"
echo "  Tunnel  : wss://$(getenv CORTEX_TUNNEL_DOMAIN)/v1/tunnel/connect (mTLS)"
echo "  Admin   : $ADMIN_EMAIL  /  $ADMIN_PW   ← À NOTER"
echo ""
echo "  Pour chaque box : ./pki/issue_box_cert.sh <tenant_id>, puis provisionner le"
echo "  credential au cockpit et configurer la box (cert client + credential + URL tunnel)."
