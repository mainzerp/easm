#!/bin/sh
# EASM TLS entrypoint: generates a self-signed cert (if missing) and
# installs the HTTPS server block unless EASM_TLS=off.
# Runs before nginx start (nginx image /docker-entrypoint.d mechanism).
set -e

TLS_DIR=/etc/nginx/tls
CONF=/etc/nginx/conf.d/tls.conf
SRC=/etc/nginx/easm-tls.conf

mkdir -p "$TLS_DIR"

if [ "${EASM_TLS:-on}" = "off" ]; then
  rm -f "$CONF"
  echo "[easm-tls] EASM_TLS=off — HTTPS listener (443) disabled"
  exit 0
fi

if [ ! -f "$TLS_DIR/easm.crt" ] || [ ! -f "$TLS_DIR/easm.key" ]; then
  SAN="${EASM_TLS_SAN:-DNS:localhost,DNS:easm.local,IP:127.0.0.1}"
  echo "[easm-tls] Generating self-signed certificate (SAN: $SAN)"
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$TLS_DIR/easm.key" \
    -out "$TLS_DIR/easm.crt" \
    -days 825 \
    -subj "/CN=easm" \
    -addext "subjectAltName=$SAN" 2>/dev/null
  chmod 600 "$TLS_DIR/easm.key"
else
  echo "[easm-tls] Existing certificate found ($TLS_DIR/easm.crt)"
fi

cp "$SRC" "$CONF"

if [ "${EASM_HSTS:-off}" = "on" ]; then
  sed -i 's/listen 443 ssl;/listen 443 ssl;\n    add_header Strict-Transport-Security "max-age=15552000" always;/' "$CONF"
  echo "[easm-tls] HSTS enabled"
fi

echo "[easm-tls] HTTPS listener active (port 443)"
