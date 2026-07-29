# Licence commerciale — entitlement de modules

## Le problème résolu

Avant ce mécanisme, la distribution des modules vendus par Polaris reposait sur un
champ `modules_actifs` **cosmétique** : il n'avait aucune conséquence côté serveur, il
ne faisait qu'orienter l'affichage. Concrètement, cela voulait dire :

1. Tous les endpoints métier (`/v1/erp`, `/v1/cyber`, `/v1/fintech`, …) restaient
   **montés et accessibles**, quel que soit le contrat commercial du client.
2. Le champ était **éditable par le client** via `PUT /v1/config` — un client pouvait
   littéralement s'auto-accorder les modules qu'il n'a pas payés.
3. Rien n'était **persisté** de façon fiable ni **signé** : aucune preuve d'origine.
4. Polaris (le vendeur) n'avait donc **aucun contrôle réel** sur ce qui est vendu vs.
   ce qui est exposé sur la box du client.

Le nouveau mécanisme (`src/zolaos/licensing/entitlement.py`) remplace ce champ
cosmétique par un **grant signé cryptographiquement**, vérifié et appliqué au
**montage même** des routers FastAPI.

## Modèle HYBRIDE : tier + options à la carte

Un entitlement (`Entitlement`) porte :

- `tenant_id` : le client concerné.
- `tier` : le bundle de base souscrit.
- `modules` : des modules **optionnels**, achetés à la carte **en plus** du tier.
- `license_id`, `issued_at`, `expires_at` : traçabilité + validité temporelle.

`effective_modules()` = `TIERS[tier] ∪ modules`, **borné** au catalogue `MODULES`
(un tier inconnu retombe sur l'ensemble vide, une option hors catalogue est
silencieusement ignorée — jamais d'élévation par un nom de module fantôme).

### Catalogue des modules vendables (`MODULES`)

```
erp · sirh · bi · crm · marketing · fintech · cyber · grc · code
```

Chaque nom correspond à un ou plusieurs routers montés dans `api/main.py` (ex. le
module `sirh` couvre à la fois `hr.py`, `gpec.py`, `recrutement.py`, `formation.py`
et `evaluation.py`).

### Table tiers → modules (`TIERS`)

| Tier       | Modules inclus                                    |
|------------|----------------------------------------------------|
| `starter`  | `erp`                                               |
| `business` | `erp`, `sirh`, `bi`, `crm`, `marketing`              |
| `full`     | tous les modules du catalogue (`MODULES`)           |

Exemple : un client `business` qui achète en plus la cybersécurité obtient
`{erp, sirh, bi, crm, marketing} ∪ {cyber}`.

## Infalsifiabilité : RS256 asymétrique

La signature utilise **RS256** (RSA), un algorithme **asymétrique** :

- La clé **PRIVÉE** signe (`sign_entitlement`) — elle ne vit **que** chez Polaris
  (poste/service d'émission, futur cockpit cortex).
- La clé **PUBLIQUE** vérifie (`verify_entitlement`) — c'est la **seule** chose
  déployée sur une Zolabox (`ENTITLEMENT_PUBLIC_KEY`).

Une box ne peut donc **ni forger, ni modifier, ni s'auto-accorder** un module : une
clé publique ne peut pas produire de signature RS256 valide, et toute altération du
jeton (même d'un seul caractère) invalide la signature. Preuve testée dans
`tests/test_entitlement.py` (`test_token_signed_by_a_different_private_key_is_invalid`,
`test_tampered_token_is_invalid`).

## Application AU MONTAGE, pas en façade

Contrairement à l'ancien `modules_actifs`, l'entitlement n'est pas un simple filtre
d'affichage : dans `api/main.py` (profil `box`), chaque router vertical est monté
**conditionnellement** :

```python
entitled = resolve_box_modules(settings)

def _mount_module(router, module):
    if entitled is None or module in entitled:
        app.include_router(router, dependencies=_box_auth)
```

Un module non couvert par la licence n'est **jamais monté** : ses routes n'existent
pas dans l'application FastAPI, elles renvoient **404** et n'apparaissent même pas
dans le schéma OpenAPI (`app.openapi()["paths"]`). Ce n'est pas un contrôle d'accès
appliqué après coup — le code du module n'est tout simplement pas exposé.
Vérifié par introspection OpenAPI, sans réseau/DB, dans
`tests/test_entitlement_mount.py` (même méthode que `tests/test_engine_profile.py`).

Le router `box.py` (`/v1/box/*`, plan de mission du tunnel Zero Trust) n'est **pas**
un module vendable : il reste toujours monté, son accès est gouverné par le JWT de
mission, pas par l'entitlement.

## Enforcement OPT-IN

`Settings.ENTITLEMENT_ENFORCED` (défaut `False`) contrôle l'activation :

- **`False`** (dev/tests, comportement actuel inchangé) : `resolve_box_modules`
  renvoie `None` → tous les modules sont montés, comme avant ce mécanisme.
- **`True`** (prod, box livrée à un client) : un entitlement absent, illisible ou
  **expiré** renvoie `frozenset()` — **fail-closed** : aucun module vertical n'est
  monté plutôt qu'un accès par défaut. Aucune licence valide ne se traduit jamais par
  un accès permissif.

## Livraison de la licence sur la box

Deux mécanismes, non exclusifs (le jeton inline est prioritaire) :

- **`ENTITLEMENT_LICENSE_JWT`** : le jeton signé déposé directement en variable
  d'environnement (secret).
- **`ENTITLEMENT_LICENSE_FILE`** : chemin vers un fichier contenant le jeton signé
  (pratique pour un refresh périodique déposé par un agent/tunnel sans redémarrer
  avec un nouvel environnement).

Dans les deux cas, `ENTITLEMENT_PUBLIC_KEY` (PEM de la clé publique Polaris) doit
être présent pour que la vérification soit possible.

## Mode opératoire

### 1. Générer la paire de clés (une fois, côté Polaris)

```
python scripts/gen_entitlement_keys.py \
    --out-private polaris_entitlement_private.pem \
    --out-public  polaris_entitlement_public.pem
```

La clé **privée** reste dans un coffre Polaris (jamais copiée sur une box, jamais
versionnée). La clé **publique** est ce qui part vers les box clientes.

### 2. Émettre une licence pour un tenant

```
python scripts/issue_license.py \
    --tenant-id acme-sarl \
    --tier business \
    --module cyber \
    --days 365 \
    --private-key-file polaris_entitlement_private.pem
```

Le script imprime le JWT signé ainsi que `effective_modules` (pour vérification
visuelle avant livraison). Répéter `--module` pour plusieurs options à la carte.

### 3. Déployer sur la box du client

Sur la Zolabox du client, poser dans l'environnement (ou le coffre de secrets qui
l'alimente) :

```
ENTITLEMENT_ENFORCED=true
ENTITLEMENT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
ENTITLEMENT_LICENSE_JWT="eyJhbGciOiJSUzI1NiIs..."
```

(ou `ENTITLEMENT_LICENSE_FILE=/etc/zolaos/license.jwt` avec le jeton déposé dans ce
fichier). Redémarrer l'application : `resolve_box_modules` recalcule le montage au
démarrage.

## Suivis (hors périmètre de cette livraison)

- **Refresh/révocation via le tunnel cortex** : aujourd'hui la licence est un fichier
  ou une variable d'environnement statique déposée manuellement. À terme, le tunnel
  Zolabox → Zolacortex (déjà utilisé pour le RAG distant Zero Trust) devrait pouvoir
  pousser un renouvellement de licence (et une révocation immédiate) sans intervention
  manuelle sur la box.
- **Cockpit cortex pour gérer les entitlements par tenant** : `scripts/issue_license.py`
  est un outil de ligne de commande pour l'amorçage ; une UI cortex (liste des
  tenants, tiers/options, dates d'expiration, ré-émission) manque encore.
- **Synchroniser l'affichage de `GET /v1/config` sur l'entitlement réel** : le champ
  `modules_actifs` existant dans la config reste aujourd'hui déclaratif côté box ; il
  faudrait le faire refléter `resolve_box_modules(settings)` pour que l'UI n'affiche
  jamais un module que le serveur n'expose pas.
- **RBAC sur `PUT /v1/config`** : `modules_actifs` a déjà été retiré du modèle
  `ConfigUpdate` (un client ne peut plus se l'auto-octroyer, cf. `api/v1/config.py`) ;
  il reste que l'édition des autres champs de personnalisation (branding, langue,
  connecteurs actifs, champs personnalisés) n'est aujourd'hui restreinte par aucun
  rôle RBAC — à réserver à un rôle admin/consultant.
