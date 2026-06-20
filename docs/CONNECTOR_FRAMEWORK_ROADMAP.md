# Connector Framework — Feuille de route d'exécution

**Date** : 2026-06-20
**Phase** : 4 (Pôle ERP — pilier critique) · amorce
**Référence cahier des charges** : `ZOLAOS_MASTER_PLAN_V2.md` §2.4 (Connector Framework générique) + §4.4 (intégrations livrées) + §5 (directives) + §7 (décision tranchée).
**Engagement** : feuille de route suivie **scrupuleusement, dans l'ordre, jusqu'au bout**. Chaque jalon est tracé (TaskList) et clos par des tests verts.

---

## 0. Rappel des exigences (source §2.4)

Arborescence cible :
```
src/zolaos/connectors/
├── base.py              # Interface abstraite + modèles canoniques
├── auth.py              # Auth pluggable (API key, OAuth2, basic, certificat, IP allowlist)
├── mapping.py           # Mapping déclaratif YAML (champ source → champ canonique)
├── registry.py          # Découverte + instanciation par config
├── odoo.py              # XML-RPC / JSON-RPC
├── erpnext.py           # REST
├── sage.py              # API ou ODBC
├── generic_rest.py      # REST configurable (OpenAPI)
├── generic_soap.py      # SOAP / WSDL
├── generic_sql.py       # DB direct via SQLAlchemy
├── csv_excel.py         # Ingestion fichiers + watcher dossier
├── webhook.py           # Entrée par webhooks
└── custom_sdk/          # SDK + docs clients (systèmes maison)
```

Principes imposés :
- **Interface unique** : `list_employees()`, `read_invoice()`, `push_journal_entry()`, etc.
- **Mapping déclaratif YAML** : `employee.full_name → person.nom_complet` sans code.
- **Auth pluggable** : API key, OAuth2, basic, certificats, IP allowlist.
- **SDK Custom** : un client implémente `CustomConnector(BaseConnector)` (5-6 méthodes), découvert via config.

Directives transverses (§5) appliquées partout : modularité stricte, sécurité by design (secrets jamais en clair, aucune commande destructrice), mesure systématique (tests + métriques), **multi-pays par tagging** (`country:<iso>`, jamais de `"CG"` en dur), versioning.

---

## 1. Jalons

### Jalon A — Socle (contrats + modèles) — *aucune dépendance externe*
- **A1** `base.py` : `BaseConnector` (cycle de vie `connect`/`healthcheck`/`close`, déclaration de capacités), mixins de capacité (`HRConnector`, `FinanceConnector`, `AccountingConnector`) exposant l'interface unique. Hiérarchie d'erreurs (`ConnectorError`, `ConnectorAuthError`, `ConnectorConfigError`, `CapabilityNotSupported`).
- **A2** Modèles canoniques Pydantic (dans `base.py` ou `models.py`) : `Employee`, `Invoice`, `JournalEntry`, `BankTransaction` — schéma ZolaOS normalisé (`person.nom_complet`…), champ `country` systématique.
- **A3** `auth.py` : interface `AuthStrategy` + implémentations `ApiKeyAuth`, `OAuth2Auth`, `BasicAuth`, `CertificateAuth`, `IPAllowlist`. Secrets via `SecretStr`, jamais en clair. `apply(request)` pour les connecteurs HTTP.
- **A4** `mapping.py` : chargement d'un mapping YAML déclaratif, application (`source → canonique`), transformations simples, validation. + fichier d'exemple `mappings/`.

### Jalon B — Connecteurs génériques standard (§4.4 « livrés en standard »)
- **B1** `csv_excel.py` : ingestion CSV + XLSX (`openpyxl`, déjà dépendance), + watcher de dossier (polling portable, pas d'inotify Windows). Mapping appliqué.
- **B2** `generic_rest.py` : REST configurable (httpx, déjà dépendance), pagination, auth pluggable, mapping.
- **B3** `generic_sql.py` : accès DB direct via SQLAlchemy (déjà dépendance), requêtes en lecture paramétrées, mapping.
- **B4** `webhook.py` : réception par webhook (handler + vérification signature HMAC optionnelle), normalisation via mapping.

### Jalon C — Connecteurs produits
- **C1** `odoo.py` : XML-RPC (`xmlrpc.client`, stdlib) — implémentation fonctionnelle.
- **C2** `erpnext.py` : REST (httpx) — implémentation fonctionnelle.
- **C3** `generic_soap.py` + `sage.py` : **squelettes fonctionnels avec import optionnel** (`zeep` / `pyodbc` non ajoutés aux deps par défaut — décision consciente pour rester léger/local). Lèvent `ConnectorConfigError` explicite si la lib optionnelle manque, avec docstring d'activation. *(Documenté comme choix, pas comme oubli.)*

### Jalon D — SDK Custom + découverte
- **D1** `custom_sdk/` : `CustomConnector(BaseConnector)` (5-6 méthodes à implémenter) + `README.md` client + exemple minimal.
- **D2** `registry.py` : enregistrement + découverte par configuration déclarative (nom → classe + config + auth + mapping), instanciation centralisée.

### Jalon E — Sécurité, observabilité, configuration
- **E1** Métriques Prometheus (`CONNECTOR_CALLS_TOTAL`, `CONNECTOR_CALL_DURATION_SECONDS`) + audit (hash via le pattern existant) sur chaque appel externe.
- **E2** Settings : ajout des réglages connecteurs (timeouts, IP allowlist) dans `core/settings.py` sans casser l'existant ; mise à jour `.env.example`.
- **E3** Disponibilité dans les deux profils (`box` ET `cortex`) — les connecteurs vivent là où sont les données (côté client = box).

### Jalon F — Tests + documentation + clôture
- **F1** Tests unitaires : `mapping`, `auth`, `csv_excel`, `generic_rest` (respx), `generic_sql` (SQLite), `registry`, `custom_sdk`. Marqueurs cohérents, couverture ≥ 60 % du module.
- **F2** `docs/CONNECTORS.md` : guide d'usage + tableau des connecteurs + exemple de mapping YAML. Pointeur depuis le README.
- **F3** Run complet de la suite dans l'image `zolaos:dev-test` → **0 échec**.
- **F4** Commits (cœur public AGPL) + push après confirmation. Mise à jour de cette feuille de route (statut final) + note mémoire si nécessaire.

---

## 2. Critères de sortie du Connector Framework

- Interface unique opérationnelle (`list_employees` / `read_invoice` / `push_journal_entry`) sur ≥ 1 connecteur réel testé bout-en-bout (`csv_excel`).
- Mapping déclaratif YAML fonctionnel et testé.
- ≥ 4 connecteurs standard livrés (`csv_excel`, `generic_rest`, `generic_sql`, `webhook`) + 2 produits (`odoo`, `erpnext`) + SDK custom.
- Auth pluggable testée (≥ ApiKey + Basic).
- Tests verts dans l'image dev, aucune régression sur les 114 tests existants.
- Multi-pays respecté (aucun `"CG"` en dur), secrets via `SecretStr`.

---

## 3. Hors périmètre (explicitement, pour ne pas confondre avec un oubli)

- **Branchement des sous-agents ERP** (RH/Finance/Compta) sur les connecteurs → jalon ERP suivant (Phase 4.1-4.3), pas ce chantier.
- **Déploiement chez un pilote PME** (§4.5) → terrain.
- **Connecteurs Mobile Money** (MTN MoMo / Airtel) → Phase 6 Fintech (§6.3), pas Phase 4.
- `zeep`/`pyodbc` ajoutés aux dépendances → différé (squelettes optionnels livrés).

---

## 4. Statut final (2026-06-20) — ✅ TERMINÉ

| Jalon | État | Livré |
|-------|------|-------|
| A — Socle | ✅ | `base.py`, `models.py`, `auth.py`, `mapping.py` + mapping d'exemple |
| B — Génériques | ✅ | `csv_excel.py`, `generic_rest.py`, `generic_sql.py`, `webhook.py` |
| C — Produits | ✅ | `odoo.py`, `erpnext.py` (fonctionnels) ; `generic_soap.py`, `sage.py` (squelettes dép. optionnelle) |
| D — SDK + découverte | ✅ | `registry.py`, `custom_sdk/` (base + exemple + README) |
| E — Sécu/observabilité/config | ✅ | métriques `zolaos_connector_*`, `CONNECTOR_DEFAULT_TIMEOUT_SECONDS`, profils box+cortex |
| F — Tests/doc/clôture | ✅ | `tests/test_connectors.py` (15 tests), `docs/CONNECTORS.md`, pointeur README |

**Tests** : 15 tests connecteurs + run complet **129 passés / 0 échec / 3 désélectionnés** (image `zolaos:dev-test`). Aucune régression sur les 114 tests préexistants.

**Critères de sortie** : tous atteints (interface unique testée bout-en-bout sur `csv_excel` + `generic_rest`, mapping YAML, 4 génériques + 2 produits + SDK custom, auth ApiKey/Basic/OAuth2/IP testées, multi-pays respecté, secrets en `SecretStr`).

---

*Feuille de route établie et exécutée intégralement le 2026-06-20 (A→F).*
