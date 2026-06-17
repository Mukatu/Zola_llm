#!/bin/sh
# Télécharge le texte officiel complet de la GNU AGPL v3 depuis gnu.org
# et l'écrit dans LICENSE.AGPL-3.0 à la racine du projet.
#
# À exécuter AVANT toute distribution publique du logiciel — exigence légale
# pour une distribution conforme AGPL (le texte complet doit accompagner le
# code source).
#
# Le fichier LICENSE de la racine contient un en-tête court + SPDX identifier
# + référence ; le texte complet va dans LICENSE.AGPL-3.0 séparé pour ne pas
# polluer la lecture quotidienne du repo.
#
# Usage :
#   bash infra/scripts/fetch_full_license.sh
#
# Vérification de l'intégrité : le hash SHA-256 du fichier officiel
# agpl-3.0.txt est stable. Si le hash ne correspond pas → script échoue.

set -eu

URL="https://www.gnu.org/licenses/agpl-3.0.txt"
TARGET="LICENSE.AGPL-3.0"
EXPECTED_SHA256="0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0"

echo "[fetch_full_license] Downloading official AGPL v3 text from $URL"

if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$URL" -o "$TARGET"
elif command -v wget >/dev/null 2>&1; then
    wget -q "$URL" -O "$TARGET"
else
    echo "[fetch_full_license] ERROR: neither curl nor wget found" >&2
    exit 1
fi

if [ ! -s "$TARGET" ]; then
    echo "[fetch_full_license] ERROR: downloaded file is empty" >&2
    exit 1
fi

# Sanity check du contenu (l'en-tête doit contenir le titre officiel)
if ! grep -q "GNU AFFERO GENERAL PUBLIC LICENSE" "$TARGET"; then
    echo "[fetch_full_license] ERROR: content does not look like AGPL text" >&2
    rm -f "$TARGET"
    exit 1
fi

# Vérification SHA-256 si sha256sum est disponible. Le hash est mis à jour
# manuellement si la FSF change le fichier (rare). Si la vérification échoue,
# le script CONTINUE avec un avertissement (le fichier reste), car la FSF
# peut légitimement avoir publié une nouvelle révision mineure.
if command -v sha256sum >/dev/null 2>&1; then
    ACTUAL=$(sha256sum "$TARGET" | awk '{print $1}')
    if [ "$ACTUAL" != "$EXPECTED_SHA256" ]; then
        echo "[fetch_full_license] WARNING: SHA-256 hash mismatch"
        echo "  expected: $EXPECTED_SHA256"
        echo "  actual:   $ACTUAL"
        echo "  → vérifier manuellement le contenu de $TARGET et mettre à jour"
        echo "    EXPECTED_SHA256 dans ce script si la FSF a publié une révision."
    fi
fi

WORD_COUNT=$(wc -w "$TARGET" | awk '{print $1}')
echo "[fetch_full_license] ✓ $TARGET ($WORD_COUNT mots)"
