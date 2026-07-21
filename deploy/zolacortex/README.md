# Zolacortex — cortex de production (chez Polaris)

Le côté **cabinet** du déploiement hybride : cockpit (comptes / clients / missions),
modèle **70B** et overlays propriétaires, et le **point d'entrée des tunnels** des
Zolabox. L'image conserve les actifs cabinet (pas de strip). Reçoit les connexions
**sortantes** des box en **mTLS** (certificat client par box).

## Pile

app (profil `cortex`) + Postgres/pgvector + Redis + MinIO + Ollama (**8B + 70B**) +
Caddy (HTTPS cockpit + **mTLS** sur le tunnel).

## Prérequis

- Serveur Linux Polaris avec Docker + Compose v2, `openssl`, **GPU** (le 70B l'exige
  en pratique), un export du dépôt ZolaOS.
- Deux domaines : `CORTEX_DOMAIN` (cockpit) et `CORTEX_TUNNEL_DOMAIN` (tunnel).

## Installation

```sh
cd deploy/zolacortex
cp .env.zolacortex.example .env
# renseigner CORTEX_DOMAIN et CORTEX_TUNNEL_DOMAIN
./install.sh admin@polaris.cg
```

`install.sh` génère les secrets, bâtit l'image (overlays conservés), démarre la pile,
télécharge le 8B puis le 70B, applique les migrations et crée l'admin.

## Sécurité du tunnel — deux couches

1. **Transport (mTLS, Caddy)** : chaque box présente un **certificat client** signé par
   la **CA Polaris** ; Caddy le vérifie (`require_and_verify`) et transmet le sujet à
   l'app (`X-Client-Cert-CN`). PKI :
   ```sh
   ./pki/issue_box_cert.sh <tenant_id>   # crée la CA au 1er appel, émet le cert de la box
   ```
   Déployer `pki/certs/box_<id>.crt|.key` sur la box (`TUNNEL_CLIENT_CERT_PATH/KEY`).
   `pki/certs/polaris-ca.crt` est monté dans Caddy (déjà câblé dans le compose).
2. **Application (credential par box)** : `TUNNEL_REQUIRE_CLIENT_CERT=true` — l'app
   vérifie que le CN du certificat == tenant, ET que le credential (cockpit → « Provisionner »)
   est valide. Révocation immédiate depuis le cockpit.

## Provisionner une box (bout en bout)

1. Cockpit → fiche client → **Provisionner le credential** (noter le secret).
2. `./pki/issue_box_cert.sh <tenant_id>` → certificat client de la box.
3. Sur la box : renseigner `ZOLAOS_BOX_CREDENTIAL`, `TUNNEL_CLIENT_CERT_PATH/KEY`,
   `TUNNEL_CORTEX_URL=wss://<CORTEX_TUNNEL_DOMAIN>/v1/tunnel/connect`, puis `./install.sh`.

## Exploitation

- **Révoquer une box** : cockpit → « Révoquer » (coupe le tunnel immédiatement). Pour
  invalider aussi le certificat : le retirer / roulement de CA (CRL — évolution).
- **Sauvegarde**, **mise à jour** : cf. `deploy/zolabox/README.md` (même principe).

## Limite testée

Bundle validé au niveau **configuration** (compose) ; la PKI est vérifiée
(`openssl verify` OK). La chaîne mTLS complète (Caddy `client_auth` + présentation du
cert par la box) se valide au déploiement sur les serveurs réels (phase pilote).
