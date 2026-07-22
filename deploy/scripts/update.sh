#!/bin/sh
# ============================================================================
# Met à jour l'instance ZolaOS du dossier COURANT. À lancer depuis un bundle :
#   cd deploy/zolabox   && ../scripts/update.sh
#   cd deploy/zolacortex && ../scripts/update.sh
# Sauvegarde d'abord, puis git pull + rebuild + migrations (service `migrate`).
# ============================================================================
set -eu
[ -f docker-compose.yml ] || { echo "✗ Lancer depuis un dossier de bundle (deploy/zolabox|zolacortex)."; exit 1; }
DB="$(grep '^POSTGRES_DB=' .env 2>/dev/null | cut -d= -f2- || true)"; DB="${DB:-zolaos}"

echo "→ Sauvegarde préalable…"
mkdir -p backups
docker compose exec -T postgres pg_dump -U postgres -d "$DB" | gzip > "backups/pre-update-$(date +%Y%m%d-%H%M%S).sql.gz"
echo "  ✓ sauvegarde faite (backups/)."

echo "→ Récupération du code (git pull --ff-only)…"
git -C ../.. pull --ff-only

echo "→ Rebuild + redémarrage (migrations rejouées par le service migrate)…"
docker compose build
docker compose up -d

echo "✓ Mise à jour appliquée. Contrôle : ./verify.sh"
echo "  (Corpus : si un nouveau dump est fourni, ./seed_corpus.sh <dump> — box uniquement.)"
