#!/bin/sh
# ============================================================================
# PKI du tunnel mTLS (côté Polaris). Génère la CA Polaris (une fois) et émet un
# certificat client PAR BOX (CN = tenant_id). La box présente box_<id>.crt/.key au
# tunnel wss ; le Cortex (Caddy) vérifie le certificat contre polaris-ca.crt.
#
# C'est la couche TRANSPORT ; elle vient EN PLUS du credential applicatif par box.
# Révocation d'une box = retirer son credential au Cortex (immédiat) ; le certificat,
# lui, se révoque via une CRL/roulement de CA (cf. README).
#
# Usage : ./issue_box_cert.sh <tenant_id>
# ============================================================================
set -eu
cd "$(dirname "$0")"
mkdir -p certs
CA_KEY=certs/polaris-ca.key
CA_CRT=certs/polaris-ca.crt

# 1) CA Polaris (une seule fois, longue durée)
if [ ! -f "$CA_CRT" ]; then
  echo "→ Génération de la CA Polaris…"
  openssl genrsa -out "$CA_KEY" 4096 2>/dev/null
  openssl req -x509 -new -nodes -key "$CA_KEY" -sha256 -days 3650 \
    -subj "/O=Polaris/CN=Polaris ZolaOS CA" -out "$CA_CRT"
  chmod 600 "$CA_KEY"
  echo "  CA : $CA_CRT (à déployer sur le Cortex pour Caddy client_auth)"
fi

# 2) certificat client pour un tenant (CN = tenant_id)
TENANT="${1:?Usage: ./issue_box_cert.sh <tenant_id>}"
OUT="certs/box_${TENANT}"
openssl genrsa -out "${OUT}.key" 2048 2>/dev/null
openssl req -new -key "${OUT}.key" -subj "/O=Polaris/CN=${TENANT}" -out "${OUT}.csr" 2>/dev/null
openssl x509 -req -in "${OUT}.csr" -CA "$CA_CRT" -CAkey "$CA_KEY" -CAcreateserial \
  -days 825 -sha256 -out "${OUT}.crt" 2>/dev/null
rm -f "${OUT}.csr"
chmod 600 "${OUT}.key"
echo "✓ Certificat client émis (tenant ${TENANT}) :"
echo "   ${OUT}.crt / ${OUT}.key  → box (TUNNEL_CLIENT_CERT_PATH / TUNNEL_CLIENT_KEY_PATH)"
echo "   Le CN du certificat = ${TENANT} ; le Cortex vérifie CN == tenant_id."
