# Zolabox — appliance client (bundle Docker Compose)

Installe une **Zolabox** sur le serveur d'un client, dans le modèle **hybride** :
les données du client restent sur son serveur ; le modèle lourd (70B) et les prompts
cabinet restent au **Cortex** (chez Polaris) ; la box ouvre un **tunnel sortant** vers
le Cortex (aucun port entrant à ouvrir côté client).

## Contenu de la box

App (profil `box`) + Postgres/pgvector + Redis + MinIO + **Ollama (8B local)** + Caddy
(HTTPS). L'image est bâtie en profil box : **les actifs propriétaires Polaris sont
retirés** au build (`strip_polaris_assets.sh`). Le 70B n'est **pas** sur la box.

## Prérequis (serveur client)

- Linux avec **Docker** + **Docker Compose v2**, `openssl`, `git`.
- Un export du dépôt ZolaOS (le build pointe sur `../..`).
- Matériel : le 8B tourne sur GPU d'entrée/milieu de gamme ou APU à mémoire unifiée ;
  CPU seul fonctionne mais lentement. (Pour activer le GPU : bloc `deploy` du service
  `ollama` dans `docker-compose.yml`.)

## Installation (côté Polaris / installateur)

1. **Provisionner la box au Cortex** : cockpit Zolacortex → fiche du client →
   « Provisionner le credential ». Noter `ZOLAOS_BOX_TENANT_ID`, `ZOLAOS_BOX_CREDENTIAL`
   (affiché une fois) et l'URL du tunnel.
2. Sur le serveur client :
   ```sh
   cd deploy/zolabox
   cp .env.zolabox.example .env
   # renseigner : ZOLAOS_BOX_TENANT_ID, ZOLAOS_BOX_CREDENTIAL, TUNNEL_CORTEX_URL, ZOLABOX_DOMAIN
   ./install.sh admin@le-client.cg
   ```
   `install.sh` génère les secrets manquants, bâtit l'image (profil box), démarre la
   pile, télécharge le 8B, applique les migrations et crée le compte admin
   (mot de passe affiché une fois).
3. **Charger le corpus public** (dump fourni par Polaris) :
   ```sh
   ./seed_corpus.sh corpus_public.dump
   ```

Le tunnel vers le Cortex démarre seul (connexion sortante). Vérifier côté Cortex que
la box apparaît connectée (`tunnel.box_connected`).

## Côté client (utilisateur final)

Ouvrir `https://<ZOLABOX_DOMAIN>`, se connecter (compte fourni par l'admin), utiliser
l'assistant et les modules sur ses données. **Aucune manipulation technique.**

## Exploitation

- **Mise à jour** : `git pull` de l'export, puis `docker compose build && docker compose up -d`
  (les migrations rejouent via le service `migrate`).
- **Sauvegarde Postgres** : `docker compose exec -T postgres pg_dump -U postgres zolaos > backup_$(date +%F).sql`
  (à planifier en cron). Volumes persistants : `postgres_data`, `minio_data`, `ollama_data`.
- **Révocation** : depuis le Cortex, « Révoquer » le credential → la box est coupée
  immédiatement et ne peut plus se reconnecter.
- **Rotation du credential** : « Provisionner » à nouveau au Cortex, mettre à jour
  `ZOLAOS_BOX_CREDENTIAL` dans `.env`, `docker compose up -d app`.

## Sécurité

- `APP_ENV=prod` : dev-token désactivé (404), cookies `Secure` (HTTPS obligatoire).
- Le credential de box est **par box**, révocable. En production, faire aussi passer
  le tunnel en `wss://` avec mTLS terminé au reverse-proxy du Cortex (cf.
  `docs/PRODUCTION_HYBRID.md`).
- Ne jamais versionner le `.env` rempli.

## Limite testée

Le bundle est validé au niveau **configuration** (schéma compose). Un test d'installation
de bout en bout se fait sur un serveur Linux cible (phase pilote).
