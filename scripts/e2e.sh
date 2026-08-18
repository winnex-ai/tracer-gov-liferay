#!/usr/bin/env bash
# e2e.sh - Full end-to-end against a live tracer-gov-service.
# Usage: ./scripts/e2e.sh [base_url] [api_key]
set -euo pipefail

BASE="${1:-http://localhost:8601}"
KEY="${2:-change-me-in-production}"
AUTH="X-API-Key: $KEY"

echo "== 1/4 health =="
curl -s "$BASE/v1/health" | python3 -m json.tool

echo ""
echo "== 2/4 build (br-gv, 30 docs 32d) =="
python3 - <<'PY' > /tmp/tg_build.json
import numpy as np, json
rng = np.random.RandomState(7)
base = rng.randn(30, 32).astype(np.float32)
base /= np.linalg.norm(base, axis=1, keepdims=True)
print(json.dumps({"vectors": base.tolist(), "jurisdiction": "br-gv"}))
PY
curl -s -X POST "$BASE/v1/tracer/build" \
  -H "Content-Type: application/json" -H "$AUTH" -d @/tmp/tg_build.json | python3 -m json.tool

echo ""
echo "== 3/4 search (auditado) =="
python3 - <<'PY' > /tmp/tg_search.json
import numpy as np, json
rng = np.random.RandomState(7)
base = rng.randn(30, 32).astype(np.float32)
base /= np.linalg.norm(base, axis=1, keepdims=True)
q = base[0].tolist()
body = {"query": q, "k": 5, "jurisdiction": "br-gv",
        "requesting_agency": "SUS", "operator_id": "op-7", "role": "Analista",
        "source_database": "DATASUS", "sensitivity": "restricted",
        "purpose": "Analise epidemiologica"}
print(json.dumps(body))
PY
RESP=$(curl -s -X POST "$BASE/v1/tracer/search" \
  -H "Content-Type: application/json" -H "$AUTH" -d @/tmp/tg_search.json)
echo "$RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('audit_id :', d['audit_id'])
print('violations:', d['bound_violations'], '| sound:', d['sound'])
print('engine   :', d['engine_used'])
print('worm_hash:', d['worm'].get('block_hash','')[:16] + '...' if d['worm'].get('block_hash') else '(vazio)')
open('/tmp/tg_aid.txt','w').write(d['audit_id'])
"
AID=$(cat /tmp/tg_aid.txt)

echo ""
echo "== 4/4 proof + verify =="
curl -s "$BASE/v1/tracer/audit/$AID/proof" -H "$AUTH" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('PROOF  : sound=%s viol=%s pairs=%s excluded=%s' % (
    d['sound'], d['bound_violations'], d['bound_pairs'], d['total_excluded']))
print('         engine=%s' % d['engine_used'])
"
curl -s -X POST "$BASE/v1/tracer/verify" -H "Content-Type: application/json" -H "$AUTH" \
  -d "{\"audit_id\": \"$AID\"}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('VERIFY : found=%s chain_integrity=%s violations=%s' % (
    d['found'], d['chain_integrity_verified'], d['chain_violations']))
"
