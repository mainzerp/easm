#!/bin/bash
set -euo pipefail

DOMAINS="${TARGET_DOMAIN:-example.com}"
DOMAIN_DISPLAY=$(echo "$DOMAINS" | grep -v '^$' | tr '\n' ' ' | sed 's/  */ /g' | sed 's/ *$//')
OUT="${OUTPUT_DIR:-/results/$(date +%Y-%m-%d_%H-%M)}"
SEVERITY="${NUCLEI_SEVERITY:-critical,high,medium}"
PORTS="${PORTS:-80,443,8080,8443,22,21,3306,5432,6379,9200,27017}"
ENABLE_HTTPX="${ENABLE_HTTPX:-true}"
ENABLE_NMAP="${ENABLE_NMAP:-true}"
ENABLE_NUCLEI="${ENABLE_NUCLEI:-true}"

mkdir -p "$OUT"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "=== EASM Scan: $DOMAIN_DISPLAY ==="

# Build subfinder args for multiple domains
SUBFINDER_ARGS=()
while IFS= read -r d; do
  [ -n "$d" ] && SUBFINDER_ARGS+=("-d" "$d")
done <<< "$DOMAINS"

# 1. Subdomain Discovery
log "[1/5] Subfinder – Subdomain Discovery..."
timeout 300 subfinder "${SUBFINDER_ARGS[@]}" -silent -o "$OUT/subdomains.txt" 2>/dev/null || true
COUNT=$(wc -l < "$OUT/subdomains.txt" 2>/dev/null || echo 0)
log "  Found $COUNT subdomains"

# 2. DNS Resolution
log "[2/5] dnsx – DNS Resolution..."
timeout 300 dnsx -l "$OUT/subdomains.txt" -silent -o "$OUT/resolved.txt" 2>/dev/null || true
COUNT=$(wc -l < "$OUT/resolved.txt" 2>/dev/null || echo 0)
log "  Resolved $COUNT hosts"

# 3. HTTP Probing
if [ "$ENABLE_HTTPX" = "true" ]; then
  log "[3/5] httpx – HTTP Probing + Tech Detection..."
  timeout 300 httpx -l "$OUT/resolved.txt" -silent \
    -title -status-code -tech-detect \
    -o "$OUT/http-results.txt" 2>/dev/null || true
  COUNT=$(wc -l < "$OUT/http-results.txt" 2>/dev/null || echo 0)
  log "  Found $COUNT live HTTP services"
else
  log "[3/5] httpx — disabled (enable_httpx=false), skipped"
fi

# Extract clean URL list for nuclei (httpx output: "https://host [200] [tech]")
grep -oE 'https?://[^ ]+' "$OUT/http-results.txt" 2>/dev/null | sort -u > "$OUT/urls.txt" || true

# 4. Port Scan
if [ "$ENABLE_NMAP" = "true" ]; then
  log "[4/5] nmap – Port Scan ($PORTS)..."
  if [ -s "$OUT/resolved.txt" ]; then
    timeout 600 nmap -iL "$OUT/resolved.txt" \
      -p "$PORTS" --open \
      -oN "$OUT/ports.txt" -T4 2>/dev/null || true
    log "  Port scan complete"
  else
    log "  No resolved hosts – skipping port scan"
  fi
else
  log "[4/5] nmap — disabled (enable_nmap=false), skipped"
fi

# 5. Nuclei
if [ "$ENABLE_NUCLEI" = "true" ]; then
  log "[5/5] Nuclei – Vulnerability Scan (severity: $SEVERITY)..."
  if [ -s "$OUT/urls.txt" ]; then
    timeout 1200 nuclei -l "$OUT/urls.txt" \
      -severity "$SEVERITY" \
      -o "$OUT/vulns.txt" -silent 2>/dev/null || true
    COUNT=$(wc -l < "$OUT/vulns.txt" 2>/dev/null || echo 0)
    log "  Found $COUNT findings"
  else
    log "  No HTTP targets – skipping Nuclei"
  fi
else
  log "[5/5] Nuclei — disabled (enable_nuclei=false), skipped"
fi

# Diff, notifications, and baseline storage are handled by the backend (notify.py)

log "=== Scan complete. Results: $OUT ==="
