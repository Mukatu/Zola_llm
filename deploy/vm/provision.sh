#!/bin/sh
# ============================================================================
# Provisionne une VM Zolabox (Ubuntu) : Docker + bundle + service de démarrage.
# Utilisé à la fois par cloud-init (user-data) et par Packer (build de l'OVA).
# Exécuté en root. Idempotent.
#
# Variables :
#   ZOLAOS_REPO  URL du dépôt public à cloner dans /opt/zolaos (si absent).
# ============================================================================
set -eu
export DEBIAN_FRONTEND=noninteractive
REPO="${ZOLAOS_REPO:-https://github.com/Mukatu/Zola_llm.git}"

echo "[provision] Paquets de base…"
apt-get update
apt-get install -y ca-certificates curl git openssl gnupg

echo "[provision] Docker…"
if ! command -v docker >/dev/null 2>&1; then
  install -m0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker

echo "[provision] Bundle ZolaOS dans /opt/zolaos…"
[ -d /opt/zolaos/.git ] || git clone --depth 1 "$REPO" /opt/zolaos

echo "[provision] Service de démarrage…"
install -m0644 /opt/zolaos/deploy/vm/zolabox.service /etc/systemd/system/zolabox.service
systemctl daemon-reload
systemctl enable zolabox.service   # ne démarre PAS tant que .env n'est pas renseigné

cat <<'MSG'
[provision] VM Zolabox prête.
  Au premier démarrage chez le client :
    cd /opt/zolaos/deploy/zolabox
    cp .env.zolabox.example .env   # renseigner l'identité de la box (provisioning Cortex)
    ./install.sh admin@le-client.cg
    ./seed_corpus.sh corpus_public.dump
  Puis le service `zolabox` maintient la pile au démarrage (systemctl start zolabox).
MSG
