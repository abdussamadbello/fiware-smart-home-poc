#!/usr/bin/env bash
# Best-effort Keyrock OAuth app + demo users via Keyrock HTTP API.
set -euo pipefail
KEYROCK=${KEYROCK_PUBLIC_URL:-http://localhost:3005}
ADMIN_EMAIL=${IDM_ADMIN_EMAIL:-admin@test.com}
ADMIN_PASS=${IDM_ADMIN_PASS:-1234}
CLIENT_ID=${OAUTH2_CLIENT_ID:-smart-home-app}
CLIENT_SECRET=${OAUTH2_CLIENT_SECRET:-smart-home-secret-change-me}

echo "Authenticating to Keyrock..."
TOKEN=$(curl -s -i -X POST "$KEYROCK/v1/auth/tokens" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASS\"}" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-subject-token"{print $2}')
if [[ -z "${TOKEN:-}" ]]; then
  echo "Could not get X-Subject-Token — Keyrock may still be seeding. Retry later."
  exit 1
fi
echo "Token obtained."

# Create application (may fail if exists)
curl -s -X POST "$KEYROCK/v1/applications" \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: $TOKEN" \
  -d "{
    \"application\": {
      \"name\": \"Smart Home Web\",
      \"description\": \"Thesis PoC web app\",
      \"redirect_uri\": \"http://localhost:8080/auth/callback\",
      \"url\": \"http://localhost:8080\",
      \"grant_type\": \"password,authorization_code,client_credentials\",
      \"token_types\": \"permanent\"
    }
  }" | tee /tmp/keyrock_app.json
echo
echo "Note: If Keyrock generated a different client id/secret, update .env OAUTH2_* accordingly."
echo "Demo users can also be created in Keyrock UI at $KEYROCK — web app has local fallback users."
