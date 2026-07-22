# Exploitation — runbook (Phase 3)

Opérer les instances ZolaOS en production : sauvegardes, mises à jour, supervision,
révocation, incidents. Vaut pour la **box** (chez le client) et le **cortex** (Polaris).

## Sauvegardes

Sauvegarde Postgres (données relationnelles + vectorielles = source unique de vérité).

```sh
# ponctuel (conteneur configurable, rétention en jours)
PG_CONTAINER=zolabox-postgres   deploy/scripts/backup.sh /var/backups/zolabox 14
PG_CONTAINER=zolacortex-postgres deploy/scripts/backup.sh /var/backups/zolacortex 30

# cron quotidien (02h30)
30 2 * * * PG_CONTAINER=zolabox-postgres /opt/zolabox/deploy/scripts/backup.sh /var/backups/zolabox 14
```

**Restauration** :
```sh
gunzip -c /var/backups/zolabox/zolaos-AAAAMMJJ-HHMMSS.sql.gz \
  | docker exec -i zolabox-postgres psql -U postgres -d zolaos
```
Volumes persistants à sauvegarder aussi si besoin : `*_minio_data`, `*_ollama_data`.

## Mises à jour

```sh
cd deploy/zolabox        # ou zolacortex
../scripts/update.sh     # sauvegarde → git pull → build → up (migrations auto) 
./verify.sh
```
- **Logiciel** : `update.sh` (pull + rebuild). Rollback = restaurer la sauvegarde pré-update
  (`backups/pre-update-*.sql.gz`) et revenir au commit précédent.
- **Corpus** (box) : Polaris publie un nouveau dump → `./seed_corpus.sh corpus_public.dump`.
- **Fleet** : aujourd'hui la mise à jour est **par instance** (opérateur). Une distribution
  poussée vers N box (via un canal signé) est une évolution — cf. « À faire ».

## Supervision

Opt-in, dans chaque bundle :
```sh
cd deploy/zolacortex
docker compose --profile monitoring up -d prometheus grafana
```
- **Grafana** : `http://<hôte>:3001` (admin / `GF_ADMIN_PASSWORD`). Dashboard **« ZolaOS —
  Vue d'ensemble »** provisionné automatiquement (santé, erreurs 5xx, souveraineté, HTTP,
  LLM, RAG, agents).
- **Prometheus** : `:9090`. Règles d'alerte (`infra/prometheus/alerts.yml`) :
  | Alerte | Sens | Réaction |
  |---|---|---|
  | `InstanceDown` | app injoignable 2 min | logs, redémarrer |
  | `HighHttpErrorRate` | 5xx > 5 % | logs applicatifs |
  | `ExternalFallbackBlocked` | appel LLM externe bloqué | vérifier la config (le local doit suffire) |
  | `LlmLatencyHigh` | p95 LLM > 60 s | GPU / charge |
- **Notifications** : brancher un Alertmanager sur Prometheus (non fourni — cible SMTP/Slack
  selon Polaris).

## Révocation d'une box

Deux niveaux (défense en profondeur) :
1. **Credential (immédiat)** — cockpit → fiche client → **Révoquer**. Coupe le tunnel vivant
   et bloque toute reconnexion. **C'est le contrôle de première ligne.**
2. **Certificat mTLS** — retirer le certificat client de la box ; pour l'invalider côté CA,
   une **CRL / rotation de CA** est nécessaire (à outiller — cf. « À faire »). En pratique,
   la révocation du credential suffit à couper l'accès immédiatement.

## Incidents fréquents

| Symptôme | Diagnostic | Action |
|---|---|---|
| Assistant / audit muet | Ollama down | relancer le service `ollama` (box/cortex) |
| Tunnel déconnecté | credential/cert, ou réseau sortant | cockpit (rejet ?), pare-feu client, `docker compose logs app` |
| Erreurs 5xx | DB/Redis/MinIO | `docker compose ps`, healthchecks, logs |
| Corruption données | — | restaurer la dernière sauvegarde |

## À faire (durcissement exploitation)

- Distribution poussée des mises à jour vers N box (canal signé).
- CRL / rotation de CA pour la révocation de certificat.
- Alertmanager (notifications) + exporters système (node_exporter) si besoin.
