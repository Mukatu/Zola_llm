# Attributions tierces — ZolaOS

Ce fichier liste l'ensemble des composants tiers utilisés par ZolaOS, leur
licence applicable et les obligations qui en découlent pour la distribution.

Dernière mise à jour : 2026-05-19.

---

## Modèles LLM

| Composant | Éditeur | Licence | Obligation distribution |
|---|---|---|---|
| **Llama 3** (8B, 70B) | Meta Platforms, Inc. | **Llama 3 Community License Agreement** | ⚠️ Attribution "Built with Llama" obligatoire, clause MAU (>700M utilisateurs mensuels — n'affecte pas Polaris). Tout modèle dérivé fine-tuné reste sous la même licence. |
| bge-m3 (embeddings) | BAAI | MIT | Préservation copyright + permission notice |

> **Note critique** : tout modèle fine-tuné par Polaris à partir de Llama 3
> (par exemple les futurs modèles spécialisés Congo) reste **sous Llama 3
> Community License**. Polaris peut commercialiser ces modèles dérivés mais
> ne peut pas prétendre à une propriété exclusive sans licence — la licence
> Llama doit toujours être incluse.

## Serveurs LLM

| Composant | Licence | Obligation |
|---|---|---|
| llama.cpp | MIT | Préserver copyright + permission notice |
| Ollama (optionnel) | MIT | Idem |

## Framework applicatif

| Composant | Licence | Obligation |
|---|---|---|
| FastAPI | MIT | Préservation copyright |
| Uvicorn | BSD 3-Clause | Préservation copyright |
| Pydantic, pydantic-settings | MIT | Idem |
| Starlette | BSD 3-Clause | Idem |
| anyio | MIT | Idem |
| httpx | BSD 3-Clause | Idem |

## Base de données

| Composant | Licence | Obligation |
|---|---|---|
| PostgreSQL 16 | **PostgreSQL License** (BSD-like) | Préservation copyright + disclaimer |
| pgvector | PostgreSQL License | Idem |
| SQLAlchemy 2.0 | MIT | Préservation copyright |
| asyncpg | Apache 2.0 | Copie de la licence + NOTICE |
| psycopg 3 | LGPL 3.0 with OpenSSL exception | LGPL : utilisation OK ; dynamic linking préservé |
| alembic | MIT | Préservation copyright |

## Embeddings et ML

| Composant | Licence | Obligation |
|---|---|---|
| sentence-transformers | Apache 2.0 | Copie de la licence + NOTICE |
| transformers (HF) | Apache 2.0 | Idem |
| torch (CPU) | BSD 3-Clause | Préservation copyright |
| huggingface-hub | Apache 2.0 | Idem |
| numpy | BSD 3-Clause | Idem |
| scipy | BSD 3-Clause | Idem |
| scikit-learn | BSD 3-Clause | Idem |
| tokenizers | Apache 2.0 | Idem |
| safetensors | Apache 2.0 | Idem |

## Cache, queue, stockage

| Composant | Licence | Obligation |
|---|---|---|
| Redis (client Python) | MIT | Préservation copyright |
| dramatiq | LGPL 3.0 | Utilisation OK, attention au linking statique |
| MinIO (client Python) | Apache 2.0 | Copie de la licence + NOTICE |

## Sécurité, JWT, crypto

| Composant | Licence | Obligation |
|---|---|---|
| python-jose | MIT | Préservation copyright |
| bcrypt | Apache 2.0 | Copie de la licence + NOTICE |
| cryptography | Apache 2.0 / BSD dual | Idem |
| python-jose[cryptography] | MIT + Apache 2.0 (cryptography) | Cumulé |

## Documents et templates

| Composant | Licence | Obligation |
|---|---|---|
| python-docx | MIT | Préservation copyright |
| openpyxl | MIT | Idem |
| pypdf | BSD 3-Clause | Idem |
| beautifulsoup4 | MIT | Idem |
| Jinja2 | BSD 3-Clause | Préservation copyright |
| pyyaml | MIT | Idem |
| orjson | Apache 2.0 / MIT dual | Copie de la licence + NOTICE |

## Observabilité

| Composant | Licence | Obligation |
|---|---|---|
| structlog | Apache 2.0 / MIT dual | Copie de la licence |
| prometheus-client | Apache 2.0 | Idem |
| opentelemetry-api/sdk/instrumentation-fastapi | Apache 2.0 | Idem |

## Utilitaires

| Composant | Licence | Obligation |
|---|---|---|
| python-dotenv | BSD 3-Clause | Préservation copyright |
| tenacity | Apache 2.0 | Copie de la licence |

## Outils de développement (non distribués au client)

| Composant | Licence | Note |
|---|---|---|
| ruff, black, mypy, pytest, pytest-asyncio, pytest-cov, pytest-mock, respx, freezegun | MIT / Apache 2.0 | Pas distribués (deps `[dev]` uniquement) |

---

## Synthèse des obligations pour Polaris

Pour distribuer ZolaOS (cœur public sous AGPL v3) à un client, Polaris doit :

1. **Inclure le fichier `LICENSE`** à la racine + `LICENSE.AGPL-3.0` (texte complet AGPL, généré via `infra/scripts/fetch_full_license.sh`).
2. **Inclure le fichier `NOTICE`** avec l'attribution Llama et autres mentions Apache 2.0.
3. **Inclure le fichier `THIRD_PARTY_LICENSES.md`** (ce fichier).
4. **Publier les modifications du cœur** que Polaris aurait apportées (clause AGPL "use over network" — c'est le cas dès qu'un client utilise la Zolabox via le réseau).
5. **Ne pas inclure les composants propriétaires** (`src/zolaos/agents/polaris/`, `src/zolaos/api/v1/cortex.py`, `src/zolaos/reports/`, `agents/prompts/polaris/`) — déjà garanti par le build `ZOLAOS_PROFILE=box` qui les strip physiquement.

## Stratégie de double licence commerciale

Pour les clients qui ne peuvent pas se conformer à l'AGPL v3 (notamment l'obligation de publication des modifications), Polaris propose une licence commerciale alternative négociée au cas par cas. Contact : `licensing@polaris.cg`.
