# Tracer-GOV for Liferay — Practical User Guide

**Winnex AI | Klenio Padilha**
Winnex Brasil Solucoes Empresariais LTDA - CNPJ 58.364.637/0001-47
Contact: **pay@winnex.ai** | Website: **https://winnex.ai**
License: **Business Source License 1.1 (BSL 1.1)**

![Winnex AI Logo](https://winnex.ai/logo-petit_white.webp)

---

## Table of Contents

1. [What is Tracer-GOV?](#1-what-is-tracer-gov)
2. [What is it for? (finality)](#2-what-is-it-for-finality)
3. [What problem does it solve?](#3-what-problem-does-it-solve)
4. [The objective of the solution](#4-the-objective-of-the-solution)
5. [How it works (the mathematics)](#5-how-it-works-the-mathematics)
6. [What is the audit certificate?](#6-what-is-the-audit-certificate)
7. [Quick start (run it now)](#7-quick-start-run-it-now)
8. [How to use it (step by step)](#8-how-to-use-it-step-by-step)
9. [How to implement it in your Liferay project](#9-how-to-implement-it-in-your-liferay-project)
10. [The endpoints (API reference)](#10-the-endpoints-api-reference)
11. [Security and compliance](#11-security-and-compliance)
12. [Troubleshooting](#12-troubleshooting)
13. [Legal](#13-legal)

---

## 1. What is Tracer-GOV?

**Tracer-GOV** is a **government audit and search system with a mathematical
guarantee**, built for Liferay DXP/Portal. It lets a public-sector institution
search its document collections (laws, rulings, contracts, requests, public
data) and receive, for every search, a **mathematical proof** that no relevant
record was lost.

It is powered by the **Winnex Madhava** engine (C++20, `winnex-madhava` 1.8.8)
and adds the government layer: **WORM audit trail**, **9 jurisdictions**,
**digital signatures**, and **compliance reports** (LGPD, LAI, TCU, CGU,
GDPR, FOIA).

> **In one sentence:** Tracer-GOV turns *"the algorithm decided so"* into
> *"here is the mathematical proof that nothing relevant was excluded."*

---

## 2. What is it for? (finality)

Tracer-GOV exists for **accountability in the public sector**. It is used when
a government body needs to:

- **Prove** that a search did not miss a relevant document (for transparency
  requests, oversight audits, litigation).
- **Record** every search in an **immutable audit trail** (WORM) so that it
  can be reconstructed later: *who searched, what, when, with what
  guarantee.*
- **Comply** with national and international frameworks (LGPD Art. 20, LAI
  12.527/2011, TCU, CGU, GDPR Art. 22, FOIA).
- **Certify** the integrity of a decision after the fact (the audit
  certificate).

---

## 3. What problem does it solve?

### 3.1 The problem: "did we miss a document?"

Traditional search (keyword, or approximate ANN like HNSW/IVF) discards
candidates by **heuristic or probability**. In the public sector, a missed
document can be a **material legal risk**:

- A transparency request (LAI) where a relevant record was silently dropped.
- An oversight audit (TCU/CGU) where the search cannot prove completeness.
- A litigation e-discovery where a missing piece of evidence changes the case.

Approximate indexes cannot answer the question *"prove nothing relevant was
lost."* They can only say *"we think it is fine."*

### 3.2 The solution: proof, not probability

Tracer-GOV replaces the heuristic with a **per-document mathematical proof**.
Every record that is excluded carries a **Cauchy-Schwarz upper bound** showing
it mathematically could not be in the top-K. `bound_violations == 0` is the
guarantee.

---

## 4. The objective of the solution

The objective is to give **regulated government institutions** a search
system they can *defend*:

| Objective | How Tracer-GOV achieves it |
|---|---|
| **Completeness** | Cauchy-Schwarz proof: 0 bound violations, sound=true per query |
| **Auditability** | Every search is appended to a WORM (SHA3-256 hash chain, fsync) |
| **Accountability** | Who searched, what, when - reconstructed from the audit trail |
| **Compliance** | Localized reports per jurisdiction (LGPD/LAI/TCU/CGU/GDPR/FOIA) |
| **Trust** | The audit certificate makes the guarantee visible and verifiable |

---

## 5. How it works (the mathematics)

### 5.1 The engine

For a query vector `q` and a document vector `x` (unit norm), the
**Cauchy-Schwarz inequality** gives a per-document **upper bound**:

```
cos(x, q)  <=  <Px, Pq> + ||x_perp|| * ||q_perp||

P       = QR-orthogonal projection
x_perp  = x - P^T P x   (projection residual)
```

### 5.2 The guarantee

A document is **provably excluded** when:

```
upper_bound(x, q) < threshold(top-K)
```

By the inequality, such a document **cannot** be in the true top-K. So:

- **`bound_violations == 0`** means nothing relevant was lost (the guarantee).
- **`bound_pairs`** is the number of (document, bound) evaluations - the audit
  record size.
- **`sound == true`** is the same guarantee as a boolean flag.

### 5.3 The honest limit

The proof is of **exclusion, not relevance**: it proves a discarded document
could not be in the top-K by similarity; it does not judge whether the top-K
is "the best answer." Relevance depends on the embedding model that produced
the vectors.

---

## 6. What is the audit certificate?

The **audit certificate** is the visible, verifiable artifact of a search. It
contains:

| Field | Example | Meaning |
|---|---|---|
| `audit_id` | `e7da90c1...` | Unique identifier of the audited search |
| `jurisdiction` | `br-gv` | The policy jurisdiction that governed the search |
| `bound_violations` | `0` | The guarantee: nothing relevant was lost |
| `bound_pairs` | `30` | How many (doc, bound) pairs were evaluated |
| `total_excluded` | `10` | How many documents were provably excluded |
| `engine_used` | `winnex-madhava (pip, C++20 core)` | The engine that produced the proof |
| `worm_hash` | `a7d6db8c...` | The SHA3-256 block hash in the WORM chain |
| `sound` | `true` | The guarantee as a flag |

### What the certificate is FOR

- **Post-hoc validation**: months later, an auditor can retrieve the WORM
  record, verify the chain integrity, and confirm the search had the
  mathematical guarantee.
- **Transparency**: a citizen/regulator can see the proof behind a decision.
- **Non-repudiation**: the WORM chain + digital signature make the record
  tamper-evident.

### The verify endpoint

```
POST /v1/tracer/verify
{ "audit_id": "e7da90c1..." }

-> { "found": true, "chain_integrity_verified": true, "chain_violations": 0 }
```

If `chain_integrity_verified == true`, the certificate is intact.

---

## 7. Quick start (run it now)

```bash
# 1. Configure the API key
cp tracer-gov-service/.env.example tracer-gov-service/.env
#    edit .env -> WINNEX_TRACER_API_KEY=<strong-value>

# 2. Start the service
docker compose up -d

# 3. Verify
curl -s http://localhost:8601/v1/health
# {"status":"ok","engine":"tracer-gov + winnex-madhava 1.8.8",...}

# 4. Full live demo (build -> search -> proof -> verify)
./scripts/e2e.sh http://localhost:8601 change-me-in-production
```

### Expected demo output

```
== health ==          -> {"status":"ok","engine":"tracer-gov + winnex-madhava 1.8.8"}
== build ==           -> {"status":"built","jurisdiction":"br-gv","N":30,"dim":32}
== search ==          -> audit_id: ... | violations: 0 | sound: True
== proof + verify ==  -> PROOF: sound=True viol=0 pairs=30 | VERIFY: found=True chain=True
```

---

## 8. How to use it (step by step)

### 8.1 From the Liferay portlet

1. Log in to your Liferay portal.
2. Add the **Tracer-GOV** portlet (Add -> Widgets -> Winnex -> Tracer-GOV).
3. Choose the **jurisdiction** (br-gv, us-gv, eu-gv, ...).
4. Fill the government metadata:
   - **Requesting agency** (e.g. SUS)
   - **Operator ID** (who is running the search)
   - **Sensitivity** (public / restricted / secret)
   - **Role**, **source database**, **purpose**
5. Click **Run audited search**.
6. Read the result:
   - **Sound proof** banner (0 bound violations) - the guarantee.
   - The audit trail block (audit_id, jurisdiction, worm_hash).
   - The proof line (WORM verified).

### 8.2 Via the API (for integrators)

```bash
# Build an index for a jurisdiction
curl -X POST http://localhost:8601/v1/tracer/build \
  -H "Content-Type: application/json" -H "X-API-Key: <key>" \
  -d '{"vectors": [[...]], "jurisdiction": "br-gv"}'

# Audited search with government metadata
curl -X POST http://localhost:8601/v1/tracer/search \
  -H "Content-Type: application/json" -H "X-API-Key: <key>" \
  -d '{
    "query": [...],
    "k": 5,
    "jurisdiction": "br-gv",
    "requesting_agency": "SUS",
    "operator_id": "op-9",
    "sensitivity": "restricted",
    "purpose": "Epidemiological trend analysis"
  }'
```

---

## 9. How to implement it in your Liferay project

### 9.1 Architecture (3 OSGi bundles + microservice)

```
+-- Liferay DXP (OSGi) ----------------------------------------------------+
|  winnex-tracer-gov-portlet   <-- Portlet MVC (consumer)                  |
|       | @Reference                                                       |
|  winnex-tracer-gov-service   <-- HTTP client (X-API-Key)                 |
|       | @Reference                                                       |
|  winnex-tracer-gov-api       <-- public interfaces (the "pip")           |
+-----------------+--------------------------------------------------------+
                  | HTTP/REST
                  v
  tracer-gov-service (FastAPI, port 8601)
     +-- TracerEngine (winnex-madhava 1.8.8)
     +-- WORM (SHA3-256) + 9 jurisdictions + compliance
```

### 9.2 Consume the service from any Liferay module

```java
// Inject the OSGi service (no HTTP plumbing in your code)
@Reference
protected volatile TracerGovService tracerGovService;

// Build a search request
TracerGovSearchRequest request = new TracerGovSearchRequest();
request.setQuery(queryVector);            // List<Float>
request.setK(5);
request.setJurisdiction("br-gv");
request.setRequestingAgency("SUS");
request.setSensitivity("restricted");

// Run the audited search
TracerGovSearchResponse response = tracerGovService.search(request);

// The guarantee
response.isSound();          // true -> 0 bound violations
response.getBoundViolations();
response.getWormHash();
```

### 9.3 Data contract (the vectors)

The Madhava engine does **not** embed text. It receives **float32 vectors**.
Your integration must transform documents into unit-norm vectors first (via an
embedding model). See the Tracer-MED **Model Integration Guide** for the full
float32 contract.

---

## 10. The endpoints (API reference)

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/v1/health` | Engine status |
| `GET` | `/v1/stats` | Simple metrics (requests, builds, searches, latency) |
| `POST` | `/v1/tracer/build` | Build the Madhava index for a jurisdiction/mode |
| `POST` | `/v1/tracer/search` | **Audited search** (writes WORM + proof) |
| `GET` | `/v1/tracer/audit/{id}` | Retrieve an audit record |
| `GET` | `/v1/tracer/audit/{id}/proof` | The mathematical proof |
| `POST` | `/v1/tracer/verify` | Verify a WORM record |
| `GET` | `/v1/worm/verify` | Full WORM chain integrity |

Auth: header `X-API-Key` (constant-time). Mode `internal` also requires an
internal credential (fail-closed).

---

## 11. Security and compliance

- **API key**: required on all `/v1/*` endpoints (constant-time comparison,
  fail-closed when configured).
- **No citizen-data leaks**: the proof and WORM store audit metadata, not
  sensitive payloads.
- **WORM**: append-only JSONL + SHA3-256 hash chain + fsync. Tampering is
  detectable.
- **Jurisdictions**: policies inherit global -> region -> country, defining
  required fields, sensitivity, retention and signature algorithms.
- **Compliance reports**: LGPD, LAI, TCU, CGU, GDPR, FOIA - self-assessment
  templates, not certifications.

---

## 12. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | Wrong or missing API key | Set `WINNEX_TRACER_API_KEY` and send `X-API-Key` |
| `409 No index built` | Corpus not indexed for that jurisdiction | `POST /v1/tracer/build` first |
| `503 Internal mode not configured` | mode=internal without credential | Set `WINNEX_TRACER_INTERNAL_CREDENTIAL` |
| Portlet shows "service unreachable" | Microservice not reachable | Check the container and the `baseUrl` in System Settings |
| `bound_violations > 0` | Data does not respect the float32 contract | Normalize vectors to unit norm; use the same embedding model |
| `chain_integrity_verified: false` | WORM tampered | Investigate immediately; check the WORM path for external writes |

---

## 13. Legal

- **Business Source License 1.1 (BSL 1.1)** - source-available, not OSI
  open-source.
- Free for Brazilian government agencies (Additional Use Grant).
- Becomes GPL v2.0+ on **2036-01-01**.
- Commercial use requires a license agreement with Winnex AI.
- Compliance reports are **self-assessment templates**, not certifications.

---

*Winnex AI -- "Replace probability with proof, in the service of government."*
*BSL 1.1 | pay@winnex.ai | CNPJ 58.364.637/0001-47*
