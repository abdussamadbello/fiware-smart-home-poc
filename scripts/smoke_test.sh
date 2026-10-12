#!/usr/bin/env bash
# Smoke-test FIWARE Smart Home PoC endpoints (host network).
set -euo pipefail
ORION=${ORION_PUBLIC_URL:-http://localhost:1026}
IOTA_N=${IOTA_NORTH:-http://localhost:4041}
QL=${QL_URL:-http://localhost:8668}
KEYROCK=${KEYROCK_PUBLIC_URL:-http://localhost:3005}
WEB=${WEBAPP_URL:-http://localhost:8080}
SVC=${FIWARE_SERVICE:-smartHome}

echo "=== Smoke test $(date) ==="
fail=0
check() {
  local name="$1" url="$2"
  if curl -sf -o /tmp/smoke_body -w "%{http_code}" "$url" | grep -qE '^(200|201|204)'; then
    echo "OK  $name"
  else
    code=$(curl -s -o /tmp/smoke_body -w "%{http_code}" "$url" || echo err)
    echo "FAIL $name ($code) — $(head -c 120 /tmp/smoke_body 2>/dev/null)"
    fail=$((fail+1))
  fi
}

check "Orion /version" "$ORION/version"
check "IoT Agent /iot/about" "$IOTA_N/iot/about"
check "Web /health" "$WEB/health"
check "Web /login" "$WEB/login"

# Optional services
curl -sf "$QL/version" >/dev/null 2>&1 && echo "OK  QuantumLeap /version" || echo "SKIP QuantumLeap (not up)"
curl -sf "$KEYROCK/version" >/dev/null 2>&1 && echo "OK  Keyrock /version" || echo "SKIP Keyrock (not up)"

echo "--- Orion entities (Fiware-Service=$SVC) ---"
curl -s -H "Fiware-Service: $SVC" -H "Fiware-ServicePath: /" \
  "$ORION/v2/entities?options=count&limit=5" -D - -o /tmp/ents.json | grep -i fiware-total || true
head -c 400 /tmp/ents.json; echo

echo "--- Login page contains Smart Home ---"
grep -q "Smart Home Login" <(curl -s "$WEB/login") && echo "OK login UI" || { echo "FAIL login UI"; fail=$((fail+1)); }

echo "=== Done (failures=$fail) ==="
exit $fail
