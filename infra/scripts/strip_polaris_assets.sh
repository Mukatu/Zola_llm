#!/bin/sh
# Security-IP-2 — Supprime les actifs Polaris d'une image Zolabox (profil box).
# Exécuté dans le Dockerfile quand --build-arg ZOLAOS_PROFILE=box.
#
# Cible :
#   - Overlays Polaris (src/zolaos/agents/polaris/)
#   - Prompts secrets cabinet (agents/prompts/polaris/)
#   - Endpoints Cortex (src/zolaos/api/v1/cortex.py)
#   - Module reports/ entier (génération .docx réservée Cortex)
#
# La présence physique de ces fichiers est strictement interdite dans une
# image livrée chez un client. Le garde-fou applicatif (Security-IP-1) constitue
# une seconde ligne de défense, mais la suppression physique est la première.

set -eu

INSTALL_ROOT="${1:-/install/lib/python3.12/site-packages/zolaos}"
APP_ROOT="${2:-/app}"

echo "[strip_polaris] Mode BOX — suppression des actifs cabinet"
echo "[strip_polaris] INSTALL_ROOT=$INSTALL_ROOT  APP_ROOT=$APP_ROOT"

# 1. Overlays Polaris dans le package installé
if [ -d "$INSTALL_ROOT/agents/polaris" ]; then
    echo "[strip_polaris] - rm -rf $INSTALL_ROOT/agents/polaris/"
    rm -rf "$INSTALL_ROOT/agents/polaris"
fi

# 2. Endpoints Cortex
if [ -f "$INSTALL_ROOT/api/v1/cortex.py" ]; then
    echo "[strip_polaris] - rm $INSTALL_ROOT/api/v1/cortex.py"
    rm -f "$INSTALL_ROOT/api/v1/cortex.py"
fi

# 3. Module reports/ : la génération .docx est exclusivement Cortex
if [ -d "$INSTALL_ROOT/reports" ]; then
    echo "[strip_polaris] - rm -rf $INSTALL_ROOT/reports/"
    rm -rf "$INSTALL_ROOT/reports"
fi

# 4. Aussi côté src/ copié dans /app/src (si présent)
if [ -d "$APP_ROOT/src/zolaos/agents/polaris" ]; then
    rm -rf "$APP_ROOT/src/zolaos/agents/polaris"
fi
if [ -f "$APP_ROOT/src/zolaos/api/v1/cortex.py" ]; then
    rm -f "$APP_ROOT/src/zolaos/api/v1/cortex.py"
fi
if [ -d "$APP_ROOT/src/zolaos/reports" ]; then
    rm -rf "$APP_ROOT/src/zolaos/reports"
fi

# 5. Prompts secrets cabinet (montés en bind dans /app/agents/prompts/)
if [ -d "$APP_ROOT/agents/prompts/polaris" ]; then
    echo "[strip_polaris] - rm -rf $APP_ROOT/agents/prompts/polaris/"
    rm -rf "$APP_ROOT/agents/prompts/polaris"
fi

# 6. Sanity check : aucun fichier polaris/ résiduel ; aucun cortex.py résiduel
LEFTOVERS=$(find "$INSTALL_ROOT" "$APP_ROOT" \
    \( -path '*/polaris/*' -o -name 'cortex.py' -o -path '*/reports/*' \) \
    -type f 2>/dev/null || true)
if [ -n "$LEFTOVERS" ]; then
    echo "[strip_polaris] ❌ ERREUR : actifs Polaris résiduels détectés :"
    echo "$LEFTOVERS"
    exit 1
fi

echo "[strip_polaris] ✓ Aucun actif Polaris résiduel — image Zolabox propre"
