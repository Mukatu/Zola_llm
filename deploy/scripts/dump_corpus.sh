#!/bin/sh
# ============================================================================
# Génère le dump du corpus PUBLIC de référence (schémas rag_* SAUF rag_tenant,
# qui est le corpus privé par client). Ce dump amorce une nouvelle Zolabox via
# `deploy/zolabox/seed_corpus.sh corpus_public.dump`.
#
# À exécuter depuis une box/cortex de RÉFÉRENCE (corpus déjà ingéré).
# Le conteneur Postgres est configurable :
#   PG_CONTAINER=zolaos-postgres ./dump_corpus.sh corpus_public.dump   # depuis le dev
#   PG_CONTAINER=zolabox-postgres ./dump_corpus.sh                     # depuis une box
#
# ⚠️ Le dump est un ARTEFACT DE RELEASE (volumineux, embeddings) — ne pas versionner.
# ============================================================================
set -eu
OUT="${1:-corpus_public.dump}"
PG="${PG_CONTAINER:-zolabox-postgres}"
DB="${POSTGRES_DB:-zolaos}"

echo "→ Export du corpus public (rag_* sauf rag_tenant) depuis $PG…"
docker exec -e PGPASSWORD=postgres "$PG" \
  pg_dump -U postgres -d "$DB" --data-only -n 'rag_*' -N rag_tenant > "$OUT"

SIZE=$(wc -c < "$OUT")
echo "✓ Dump généré : $OUT ($SIZE octets)"
[ "$SIZE" -gt 1000 ] || echo "  ⚠️ Dump suspicieusement petit — le corpus est-il ingéré côté source ?"
