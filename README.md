# ZolaOS

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Plateforme IA multi-agents **souveraine**, exécutée **exclusivement en local**, pour la **République du Congo** (Brazzaville).

> **Licence — Modèle open-core** : le cœur public est sous **GNU AGPL v3 ou
> ultérieure**. Les composants propriétaires de Polaris (overlays cabinet,
> prompts secrets, modèles fine-tunés, templates de rapport) ne sont pas
> distribués et restent chez Polaris (architecture Zero Trust Client).
> Une licence commerciale alternative est négociable. Voir
> [`LICENSE`](./LICENSE), [`NOTICE`](./NOTICE),
> [`THIRD_PARTY_LICENSES.md`](./THIRD_PARTY_LICENSES.md). **Built with Llama.**

- Modèles : Llama-3-8B (routeur + brigade) + Llama-3-70B (orchestrateur) via Ollama.
- Persistance : PostgreSQL + pgvector, schémas cloisonnés par pôle.
- API : FastAPI exposée à des clients tiers (Web, Flutter).
- Fallback API externe (Anthropic) : **codé mais désactivé par défaut** (`ENABLE_EXTERNAL_FALLBACK=false`).

> Marché initial : **République du Congo (Brazzaville)** uniquement. À ne pas confondre avec la RDC.
> Cadres : OHADA, CEMAC/BEAC, OAPI, CIPRES + législation nationale CG.

Plan complet : [`ZOLAOS_MASTER_PLAN_V2.md`](./ZOLAOS_MASTER_PLAN_V2.md).

---

## Démarrage rapide (dev)

### Prérequis
- Docker Desktop (Windows/Mac) ou Docker Engine (Linux)
- Python 3.12+ (pour le dev local hors conteneur)
- 16 Go RAM minimum pour la stack complète (sans le 70B)
- Pour Llama-3-70B : 64 Go+ RAM utile

### Installation

1. **Cloner et copier la configuration** :
   ```powershell
   Copy-Item .env.example .env
   ```

2. **Générer les secrets** (PowerShell) :
   ```powershell
   # Exemple : génère un secret hex 32 octets
   [Convert]::ToHexString((New-Object byte[] 32 | ForEach-Object { Get-Random -Maximum 256 -SetSeed $_ })).ToLower()
   ```
   Ou via openssl si disponible :
   ```bash
   openssl rand -hex 32
   ```
   Renseigner dans `.env` : tous les `POSTGRES_PASSWORD_*`, `REDIS_PASSWORD`, `MINIO_ROOT_PASSWORD`, `JWT_SECRET`, `API_KEY_PEPPER`, `ENCRYPTION_KEY_AUDIT`.

3. **Démarrer la stack** :
   ```bash
   docker compose up -d
   ```
   Services :
   - API : http://localhost:8000 (docs : http://localhost:8000/docs en dev)
   - Postgres : localhost:5432
   - Redis : localhost:6379
   - MinIO console : http://localhost:9001
   - Ollama : http://localhost:11434

4. **Activer l'observabilité** (optionnel) :
   ```bash
   docker compose --profile observability up -d
   ```
   - Prometheus : http://localhost:9090
   - Grafana : http://localhost:3001

5. **Activer le reverse proxy Caddy** (staging/prod) :
   ```bash
   docker compose --profile with-proxy up -d
   ```

### Vérification

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.0.1","env":"dev","country":"cg","external_fallback_enabled":false}

curl http://localhost:8000/metrics
# (exposition Prometheus)
```

---

## Développement local (sans Docker pour l'app)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Lancer Postgres + Redis + MinIO + Ollama via Docker
docker compose up -d postgres redis minio ollama

# Lancer l'API en local
uvicorn zolaos.api.main:app --reload --port 8000
```

---

## Tests

```bash
pytest                          # tous les tests
pytest -m security              # tests de sécurité (garde-fou anti-fallback)
pytest -m "not integration"     # exclut les tests d'intégration
pytest --cov                    # avec couverture
```

---

## Structure

```
.
├── src/zolaos/             # Code applicatif
│   ├── api/                # FastAPI app + routes
│   ├── core/               # Settings, logging, metrics
│   ├── llm/                # Clients Ollama + garde-fou fallback
│   ├── agents/             # Sous-agents (Phase 1+)
│   ├── connectors/         # Connector Framework (Phase 4) — voir docs/CONNECTORS.md
│   ├── rag/                # Pipelines d'indexation et recherche
│   └── tools/              # Outils sandboxés
├── agents/prompts/         # Prompts versionnés (Phase 1+)
├── alembic/                # Migrations DB
├── infra/
│   ├── postgres/           # init SQL (schémas + audit log)
│   ├── caddy/              # Reverse proxy config
│   ├── prometheus/         # Scrape config
│   └── secrets/            # Inventaire local (gitignored)
├── tests/                  # Tests pytest
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
└── ZOLAOS_MASTER_PLAN_V2.md
```

---

## Garde-fou anti-fallback

Tant que `ENABLE_EXTERNAL_FALLBACK=false`, **aucun appel sortant** n'est possible vers une API externe. Vérifié par un test marqué `security` à chaque commit. Voir `src/zolaos/llm/guard.py` et `tests/test_external_fallback_guard.py`.

L'activation manuelle nécessite simultanément :
- `ENABLE_EXTERNAL_FALLBACK=true`
- `ANTHROPIC_API_KEY` renseignée
- `EXTERNAL_FALLBACK_BUDGET_MONTHLY_USD > 0`

Voir §2.7 du plan pour la procédure complète.

---

## Roadmap

| Phase | Durée    | Livrable                                                    |
|-------|----------|-------------------------------------------------------------|
| 0     | S 1-2    | Socle technique (vous êtes ici)                            |
| 1     | Mois 1   | Fondations système (orchestrateur, méta-agents)            |
| 2     | Mois 2-3 | MVP Santé + Droit (OHADA + droit du travail CG + fiscal)   |
| 3     | Mois 4   | Code Agent (Pôle Engineering)                              |
| 4     | Mois 5-6 | Pôle ERP + Connector Framework                             |
| 5     | Mois 7   | Pôle GRC (conformité, audit, reporting)                    |
| 6     | Mois 8   | Fintech (scoring crédit, KYC, MoMo + Airtel Money)         |
| 7     | Mois 9+  | Cyber-défense (défensif strict)                            |
| 8     | Mois 10+ | Industrialisation                                          |
| 9     | Mois 12+ | Pôle K (Lingala + Kituba)                                  |

Détails : [`ZOLAOS_MASTER_PLAN_V2.md`](./ZOLAOS_MASTER_PLAN_V2.md).

---

## Contribution

Voir [`CONTRIBUTING.md`](./CONTRIBUTING.md).
