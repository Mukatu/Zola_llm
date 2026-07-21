#!/bin/sh
# ============================================================================
# Installation d'une Zolabox sur le serveur d'un client. Idempotent.
#
# Prérequis : Docker + Docker Compose v2 ; un export du dépôt ZolaOS présent
# (le contexte de build pointe sur ../..). Provisioning fait côté Cortex
# (cockpit → fiche client → « Provisionner ») pour obtenir l'identité de la box.
#
# Usage : ./install.sh [email-admin]
# ============================================================================
set -eu
cd "$(dirname "$0")"

getenv() { grep "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- || true; }

# 1) .env
if [ ! -f .env ]; then
  cp .env.zolabox.example .env
  echo "→ .env créé depuis l'exemple."
  echo "  Renseigne l'identité de la box (fournie par le provisioning Cortex) puis relance :"
  echo "    ZOLAOS_BOX_TENANT_ID, ZOLAOS_BOX_CREDENTIAL, TUNNEL_CORTEX_URL, ZOLABOX_DOMAIN"
  exit 1
fi

# 2) identité de la box obligatoire
for v in ZOLAOS_BOX_TENANT_ID ZOLAOS_BOX_CREDENTIAL TUNNEL_CORTEX_URL ZOLABOX_DOMAIN; do
  [ -n "$(getenv "$v")" ] || { echo "✗ $v manquant dans .env (provisioning Cortex)"; exit 1; }
done

# 3) secrets AUTO (générés s'ils sont vides)
for v in JWT_SECRET API_KEY_PEPPER ENCRYPTION_KEY_AUDIT \
  POSTGRES_PASSWORD_MIGRATIONS POSTGRES_PASSWORD_APP POSTGRES_PASSWORD_HEALTH \
  POSTGRES_PASSWORD_LEGAL POSTGRES_PASSWORD_ERP POSTGRES_PASSWORD_CODE \
  POSTGRES_PASSWORD_AUDIT_W POSTGRES_PASSWORD_AUDIT_R REDIS_PASSWORD MINIO_ROOT_PASSWORD; do
  if [ -z "$(getenv "$v")" ]; then
    sed -i "s|^$v=.*|$v=$(openssl rand -hex 32)|" .env
    echo "  secret généré : $v"
  fi
done

DOMAIN="$(getenv ZOLABOX_DOMAIN)"
MODEL="$(getenv LLM_MODEL_BRIGADE)"; MODEL="${MODEL:-llama3:8b}"

# 4) build (profil box → strip des actifs propriétaires Polaris) + démarrage
echo "→ Build de l'image (profil box)…"
docker compose build
echo "→ Démarrage de la pile (Postgres init + migrations + services)…"
docker compose up -d

# 5) attendre Ollama puis télécharger le modèle 8B
echo "→ Attente d'Ollama…"
i=0; while [ $i -lt 30 ]; do docker compose exec -T ollama ollama list >/dev/null 2>&1 && break; i=$((i+1)); sleep 3; done
echo "→ Téléchargement du modèle $MODEL (peut être long au premier install)…"
docker compose exec -T ollama ollama pull "$MODEL"

# 6) attendre l'app puis créer l'admin
echo "→ Attente de l'application…"
i=0; while [ $i -lt 30 ]; do docker compose exec -T app curl -fsS http://localhost:8000/health >/dev/null 2>&1 && break; i=$((i+1)); sleep 3; done
ADMIN_EMAIL="${1:-admin@box.local}"
ADMIN_PW="$(openssl rand -base64 12)"
docker compose exec -T -e ADMIN_PASSWORD="$ADMIN_PW" app python scripts/create_admin.py --email "$ADMIN_EMAIL" --role admin

echo ""
echo "✓ Zolabox installée."
echo "  Accès       : https://$DOMAIN"
echo "  Admin       : $ADMIN_EMAIL"
echo "  Mot de passe: $ADMIN_PW   ← À NOTER (non réaffiché)"
echo ""
echo "  Corpus public : restaure le dump fourni par Polaris avec :"
echo "      ./seed_corpus.sh corpus_public.dump"
echo "  Le tunnel vers le Cortex démarre automatiquement (connexion sortante)."
