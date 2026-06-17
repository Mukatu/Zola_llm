# Inventaire et rotation des secrets

Ce dossier est **ignoré par git** (sauf ce README). Il sert à conserver localement les secrets de production et la traçabilité de leur rotation.

## Conventions

- Aucun secret n'est jamais committé.
- Tous les secrets sont générés via `python scripts/gen_secrets.py` (à venir Phase 1).
- Rotation maximale : **90 jours**.

## Inventaire local (à maintenir manuellement)

| Secret                          | Émis le      | Rotation prévue | Détenteur       |
|---------------------------------|--------------|-----------------|-----------------|
| POSTGRES_PASSWORD_APP           | YYYY-MM-DD   | YYYY-MM-DD      |                 |
| POSTGRES_PASSWORD_MIGRATIONS    | YYYY-MM-DD   | YYYY-MM-DD      |                 |
| JWT_SECRET                      | YYYY-MM-DD   | YYYY-MM-DD      |                 |
| API_KEY_PEPPER                  | YYYY-MM-DD   | YYYY-MM-DD      |                 |
| ENCRYPTION_KEY_AUDIT            | YYYY-MM-DD   | YYYY-MM-DD      |                 |
| MINIO_ROOT_PASSWORD             | YYYY-MM-DD   | YYYY-MM-DD      |                 |

## Procédure de rotation

1. Générer la nouvelle valeur : `openssl rand -hex 32` (ou via le script).
2. Mettre à jour `.env.prod` chiffré sur le serveur.
3. Redémarrer le service concerné via `docker compose up -d --no-deps <service>`.
4. Vérifier les logs.
5. Mettre à jour la ligne dans le tableau ci-dessus.

## Migration Phase 4+

Au passage en multi-environnement, ce fichier sera remplacé par **HashiCorp Vault** ou **Doppler self-hosted**.
