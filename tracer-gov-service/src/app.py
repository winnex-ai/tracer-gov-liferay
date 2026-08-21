"""
tracer-gov-service — Government Audit Bridge (FastAPI) for Liferay
===================================================================
HTTP service exposing the real Tracer-GOV engine (TracerEngine + WORM +
jurisdictions + compliance) to the Liferay OSGi bridge.

It reuses the published `tracer-gov` package (54 tests passing). Endpoints:

  POST /v1/tracer/build   - build the Madhava index for a jurisdiction/mode
  POST /v1/tracer/search  - audited search (writes WORM + proof)
  GET  /v1/tracer/audit/{id}        - retrieve audit record
  GET  /v1/tracer/audit/{id}/proof  - the mathematical proof
  POST /v1/tracer/verify  - verify WORM chain integrity
  GET  /v1/worm/verify    - full WORM integrity check
  GET  /v1/stats          - simple metrics for monitoring
  GET  /v1/health         - engine status

Security: header X-API-Key (constant-time), configured via env vars.
Mode "internal" requires an internal credential (fail-closed).

License: Business Source License 1.1 (BSL 1.1)
Copyright (c) 2026 Winnex AI - Winnex Brasil Solucoes Empresariais LTDA (CNPJ 58.364.637/0001-47)
Contact: pay@winnex.ai
"""
import logging
import os
import time
from typing import Any, Dict, List, Optional

import numpy as np

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# Report the ACTUAL installed engine version (winnex-madhava pip), not a
# hardcoded string — the old "1.9.1" health string was misleading (the motor
# in use is whatever winnex-madhava is installed).
def _engine_version() -> str:
    try:
        import winnex_madhava as _wm
        return "winnex-madhava " + str(getattr(_wm, "__version__", "?"))
    except Exception:
        return "winnex-madhava ?"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tracer-gov-bridge")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Tracer-GOV Bridge (Liferay)",
    version="1.0.0",
    description="Government audit with mathematical proof for Liferay Tracer-GOV.",
    contact={"name": "Winnex AI | Klenio Padilha", "email": "pay@winnex.ai"},
    license_info={
        "name": "Business Source License 1.1",
        "url": "https://www.mariadb.com/bsl11/",
    },
)

# ---------------------------------------------------------------------------
# Security: API key (constant-time) - fail-closed when configured
# ---------------------------------------------------------------------------
_API_KEY = os.environ.get("WINNEX_TRACER_API_KEY", "change-me-in-production")
_INTERNAL_CREDENTIAL = os.environ.get("WINNEX_TRACER_INTERNAL_CREDENTIAL", "")


def _constant_time_eq(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a.encode(), b.encode())


def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")):
    """FastAPI dependency: enforce the API key on protected endpoints."""
    if not _API_KEY:
        return  # disabled -> open (dev only)
    if not x_api_key or not _constant_time_eq(x_api_key, _API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _require_internal_credential(provided: str):
    expected = _INTERNAL_CREDENTIAL
    if not expected:
        raise HTTPException(
            503, "Internal mode not configured (WINNEX_TRACER_INTERNAL_CREDENTIAL not set).")
    if not provided or not _constant_time_eq(provided, expected):
        raise HTTPException(401, "Invalid internal credential.")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
_METRICS = {
    "total_requests": 0,
    "total_builds": 0,
    "total_searches": 0,
    "total_latency_ms": 0.0,
    "avg_latency_ms": 0.0,
    "total_bound_violations": 0,
    "started_at": time.time(),
}


def _record(latency_ms: float, violations: int = 0, search: bool = True):
    m = _METRICS
    m["total_requests"] += 1
    m["total_searches" if search else "total_builds"] += 1
    m["total_latency_ms"] += latency_ms
    m["total_bound_violations"] += violations
    m["avg_latency_ms"] = round(m["total_latency_ms"] / max(m["total_requests"], 1), 4)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class BuildRequest(BaseModel):
    vectors: List[List[float]]
    jurisdiction: str = "global"
    mode: str = "public"
    state: str = ""
    internal_credential: str = ""


class SearchRequest(BaseModel):
    query: List[float]
    k: int = 10
    jurisdiction: str = "global"
    mode: str = "public"
    state: str = ""
    internal_credential: str = ""
    requesting_agency: str = ""
    operator_id: str = ""
    role: str = ""
    source_database: str = ""
    sensitivity: str = "restricted"
    purpose: str = ""


class VerifyRequest(BaseModel):
    audit_id: str


# ---------------------------------------------------------------------------
# Engine registry (per jurisdiction + mode, like the tracer-gov API)
# ---------------------------------------------------------------------------
_engines: Dict[str, Any] = {}
_engine_meta: Dict[str, Dict[str, Any]] = {}


def _engine_key(jurisdiction: str, mode: str, state: str = "") -> str:
    return f"{jurisdiction}|{mode}|{state}"


def _get_engine(jurisdiction: str, mode: str, state: str = ""):
    key = _engine_key(jurisdiction, mode, state)
    if key not in _engines:
        from winnex_tracer.gov.core import TracerEngine, Config
        cfg = Config(
            jurisdiction=jurisdiction,
            mode=mode,
            state=state,
            internal_credential="" if mode != "internal" else _INTERNAL_CREDENTIAL,
            worm_base_path=os.environ.get(
                "TRACER_GOV_WORM_PATH", "/var/lib/tracer-gov/worm"),
        )
        engine = TracerEngine(cfg)
        _engines[key] = engine
        _engine_meta[key] = {"jurisdiction": jurisdiction, "mode": mode, "state": state}
        logger.info("engine created: %s", key)
    return _engines[key]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/v1/health")
def health():
    return {
        "status": "ok",
        "engine": "tracer-gov + " + _engine_version(),
        "engines": list(_engines.keys()),
        "timestamp": time.time(),
    }


@app.get("/v1/stats")
def stats(_: str = Depends(require_api_key)):
    m = dict(_METRICS)
    m["uptime_s"] = round(time.time() - m["started_at"], 1)
    return m


@app.post("/v1/tracer/build", dependencies=[Depends(require_api_key)])
def build(req: BuildRequest):
    if not req.vectors or not req.vectors[0]:
        raise HTTPException(422, "vectors must be a non-empty matrix")

    mode = (req.mode or "public").lower()
    if mode == "internal":
        _require_internal_credential(req.internal_credential or "")

    t0 = time.time()
    engine = _get_engine(req.jurisdiction or "global", mode, req.state or "")
    vectors = np.array(req.vectors, dtype=np.float32)
    engine.build(vectors)
    latency = (time.time() - t0) * 1000
    _record(latency, search=False)

    return {
        "status": "built",
        "jurisdiction": engine.jurisdiction_code,
        "mode": engine.config.mode,
        "N": int(getattr(engine, "_N", vectors.shape[0])),
        "dim": int(vectors.shape[1]),
        "engine": "tracer-gov + " + _engine_version(),
        "latency_ms": round(latency, 3),
    }


@app.post("/v1/tracer/search", dependencies=[Depends(require_api_key)])
def search(req: SearchRequest):
    mode = (req.mode or "public").lower()
    if mode == "internal":
        _require_internal_credential(req.internal_credential or "")

    engine = _get_engine(req.jurisdiction or "global", mode, req.state or "")
    if getattr(engine, "_N", 0) == 0:
        raise HTTPException(
            409, "No index built. Call POST /v1/tracer/build first.")

    from winnex_tracer.gov.core import GovMetadata

    metadata_data = {
        "requesting_agency": req.requesting_agency,
        "operator_id": req.operator_id,
        "role": req.role,
        "source_database": req.source_database,
        "sensitivity": req.sensitivity,
        "purpose": req.purpose,
    }
    metadata_data = {k: v for k, v in metadata_data.items() if v}

    query = np.array(req.query, dtype=np.float32)
    metadata = GovMetadata(data=metadata_data)
    t0 = time.time()
    result = engine.search_with_audit(query, metadata, k=req.k)
    latency = (time.time() - t0) * 1000

    _record(latency, int(result.violations_64d), search=True)

    # Persist to WORM (append-only + hash chain) so audit/proof/verify
    # return real data. Persistence must never fail the search.
    receipt = {}
    try:
        from winnex_tracer.persistence import WormStorage
        worm = WormStorage(base_path=engine.config.worm_base_path)

        def _native(v):
            if isinstance(v, (list, tuple)):
                return [_native(x) for x in v]
            if isinstance(v, dict):
                return {k: _native(x) for k, x in v.items()}
            return v.item() if hasattr(v, "item") else v

        if result.commitment is not None:
            # --- PRODUCTION (1.9.2+) : the signed lightweight commitment.
            # The motor returned a ~500-byte AuditCommitment already signed
            # with Ed25519 by the compliance layer (core.commitment). The WORM
            # stores the SIGNED commitment UNCHANGED (so the signature remains
            # valid) plus a _ctx block with the contextual government fields.
            # verify_record operates on the `commitment` sub-block — the
            # _ctx/metadata/result fields are NOT part of the signed payload.
            record = {
                "commitment": result.commitment,   # the signed payload (intact)
                "_ctx": {
                    "jurisdiction": result.jurisdiction,
                    "mode": result.mode,
                    "state": result.state,
                    "language": result.language,
                    "metadata": metadata.to_dict(),
                    "result": {
                        "indices": _native(result.indices),
                        "scores": [round(float(s), 6) for s in result.scores],
                        "bound_violations": int(result.violations_64d),
                        "bound_pairs": int(result.bound_pairs),
                        "total_excluded": int(result.total_excluded),
                        "engine_used": result.engine_used,
                        "latency_ms": round(latency, 3),
                    },
                    # boundary sample (light) — NOT the full certificate
                    "audit": [
                        {
                            "doc_id": r.doc_id,
                            "upper_bound": float(r.upper_bound),
                            "threshold": float(r.threshold),
                            "excluded": bool(r.excluded),
                            "verdict": r.verdict,
                        }
                        for r in result.audit
                    ],
                },
            }
        else:
            # Legacy path (< 1.9.2 or non-madhava backend): full record.
            record = {
                "audit_id": metadata.audit_id,
                "jurisdiction": result.jurisdiction,
                "mode": result.mode,
                "state": result.state,
                "language": result.language,
                "metadata": metadata.to_dict(),
                "result": {
                    "indices": _native(result.indices),
                    "scores": [round(float(s), 6) for s in result.scores],
                    "bound_violations": int(result.violations_64d),
                    "bound_pairs": int(result.bound_pairs),
                    "total_excluded": int(result.total_excluded),
                    "engine_used": result.engine_used,
                    "latency_ms": round(latency, 3),
                },
                "audit": [
                    {
                        "doc_id": r.doc_id,
                        "upper_bound": float(r.upper_bound),
                        "threshold": float(r.threshold),
                        "excluded": bool(r.excluded),
                        "verdict": r.verdict,
                    }
                    for r in result.audit
                ],
                "signature": result.signature,
                "signature_algorithm": result.signature_algorithm,
            }
        receipt = worm.append(record)
    except Exception as e:
        logger.warning("Tracer-GOV bridge: WORM persist failed: %s", e)
        receipt = {}

    return {
        "audit_id": metadata.audit_id,
        "jurisdiction": result.jurisdiction,
        "mode": result.mode,
        "state": result.state,
        "language": result.language,
        "indices": [int(i) for i in result.indices],
        "scores": [round(float(s), 6) for s in result.scores],
        "bound_violations": int(result.violations_64d),
        "bound_pairs": int(result.bound_pairs),
        "total_excluded": int(result.total_excluded),
        "engine_used": result.engine_used,
        "latency_ms": round(latency, 3),
        "sound": int(result.violations_64d) == 0,
        "signature": result.signature,
        "signature_algorithm": result.signature_algorithm,
        "worm": {
            "block_hash": receipt.get("worm_hash", ""),
            "path": receipt.get("worm_path", ""),
        },
        "audit": [
            {
                "doc_id": r.doc_id,
                "upper_bound": float(r.upper_bound),
                "threshold": float(r.threshold),
                "excluded": bool(r.excluded),
                "verdict": r.verdict,
            }
            for r in result.audit
        ],
    }


@app.get("/v1/tracer/audit/{audit_id}")
def get_audit(audit_id: str, _: str = Depends(require_api_key)):
    # Reuse the WORM store to fetch the audit record (like tracer-gov API).
    from winnex_tracer.persistence import WormStorage
    for key, engine in _engines.items():
        try:
            worm = WormStorage(base_path=engine.config.worm_base_path)
            rec = _find_audit(worm, audit_id)
            if rec:
                return rec
        except Exception as e:
            logger.warning("audit lookup %s: %s", key, e)
    raise HTTPException(404, f"Audit {audit_id} not found")


@app.get("/v1/tracer/audit/{audit_id}/proof")
def get_proof(audit_id: str, _: str = Depends(require_api_key)):
    from winnex_tracer.persistence import WormStorage
    for engine in _engines.values():
        try:
            worm = WormStorage(base_path=engine.config.worm_base_path)
            rec = _find_audit(worm, audit_id)
            if rec:
                result = rec.get("result", {})
                sound = int(result.get("bound_violations", 0)) == 0
                return {
                    "report_type": "TRACER_GOV_PROOF",
                    "audit_id": audit_id,
                    "sound": sound,
                    "bound_violations": int(result.get("bound_violations", 0)),
                    "bound_pairs": int(result.get("bound_pairs", 0)),
                    "total_excluded": int(result.get("total_excluded", 0)),
                    "engine_used": result.get("engine_used", ""),
                    "latency_ms": result.get("latency_ms", 0),
                    "jurisdiction": rec.get("jurisdiction"),
                    "mode": rec.get("mode"),
                    "worm_hash": rec.get("block_hash", ""),
                    "disclaimer": (
                        "Proof of exclusion, not of relevance. Every excluded "
                        "document carries a Cauchy-Schwarz proof it could not "
                        "be in the top-K."),
                }
        except Exception as e:
            logger.warning("proof lookup: %s", e)
    raise HTTPException(404, f"Audit {audit_id} not found")


@app.post("/v1/tracer/verify", dependencies=[Depends(require_api_key)])
def verify_audit(req: VerifyRequest):
    from winnex_tracer.persistence import WormStorage
    for engine in _engines.values():
        try:
            worm = WormStorage(base_path=engine.config.worm_base_path)
            rec = _find_audit(worm, req.audit_id)
            if rec:
                integrity = worm.verify_integrity()
                return {
                    "audit_id": req.audit_id,
                    "found": True,
                    "chain_integrity_verified": integrity["chain_integrity_verified"],
                    "chain_violations": integrity["violations"],
                }
        except Exception as e:
            logger.warning("verify lookup: %s", e)
    raise HTTPException(404, f"Audit {req.audit_id} not found")


@app.get("/v1/worm/verify", dependencies=[Depends(require_api_key)])
def worm_verify():
    from winnex_tracer.persistence import WormStorage
    results = {}
    for key, engine in _engines.items():
        try:
            worm = WormStorage(base_path=engine.config.worm_base_path)
            integrity = worm.verify_integrity()
            results[key] = {
                "total_blocks": integrity["total_blocks"],
                "violations": integrity["violations"],
                "chain_integrity_verified": integrity["chain_integrity_verified"],
            }
        except Exception as e:
            results[key] = {"error": str(e)}
    return results


@app.get("/v1/audit/public-key", dependencies=[Depends(require_api_key)])
def audit_public_key():
    """The Ed25519 public verify key — distribute to auditors.

    Auditors use this to verify the signature on any WORM commitment record
    (non-repudiation). It is derived from the private key at deploy time and
    never changes while the same key is in use.
    """
    try:
        from winnex_tracer.core import public_key_hex
        return {
            "public_key_hex": public_key_hex(),
            "algorithm": "Ed25519",
            "note": "Use to verify signature_hex on any tracer-gov commitment record.",
        }
    except Exception as e:
        raise HTTPException(503, f"Signing key not configured: {e}")


@app.post("/v1/audit/verify-signature", dependencies=[Depends(require_api_key)])
def audit_verify_signature(req: VerifyRequest):
    """Verify the Ed25519 signature of a stored commitment record.

    Finds the record by audit_id in the WORM and verifies:
      1. the Ed25519 signature (non-repudiation — the record was signed by
         the trusted compliance service, not forged by a compromised engine),
      2. the integrity hash (C++→Python consistency).
    """
    from winnex_tracer.persistence import WormStorage
    for engine in _engines.values():
        try:
            worm = WormStorage(base_path=engine.config.worm_base_path)
            rec = _find_audit(worm, req.audit_id)
            if rec:
                from core.commitment import verify_record, public_key_hex
                pk = public_key_hex()
                # New format: the signed commitment is the `commitment` sub-block.
                # Legacy: the record itself carries signature_hex at the top.
                if isinstance(rec.get("commitment"), dict):
                    target = dict(rec["commitment"])
                else:
                    target = dict(rec)
                v = verify_record(target, pk)
                return {"audit_id": req.audit_id, **v}
        except Exception as e:
            logger.warning("verify-signature lookup: %s", e)
    raise HTTPException(404, f"Audit {req.audit_id} not found")


def _find_audit(worm, audit_id: str) -> Optional[Dict[str, Any]]:
    """Search the WORM records for an audit_id.

    Uses the WormStorage O(log N) SQLite index when available; falls back to
    the O(N) JSONL scan (the index and the chain share the same source of
    truth). This replaces the previous linear scan (Gargalo #8).
    """
    if not worm.base_path.exists():
        return None
    rec = worm.get_audit_id(audit_id)
    if rec is not None:
        return rec
    # Belt-and-suspenders: legacy records not yet indexed → linear scan.
    import json
    for f in sorted(worm.base_path.rglob("records.jsonl")):
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    block = json.loads(line)
                except json.JSONDecodeError:
                    continue
                data = block.get("data", {})
                if data.get("audit_id") == audit_id:
                    return {**block, **data}
    return None


# ---------------------------------------------------------------------------
# Normalization integration (winnex-ai-normalize) — provider registration
# and text → vector normalization, so the Liferay form can register embedding
# providers and any client can feed text to the Madhava engine.
# ---------------------------------------------------------------------------
class _ProviderIn(BaseModel):
    name: str
    type: str = "openai_compat"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    api_key_env: str = ""
    dim: int = 0
    timeout: float = 20.0
    priority: int = 10
    enabled: bool = True


class _NormalizeRequest(BaseModel):
    input: List[str]
    model: str = ""


def _normalize_admin_required(authorization: str = Header(default="", alias="Authorization")):
    from winnex_ai_normalize.core.provider_registry import require_admin_key
    try:
        require_admin_key(authorization)
    except PermissionError as e:
        raise HTTPException(403, str(e))


@app.get("/v1/normalize/providers")
def list_providers(authorization: str = Header(default="", alias="Authorization")):
    """List registered embedding providers (secrets masked)."""
    _normalize_admin_required(authorization)
    from winnex_ai_normalize.core.provider_registry import get_registry
    return {"providers": get_registry().list()}


@app.post("/v1/normalize/providers")
def upsert_provider(provider: _ProviderIn,
                    authorization: str = Header(default="", alias="Authorization")):
    """Register an embedding provider via the Liferay form (admin key)."""
    _normalize_admin_required(authorization)
    from winnex_ai_normalize.core.provider_registry import get_registry
    try:
        cfg = get_registry().upsert(provider.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"status": "registered", "provider": cfg.name}


@app.post("/v1/normalize/embed")
def normalize_embed(req: _NormalizeRequest):
    """Text → float32 vectors (via the registered embedding provider)."""
    from winnex_ai_normalize.core.embedding import get_embedding_service
    try:
        vecs = get_embedding_service().embed_texts(req.input)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return {
        "data": [
            {"embedding": vecs[i].tolist(), "index": i, "dim": int(vecs.shape[1])}
            for i in range(len(vecs))
        ],
        "model": req.model or "winnex-ai-normalize",
        "normalized": True,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8601)
