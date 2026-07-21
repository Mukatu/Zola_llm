#!/bin/sh
# Vérification post-installation du Zolacortex. À lancer depuis deploy/zolacortex/
# après ./install.sh. Sort en erreur si un contrôle échoue.
set -eu
cd "$(dirname "$0")"
fail=0
check() { printf "  %-42s " "$1"; shift; if "$@" >/dev/null 2>&1; then echo "OK"; else echo "ÉCHEC"; fail=1; fi; }

echo "Vérification Zolacortex :"
check "au moins 5 services démarrés" sh -c 'test "$(docker compose ps --services --status running | wc -l)" -ge 5'
check "app /health répond" docker compose exec -T app curl -fsS http://localhost:8000/health
check "modèle 8B présent" sh -c 'docker compose exec -T ollama ollama list | grep -qi "8b"'
check "modèle 70B présent" sh -c 'docker compose exec -T ollama ollama list | grep -qi "70b"'
check "routes cortex montées" sh -c 'docker compose exec -T app curl -fsS http://localhost:8000/openapi.json | grep -q "/v1/cortex/missions"'
check "CA Polaris présente (mTLS)" test -f pki/certs/polaris-ca.crt
check "dev-token désactivé (prod)" sh -c 'test "$(docker compose exec -T app curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/v1/auth/dev-token)" = "404"'

if [ $fail -eq 0 ]; then
  echo "✓ Zolacortex opérationnel. Attendre qu'une box se connecte (log 'tunnel.box_connected')."
else
  echo "✗ Des vérifications ont échoué — voir 'docker compose logs'."
  exit 1
fi
