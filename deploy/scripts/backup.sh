#!/bin/sh
# ============================================================================
# Sauvegarde Postgres d'une instance ZolaOS (box ou cortex). À planifier en cron.
# Le conteneur Postgres est configurable ; rétention automatique.
#
#   PG_CONTAINER=zolabox-postgres   ./backup.sh /var/backups/zolabox 14
#   PG_CONTAINER=zolacortex-postgres ./backup.sh /var/backups/zolacortex 30
#
# Exemple cron (quotidien 02h30) :
#   30 2 * * * PG_CONTAINER=zolabox-postgres /opt/zolabox/deploy/scripts/backup.sh /var/backups/zolabox 14
# ============================================================================
set -eu
DEST="${1:-./backups}"
KEEP_DAYS="${2:-14}"
PG="${PG_CONTAINER:-zolabox-postgres}"
DB="${POSTGRES_DB:-zolaos}"

mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="$DEST/zolaos-$STAMP.sql.gz"

echo "→ Sauvegarde de $DB ($PG) → $FILE"
docker exec -e PGPASSWORD=postgres "$PG" pg_dump -U postgres -d "$DB" | gzip > "$FILE"

SIZE="$(wc -c < "$FILE")"
[ "$SIZE" -gt 1000 ] || { echo "✗ Sauvegarde suspicieusement petite ($SIZE o)"; exit 1; }
echo "✓ Sauvegarde OK ($(du -h "$FILE" 2>/dev/null | cut -f1))"

# Rétention : purge des sauvegardes plus vieilles que KEEP_DAYS.
find "$DEST" -maxdepth 1 -name 'zolaos-*.sql.gz' -mtime +"$KEEP_DAYS" -print -delete 2>/dev/null | \
  while read -r old; do echo "  purgé : $old"; done
echo "  rétention : $KEEP_DAYS jours"
