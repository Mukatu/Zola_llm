# Production — déploiement hybride (Zolabox sur site + Zolacortex chez Polaris)

Décidé 2026-07-20. Modèle **hybride** : la Zolabox tourne sur le serveur de chaque
client (données sur site) ; le Zolacortex tourne chez Polaris (cockpit cabinet,
modèle lourd 70B, overlays propriétaires). Connectivité par **tunnel sortant** :
la box appelle Polaris, aucun port ouvert côté client.

Ce document est la référence du chantier « prod ». Il ne s'agit plus de code
fonctionnel (l'app marche) mais d'**empaquetage et d'exploitation**.

## Qui fait quoi

| | Le client | Polaris |
|---|---|---|
| Matériel | Fournit **un serveur** (tier 8B, cf. specs) | Héberge le cortex + 70B |
| Installation | Rien (Polaris/installateur pose la Zolabox) | Provisionne chaque Zolabox |
| Usage courant | Navigateur → login → assistant + modules sur SES données | Opère le cortex, lance les missions |
| Pendant une mission | Sa box est allumée, corpus à jour — rien d'autre | Tire les extraits du client via tunnel, analyse chez Polaris, produit le rapport |

**Le client ne touche jamais à Docker, Ollama, un terminal.** S'il doit taper une
commande, le produit a échoué.

## Flux d'une mission (Zero Trust)

1. La Zolabox démarre → son **agent tunnel** ouvre une connexion sécurisée SORTANTE
   vers le cortex et s'authentifie (identité de box émise au provisioning). Le
   cortex enregistre « le tenant X est joignable sur ce canal ».
2. Un consultant crée une mission pour X → un **jeton de mission éphémère** est émis
   (TTL court, périmètre = `scope_tags`).
3. Le cortex envoie la requête RAG (`/v1/box/rag/search` + jeton) **dans le tunnel**
   du tenant X. La box valide le jeton (`verify_mission_token`), renvoie les extraits
   (lecture seule, bornée au scope). Aucune écriture, aucune inférence côté box.
4. L'analyse (overlay Polaris + 70B) tourne **chez Polaris**. Le prompt cabinet ne
   traverse jamais le réseau. Le rapport `.docx` sort côté cabinet.

Garantie : le prompt propriétaire reste sur le hardware Polaris ; les données du
client restent sur son serveur (seuls des extraits scopés transitent, chiffrés).

## Ce qui reste à construire (backlog prod)

### P-A — RAG distant Zero Trust (câbler les missions sur les vraies données)

**P-A.1 — Chemin de données distant. FAIT (2026-07-21), prouvé côté box.**
- [x] `Tenant.box_url` (migration 0046) : adresse par laquelle le cortex joint la box.
  En dev = URL directe ; en prod (tunnel) = endpoint local au cortex attribué au canal.
- [x] `run_audit` construit `MissionClient(box_url, jeton)` et lit le corpus du client à
  distance quand `box_url` est renseignée (sinon retrieve local). Source tracée
  (`retrieval` = `remote_box` | `local_cortex`), persistée dans `last_audit`.
- [x] `box_url` provisionnable via le router clients (create/patch/out).
- Vérifié : audit `conformite_rh` → la box journalise `mission.token.verified` +
  `audit.box_access` + `POST /v1/box/rag/search 200`, l'inférence reste au cortex.

**P-A.2 — Transport par tunnel sortant (traversée de pare-feu). FAIT (2026-07-21), prouvé.**
- [x] **Serveur de tunnel** côté cortex : WebSocket `/v1/tunnel/connect` (`api/v1/tunnel.py`),
  auth par secret partagé + identité de tenant, registre `tenant → canal` runtime
  (`tunnel/channel.py`, multiplexage requête/réponse par `req_id`).
- [x] **Agent tunnel** côté box : dial sortant persistant + reconnexion (`tunnel/agent.py`),
  démarré au lifespan (profil box, si `TUNNEL_CORTEX_URL`). Relaie les requêtes vers sa
  propre API locale `/v1/box/rag/search` (préserve jeton mission + scope + audit).
- [x] `run_audit` priorise le tunnel : canal vivant (`remote_box_tunnel`) > `box_url` direct
  (`remote_box`) > local (`local_cortex`). `TunnelRagClient` compatible `MissionClient`.
- Vérifié : box dial sortant → `tunnel.box_connected` ; audit → `remote_box_tunnel`,
  la box sert le RAG depuis 127.0.0.1 (relais local via le tunnel, pas d'accès entrant).
- Réglages : `TUNNEL_CORTEX_URL`, `ZOLAOS_BOX_TENANT_ID`, `TUNNEL_SHARED_SECRET`,
  `TUNNEL_RAG_TIMEOUT_SECONDS`, `TUNNEL_RECONNECT_SECONDS`.

**P-A.2 durci — credential par box (mTLS applicatif). FAIT (2026-07-21), prouvé.**
- [x] Credential UNIQUE par box (`Tenant.box_credential_hash`, migration 0047), haché
  HMAC + pepper (comme les clés API) ; le secret partagé n'authentifie plus rien.
- [x] Handshake : le Cortex vérifie le credential contre le hash actif du tenant
  (constant-time). Émission/rotation/révocation via `POST`/`DELETE
  /v1/cortex/clients/{id}/box-credential` (secret affiché une fois).
- [x] Révocation **immédiate** : coupe aussi la connexion vivante (`disconnect_tenant`).
- Vérifié : ancienne box (secret partagé) rejetée ; credential valide → connectée +
  audit `remote_box_tunnel` ; révocation → box coupée + reconnexion rejetée (code 4401).

**Transport mTLS (couche déploiement, à configurer) :** en prod le tunnel passe en
`wss://` avec terminaison **mTLS au reverse-proxy** (Caddy/nginx) : la box présente un
certificat client signé par une CA Polaris, le proxy le vérifie et transmet l'identité.
La vérification applicative par credential (ci-dessus) vient EN PLUS — défense en profondeur.

**Reste (durcissement) :** CA + certificats client par box (PKI), registre partagé
(Redis) si Cortex multi-worker, heartbeat/keepalive.

### P-B — Appliance Zolabox (installateur pour le serveur client)
- [ ] Bundle reproductible (Compose durci ou image VM) : app box + Postgres/pgvector +
  Redis + MinIO + Caddy (HTTPS) + **8B local en service supervisé** + agent tunnel.
- [ ] Auto-démarrage (services système, pas un script de session), sauvegardes Postgres,
  corpus public V2.2 pré-chargé.
- [ ] **Provisioning** : générer l'identité de box, l'enregistrer chez Polaris, brancher
  le tunnel. Un seul geste d'installation.

### P-C — Cortex de production (côté Polaris)
- [ ] Le cortex comme service hébergé (pas un `docker run` manuel) : secrets depuis un
  coffre, HTTPS (domaine réel), CORS réel, **70B en service supervisé**.
- [ ] Point d'entrée du tunnel exposé (le seul port entrant, côté Polaris — pas côté client).

### P-D — Exploitation (les deux côtés)
- [ ] Canal de **mise à jour** (corpus + logiciel) poussé par Polaris vers N box.
- [ ] Supervision (Prometheus/Grafana déjà dans la stack), alertes, sauvegardes.
- [ ] Rotation des secrets, révocation d'une box compromise (couper son canal + son crédential).

## Spécification matérielle (indicative)

- **Zolabox client (tier 8B)** : le 70B ne tourne PAS ici — il reste chez Polaris.
  Cible : machine avec GPU d'entrée/milieu de gamme ou APU à mémoire unifiée
  suffisante pour le 8B + embeddings bge-m3, SSD, RAM confortable. À affiner par un
  bench sur le matériel réel des clients cibles.
- **Cortex Polaris** : le gros porteur — GPU/mémoire dimensionnés pour le 70B résident,
  mutualisé sur toutes les missions.

## Ce qui est DÉJÀ prêt (rappel)

Auth de production (login, cookies httpOnly, CSRF, refresh, RBAC), cockpit Zolacortex
(comptes/clients/missions/audit/rapport `.docx`), cloisonnement multi-tenant, profils
box/cortex, mécanique de jeton de mission + `MissionClient`. Le socle fonctionnel est
là ; le chantier prod est l'empaquetage et la connectivité ci-dessus.
