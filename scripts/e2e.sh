#!/usr/bin/env bash
# e2e.sh - Full end-to-end for tracer-gov-service: Liferay bridge →
# winnex-ai-normalize (provider registration + text embedding) →
# winnex-madhava → winnex-tracer commitment/WORM.
# Uses REAL data (arXiv d=1536) and REAL embedding providers.
#
# Usage: ./scripts/e2e.sh [base_url] [api_key] [embedding_url] [embedding_model] [admin_key]
set -euo pipefail

BASE="${1:-http://localhost:8601}"
KEY="${2:-change-me-in-production}"
EMB_URL="${3:-http://localhost:8102}"
EMB_MODEL="${4:-BAAI/bge-m3}"
ADMIN_KEY="${5:-change-me-in-production}"
AUTH="X-API-Key: $KEY"

echo "== 1/5 health =="
curl -s "$BASE/v1/health" | python3 -m json.tool

echo ""
echo "== 2/5 register embedding provider (via the Liferay form contract) =="
curl -s -X POST "$BASE/v1/normalize/providers" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -d "{\"name\": \"qwen3\", \"base_url\": \"$EMB_URL\", \"model\": \"$EMB_MODEL\", \"dim\": 1024, \"priority\": 1}" | python3 -m json.tool

echo ""
echo "== 3/5 normalize real government text → vectors =="
python3 - "$BASE" <<'PY' > /tmp/tg_embed.json
import sys, json, urllib.request
base = sys.argv[1]
docs = [
    "Lei 12.527 de 2011 - acesso a informacao publica. Regula o direito fundamental de acesso.",
    "Decreto regulamentador da transparencia ativa na administracao publica federal.",
    "Parecer sobre licitacao de servicos de tecnologia da informacao.",
    "Norma de auditoria interna para orgaos de controle governamental.",
]
req = urllib.request.Request(f"{base}/v1/normalize/embed",
    data=json.dumps({"input": docs}).encode(),
    headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=30) as resp:
    d = json.loads(resp.read())
print(json.dumps({"vectors": [x["embedding"] for x in d["data"]],
                  "jurisdiction": "br-gv"}))
PY
python3 -c "
import json
d = json.load(open('/tmp/tg_embed.json'))
print(f'  {len(d[\"vectors\"])} documentos normalizados (d={len(d[\"vectors\"][0])})')
"

echo ""
echo "== 4/5 build + audited search (commitment + WORM) =="
curl -s -X POST "$BASE/v1/tracer/build" \
  -H "Content-Type: application/json" -H "$AUTH" -d @/tmp/tg_embed.json | python3 -m json.tool

python3 - "$BASE" <<'PY' > /tmp/tg_search.json
import sys, json, urllib.request
base = sys.argv[1]
req = urllib.request.Request(f"{base}/v1/normalize/embed",
    data=json.dumps({"input": ["acesso a informacao e transparencia publica"]}).encode(),
    headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=30) as resp:
    d = json.loads(resp.read())
body = {"query": d["data"][0]["embedding"], "k": 5, "jurisdiction": "br-gv",
        "metadata": {"orgao_requisitante": "CGU", "cpf": "000.000.000-00",
                     "funcao": "Auditor", "base_de_dados": "LEGISLACAO",
                     "sensibilidade": "public", "finalidade": "Auditoria de transparencia"}}
print(json.dumps(body))
PY
RESP=$(curl -s -X POST "$BASE/v1/tracer/search" \
  -H "Content-Type: application/json" -H "$AUTH" -d @/tmp/tg_search.json)
echo "$RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('audit_id :', d['audit_id'])
print('violations:', d['bound_violations'], '| sound:', d['sound'])
print('excluded :', d.get('total_excluded'))
print('engine   :', d['engine_used'])
print('threshold:', d.get('global_threshold', 'n/a'))
open('/tmp/tg_aid.txt','w').write(d['audit_id'])
"
AID=$(cat /tmp/tg_aid.txt)

echo ""
echo "== 5/5 proof + verify =="
curl -s "$BASE/v1/tracer/audit/$AID/proof" -H "$AUTH" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('PROOF  : sound=%s viol=%s pairs=%s excluded=%s' % (
    d['sound'], d['bound_violations'], d['bound_pairs'], d['total_excluded']))
"
curl -s -X POST "$BASE/v1/tracer/verify" -H "Content-Type: application/json" -H "$AUTH" \
  -d "{\"audit_id\": \"$AID\"}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('VERIFY : found=%s chain_integrity=%s violations=%s' % (
    d['found'], d['chain_integrity_verified'], d['chain_violations']))
"
