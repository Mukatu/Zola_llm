# Authentification — passage en production

ZolaOS s'authentifie par **jeton** (JWT), et c'est le bon mécanisme : le jeton porte
l'identité de l'appelant, son **tenant** (clé de cloisonnement du corpus privé
`rag_tenant`) et ses scopes. Ce qui n'était **pas** prêt pour la production, c'était
la *façon d'obtenir* un jeton : jusqu'ici, seul l'endpoint de développement
`/v1/auth/dev-token` en émettait — il forge un jeton **sans vérifier d'identifiants**
et renvoie 404 hors dev. Un vrai utilisateur ne pouvait donc pas se connecter.

Ce document décrit l'authentification de production (login email + mot de passe,
cookies httpOnly) et les étapes de mise en service.

## Ce qui a été mis en place

- **Login réel** : `POST /v1/auth/login` vérifie email + mot de passe (bcrypt) et
  émet un access token JWT court + un refresh token opaque.
- **Cookies httpOnly** : `zo_access` et `zo_refresh` sont invisibles au JavaScript
  → un vol par XSS est impossible. `zo_csrf` (lisible) sert la protection CSRF.
- **CSRF double-submit** : les endpoints mutants d'auth exigent l'en-tête
  `X-CSRF-Token` égal au cookie `zo_csrf`. Couplé à `SameSite=lax`, il neutralise
  les requêtes forgées cross-site.
- **Refresh + rotation** : `POST /v1/auth/refresh` réémet un access token et
  **révoque** l'ancien refresh (défense anti-rejeu). `POST /v1/auth/logout` révoque
  et efface les cookies.
- **Anti-brute-force** : verrou temporaire après N échecs par (email + IP).
- **Réponse en temps constant** au login (pas d'énumération des comptes).
- Le frontend bascule **automatiquement** dev↔prod : en dev il s'auto-connecte via
  `dev-token` ; en prod (dev-token 404) un 401 renvoie vers `/login`.

## Étapes de mise en production

### 1. Secrets (obligatoire)

Générer des secrets forts et les servir **depuis un coffre** (pas depuis un `.env`
versionné) :

```
JWT_SECRET=$(openssl rand -hex 32)
API_KEY_PEPPER=$(openssl rand -hex 32)
```

⚠️ `JWT_SECRET` signe tous les jetons : il doit être **stable** (le régénérer
invalide toutes les sessions) et **secret**. Le partager entre instances d'un même
déploiement.

### 2. Environnement + HTTPS

```
APP_ENV=prod            # désactive dev-token (404), force les cookies Secure
CORS_ORIGINS=https://app.polaris.cg      # origine(s) réelle(s) du frontend, jamais *
```

Les cookies `Secure` exigent **HTTPS** : servir derrière Caddy/TLS (déjà dans
`docker-compose.yml`). En `prod`, `AUTH_COOKIE_SECURE` vaut True par défaut.

### 3. Migration de base

```
python -m alembic upgrade head     # crée core.refresh_tokens (rév. 0043)
```

### 4. Créer le premier administrateur

```
docker exec -it zolaos-app python scripts/create_admin.py \
    --email admin@polaris.cg --display-name "Admin Polaris" --tenant-id polaris
# mot de passe demandé de façon masquée (ou via ADMIN_PASSWORD)
```

Rejouer le script sur un email existant **réinitialise** son mot de passe.

## Limites connues / prochaines itérations

- **Scopes/RBAC** : le login émet des jetons **sans scope élevé** (least-privilege).
  La curation du communs (`commons:curate`) reste donc réservée — il faudra un
  modèle de rôles pour l'attribuer à des comptes précis.
- **Verrou anti-brute-force en mémoire** : mono-process (suffisant pour une Zolabox
  mono-instance) ; un backend Redis serait nécessaire en cluster multi-worker.
- **Gestion des comptes** : création/reset via script CLI. Une UI d'administration
  (inviter, désactiver, réinitialiser) est une itération ultérieure.
- **SSO/OIDC** : non couvert (choix « email + mot de passe »). L'architecture le
  permet en ajoutant un émetteur de jeton sans toucher au reste.
