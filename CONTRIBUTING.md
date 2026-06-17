# Contribuer à ZolaOS

## Workflow

1. Créer une branche depuis `dev` : `git checkout -b feat/<sujet>`.
2. Coder + tester localement.
3. Ouvrir une PR vers `dev`. La CI doit passer (lint, types, tests, security, build).
4. Une PR de `dev` vers `main` après validation pilote.

---

## Conventions de code

### Python
- Version : **3.12+**.
- Formatage : `black` (largeur 100).
- Lint : `ruff` (config dans `pyproject.toml`). Règles activées : E, W, F, I, B, C4, UP, S, N, RUF.
- Types : `mypy --strict` sur `src/`. Tests dispensés du strict.
- Async par défaut pour les I/O (FastAPI, asyncpg, httpx).

### Commits
- Style : `<type>: <résumé>` (impératif, < 70 caractères).
- Types : `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `infra`, `sec`.
- Le corps de message explique le **pourquoi**, pas le **quoi**.
- Aucune signature externe (pas de `Co-Authored-By` automatique).

### Tests
- Tout nouveau code = tests obligatoires.
- Couverture minimale CI : **60 %** (montée progressive : 70 % en fin Phase 1, 80 % à partir de Phase 4).
- Marqueurs disponibles : `integration`, `slow`, `security`.

---

## Versioning des prompts

Les system prompts sont du **code critique**. Conventions :

### Emplacement
```
agents/prompts/
├── router.md
├── health/
│   └── pharmacology.md
├── legal/
│   ├── ohada.md
│   ├── labor_cg.md
│   └── tax_cg.md
├── erp/
│   ├── hr.md
│   ├── finance.md
│   └── accounting.md
└── ...
```

### Format de chaque prompt
```markdown
---
agent: pharmacology
model: llama3:8b
version: 1.2.0
country: cg
last_review: 2026-05-14
reviewer: <initiales>
test_set: tests/agents/pharmacology/regression_v1.jsonl
---

# System prompt

Tu es un sous-agent spécialisé en pharmacologie...
```

### Règles
- Chaque modification = bump `version` (semver : patch pour reformulation, minor pour comportement, major pour rupture).
- Chaque modification ≥ minor = exécution du test set de régression, résultats joints à la PR.
- Pas de prompt non documenté ni de prompt en dur dans le code applicatif.

---

## Sécurité

### Secrets
- **Jamais** de secret dans le code, dans les tests, ou dans les commits.
- `gitleaks` scanne chaque PR.
- Faux-positifs : ajouter une exception explicite dans `.gitleaks.toml`.

### Garde-fou anti-fallback
- Toute modification du module `zolaos.llm.guard` ou de l'activation du flag `ENABLE_EXTERNAL_FALLBACK` exige une PR distincte, **review obligatoire d'un mainteneur**, et un commentaire explicite justifiant le changement.
- Le test `test_external_fallback_guard.py` ne doit **jamais** être désactivé.

### Données sensibles (santé, droit, ERP)
- Toute fonction touchant des données utilisateur passe par l'audit (`audit.log`).
- Les tests d'intégration utilisent des données **synthétiques**, jamais des données réelles de pilotes.

---

## Multi-pays

ZolaOS est conçu multi-pays par tagging :
- Tout chunk de RAG porte un tag `country:<iso>` (`country:cg` par défaut).
- **Jamais** de constante `"CG"` codée en dur dans la logique métier. Toujours via `settings.DEFAULT_COUNTRY` ou paramètre explicite.
- Les corpus juridiques nationaux sont indexés dans des schémas séparés (`rag_legal_labor_cg`, `rag_legal_tax_cg`, etc.).

---

## Souveraineté repo

Le projet démarre sur **GitHub privé** pour la vélocité, avec migration prévue vers **Gitea self-hosted** en Phase 8.
- Pas de GitHub-specific dans le code applicatif.
- Workflow `.github/workflows/ci.yml` documenté pour pouvoir être porté vers Gitea Actions ou Drone CI sans réécriture.
