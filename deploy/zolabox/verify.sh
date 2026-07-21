#!/bin/sh
# Vérification post-installation d'une Zolabox. À lancer depuis deploy/zolabox/
# après ./install.sh (et ./seed_corpus.sh). Sort en erreur si un contrôle échoue.
set -eu
cd "$(dirname "$0")"
fail=0
check() { printf "  %-42s " "$1"; shift; if "$@" >/dev/null 2>&1; then echo "OK"; else echo "ÉCHEC"; fail=1; fi; }

echo "Vérification Zolabox :"
check "au moins 5 services démarrés" sh -c 'test "$(docker compose ps --services --status running | wc -l)" -ge 5'
check "app /health répond" docker compose exec -T app curl -fsS http://localhost:8000/health
check "modèle 8B présent (ollama)" sh -c 'docker compose exec -T ollama ollama list | grep -q .'
check "corpus public chargé (rag_legal)" sh -c 'docker compose exec -T postgres psql -U postgres -d "${POSTGRES_DB:-zolaos}" -tAc "SELECT count(*)>0 FROM rag_legal.documents" | grep -q t'
check "tunnel sortant connecté" sh -c 'docker compose logs app --since 10m 2>/dev/null | grep -q tunnel.agent.connected'
check "dev-token désactivé (prod)" sh -c 'test "$(docker compose exec -T app curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/v1/auth/dev-token)" = "404"'

if [ $fail -eq 0 ]; then
  echo "✓ Zolabox opérationnelle. Test final : se connecter sur https://<domaine> et poser une question."
else
  echo "✗ Des vérifications ont échoué — voir 'docker compose logs'."
  exit 1
fi
