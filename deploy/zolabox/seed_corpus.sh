#!/bin/sh
# Restaure le corpus public V2.2 (dump fourni par Polaris) dans la Zolabox.
# Le dump est un pg_dump des schémas rag_* généré depuis une box de référence :
#   docker compose exec -T postgres pg_dump -U postgres -d zolaos \
#       -n 'rag_*' --data-only > corpus_public.dump
# Usage : ./seed_corpus.sh <fichier-dump>
set -eu
cd "$(dirname "$0")"
DUMP="${1:?Usage: ./seed_corpus.sh <fichier-dump>}"
[ -f "$DUMP" ] || { echo "Dump introuvable : $DUMP"; exit 1; }
DB="$(grep '^POSTGRES_DB=' .env 2>/dev/null | cut -d= -f2- || true)"; DB="${DB:-zolaos}"
echo "→ Restauration du corpus public dans Postgres ($DB)…"
docker compose exec -T postgres psql -U postgres -d "$DB" < "$DUMP"
echo "✓ Corpus restauré."
