# Pilote — première mise en production hybride (Zolacortex + Zolabox)

Objectif : **installer et valider pour de vrai** les deux faces sur des serveurs Linux,
et dérouler une mission de bout en bout. C'est l'étape qui révèle ce que la validation
de configuration ne voit pas.

## Pré-vol (checklist)

**Serveur Cortex (Polaris)** — cockpit + 70B :
- [ ] Linux, Docker + Compose v2, `openssl`, **GPU** (70B), disque ≥ 100 Go.
- [ ] Deux domaines résolvant vers ce serveur : `CORTEX_DOMAIN`, `CORTEX_TUNNEL_DOMAIN`.
- [ ] Ports 80/443 ouverts en entrée.
- [ ] Export du dépôt ZolaOS présent (contexte de build).

**Serveur Box (client ou VM de test)** — assistant + 8B :
- [ ] Linux, Docker + Compose v2, `openssl`, GPU/APU conseillé.
- [ ] Accès **sortant** vers `https://CORTEX_TUNNEL_DOMAIN:443` (le tunnel est sortant ;
      aucun port entrant requis, hormis l'accès web local des utilisateurs).
- [ ] Export du dépôt + le dump corpus (`corpus_public.dump`, généré par
      `deploy/scripts/dump_corpus.sh` depuis une source de référence).

## Séquence

### 1. Cortex (d'abord)
```sh
cd deploy/zolacortex
cp .env.zolacortex.example .env   # renseigner CORTEX_DOMAIN, CORTEX_TUNNEL_DOMAIN
./install.sh admin@polaris.cg
./verify.sh
```
Noter le mot de passe admin. Se connecter au cockpit `https://CORTEX_DOMAIN`.

### 2. Provisionner le client pilote (au cockpit)
- Créer le tenant **cabinet** (Polaris) et le tenant **client** (annuaire Clients).
- Fiche client → **Provisionner le credential** → noter `credential` + `tenant_id`.
- Émettre le certificat client : `./pki/issue_box_cert.sh <tenant_id>` (crée aussi la CA).
  Récupérer `pki/certs/box_<tenant_id>.crt|.key`.

### 3. Box (chez le client / VM de test)
```sh
cd deploy/zolabox
cp .env.zolabox.example .env
# renseigner : ZOLAOS_BOX_TENANT_ID, ZOLAOS_BOX_CREDENTIAL,
#   TUNNEL_CORTEX_URL=wss://CORTEX_TUNNEL_DOMAIN/v1/tunnel/connect, ZOLABOX_DOMAIN,
#   TUNNEL_CLIENT_CERT_PATH=/certs/box.crt, TUNNEL_CLIENT_KEY_PATH=/certs/box.key
# (déposer box_<id>.crt/.key sur la box, monter le dossier /certs)
./install.sh admin@le-client.cg
./seed_corpus.sh corpus_public.dump
./verify.sh
```

### 4. Confirmer le tunnel
- Cortex : `docker compose logs app | grep tunnel.box_connected` (le tenant du client).
- Aucun `tunnel.reject` (sinon : credential ou certificat, cf. dépannage).

### 5. Mission de bout en bout
- Cockpit → créer une mission pour le client (offre `conformite_rh`, scope
  `country:cg,module:travail_cg`).
- Ouvrir la mission → **Lancer l'audit** avec une requête ciblée. Attendu : badge
  **« Données client (tunnel sécurisé) »** (`remote_box_tunnel`), findings + citations.
- **Générer le rapport** → le `.docx` se télécharge.

## Critères de succès

- [ ] `verify.sh` OK des deux côtés.
- [ ] Un utilisateur du client se connecte à `https://ZOLABOX_DOMAIN` et l'assistant cite ses sources.
- [ ] Le tunnel apparaît connecté au Cortex (mTLS + credential).
- [ ] Audit `remote_box_tunnel` + rapport `.docx` produits.
- [ ] `dev-token` en 404 des deux côtés (prod).

## Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| Tunnel `bad_credential` | credential erroné/révoqué | re-provisionner au cockpit, MAJ `.env`, `up -d app` |
| Tunnel `client_cert_mismatch` | CN du cert ≠ tenant, ou CA absente | ré-émettre le cert (CN=tenant_id), vérifier `polaris-ca.crt` dans Caddy |
| Tunnel ne se connecte pas | sortant 443 bloqué, mauvais domaine | vérifier le pare-feu client, `TUNNEL_CORTEX_URL` |
| Audit `insufficient_context` | requête trop générique | requête ciblée (garde-fou d'abstention, comportement voulu) |
| Audit lent | pas de GPU | activer le bloc `deploy` GPU d'ollama |
| Corpus vide | dump non restauré | `./seed_corpus.sh corpus_public.dump` |

## Rollback / teardown

- Retirer une box : cockpit → **Révoquer** le credential (coupe le tunnel immédiatement).
- Arrêter/supprimer une pile : `docker compose down` (ajouter `-v` pour effacer les données).
- Sauvegarde avant toute manip : `docker compose exec -T postgres pg_dump -U postgres zolaos > backup.sql`.
