# Tracer-GOV for Liferay

**Winnex AI | Klenio Padilha**
Winnex Brasil Solucoes Empresariais LTDA - CNPJ 58.364.637/0001-47
Contact: **pay@winnex.ai** | Website: **https://winnex.ai**
License: **Business Source License 1.1 (BSL 1.1)**

![Winnex AI Logo](https://winnex.ai/logo-petit_white.webp)

---

## For developers

This README is written for the **developer who will integrate Tracer-GOV**
into a Liferay project (or call the engine from any JVM/Python service). It
shows, with working code:

- How to **start** the engine.
- How to **call the API** (cURL).
- How to **consume the OSGi service** from a Liferay module.
- How to **read the mathematical proof** and the audit trail.

For the product/end-user perspective, see [USER_GUIDE.md](docs/USER_GUIDE.md).

---

## What you get

| Component | What it does for you |
|---|---|
| **`tracer-gov-service`** (FastAPI, port 8601) | The engine: audited search with Cauchy-Schwarz proof + WORM audit trail |
| **`winnex-tracer-gov-api`** (OSGi) | The public interface (`TracerGovService`) you `@Reference` |
| **`winnex-tracer-gov-service`** (OSGi) | HTTP bridge from Liferay to the FastAPI engine (configurable, API key) |
| **`winnex-tracer-gov-portlet`** (OSGi) | Ready-made UI: jurisdiction form + government metadata + proof |

---

## Important: Tracer-GOV is NOT a plug-and-play RAG solution

> **Please read this before you buy or deploy.**

**Tracer-GOV is Madhava made easy for government in Liferay.** It is the
guaranteed-retrieval layer + the government audit layer + the Liferay UI
already built: the portlet, the WORM audit trail, the 9 jurisdictions, the
digital signature, the soundness proof and the compliance metadata all work
out of the box. What is **not** included is the data side (embeddings,
encoding, tuning, optional LLM answers). It is therefore **not** a complete,
out-of-the-box RAG (Retrieval-Augmented Generation) product. In particular:

- **You must generate the embeddings yourself.** The Madhava engine does **not**
  embed text. `POST /v1/tracer/build` receives `vectors`, and
  `POST /v1/tracer/search` receives a `query` vector -- both already-embedded
  **float32 vectors** (unit-norm for cosine). There is no "give me text, get me
  a vector" endpoint. See the
  [Tracer-MED Model Integration Guide](../tracer-med-liferay/docs/MODEL_INTEGRATION_GUIDE.md)
  for the exact float32 contract.
- **RAG answers (LLM-generated responses) are not included.** Tracer-GOV
  returns the ranked records **plus the mathematical proof and the WORM
  receipt**; it does not generate an answer paragraph from them.

In the public sector this distinction is **material, not cosmetic**: the proof
guarantees *completeness* (nothing relevant was excluded), but relevance
itself is decided by the embedding model that produced the vectors. If the
embedding is wrong for your language/domain, the top-K is wrong even though
`bound_violations == 0`. Who generates the vectors is therefore part of the
accountability chain.

### Why there is no plug-and-play: your data decides

"Plug and play" would mean every government institution has identical data --
same language, same legal domain, same structured fields, same scale, same
ingestion source, same jurisdiction. No two do. Each of the scenarios below
changes at least one component of the pipeline, and it is exactly **this
variability that Winnex solves for you** (see "Your options", below).

| Scenario | What it forces you to decide |
|---|---|
| **Free-text legal documents** (laws, rulings, contracts, requests, jurisprudence) | Which embedding model, and for which **language and legal domain** (PT juridico vs EN legal; normas vs contratos vs jurisprudencia). Domain mismatch silently degrades retrieval. Model choice, dimension and token limits are decisions, not defaults. |
| **Structured-only data** (dates, values, process numbers, agency codes) | A numeric **feature vector** design: how to clip and scale each field, and what "similarity" means in *your* feature space. Different scaling = different results. |
| **Categorical data** (state/UF, agency, document type, classification / secrecy level) | A frozen **codebook** (which values exist in *your* org) and a one-hot/embedding encoding. New values added later change the space and require re-indexing. |
| **Mixed records** (text + government metadata) | How to combine the signals into **one unit-norm vector** (concatenate? weight? separate index?) and re-normalize. There is no universal recipe; the mix differs per institution. |
| **Scale** | Hundreds of documents (linear scan with proof, defaults are fine) vs millions (DATASUS-scale, revenue-service-scale, electronic-process systems: tight PCA-based bounds, cascade tuning, `early_exit`, possibly GPU). The settings that make sense at 500 documents are not the ones at 5M. |
| **Ingestion source** | The institution's SQL database, SEI / e-SIC, electronic-process systems, CSV, PDFs -- each needs its own loader/normalizer seam (the scheduler's `CorpusLoader`). There is no single import path. |
| **Jurisdiction, mode & sensitivity** | `br-gv` / `us-gv` / `eu-gv` policies that inherit global -> region -> country; mode `public` vs `internal` (internal is fail-closed); sensitivity `public` / `restricted` / `secret`. The vector space is the same; the audit/compliance policy is not. |
| **Output expectations** | Retrieval-with-proof only vs retrieval + LLM answers (RAG, e.g. drafting a response to an LAI/FOIA request) vs full question-answering with citations. Each is a different scope of work. |

Any one of these scenarios is enough to make a generic pipeline wrong; in
practice most institutions present several at once. That is normal -- and it is
the reason Winnex offers a full menu below.

### What Tracer-GOV actually does

```
Your laws / rulings / contracts / requests / public data
        |
        |   (embedding happens HERE -- outside Madhava,
        |    with BGE, BlueBERT, OpenAI, your own model, ...)
        v
   float32 vectors  --POST /v1/tracer/build-->  winnex-madhava (retrieval + proof)
                                                      |
        POST /v1/tracer/search <---------------------+  ranked records
            |                                             + bound_violations: 0
            v                                             + worm_hash (WORM audit)
      Tracer-GOV portlet (Liferay UI)
```

Madhava v1.8.8 is a **vector search engine with a mathematical guarantee**.
Its public tuning surface is vector-side: `metric="cosine"`, `stage1_dim` /
`stage2_dim` (projection cascade, defaults 64 / 128), `k`, `k1_fraction`,
`modulation`, `postfilter`, `normalize_input`, and `early_exit`. At
million-scale corpora the engine can also use tighter PCA-based bounds
(`basis="pca_corpus"`, see the Tracer-MED
[Model Integration Guide](../tracer-med-liferay/docs/MODEL_INTEGRATION_GUIDE.md)).
Every one of these parameters operates on **vectors** -- none of them turns
text into vectors for you.

### How to get the embeddings

| Your data | Who generates the vectors |
|---|---|
| Text (laws, rulings, contracts, requests) | An embedding model -- BGE, BlueBERT, OpenAI, Qwen, or your own |
| Structured (dates, values, process numbers) | A numeric encoder you (or Winnex) implement |
| Categorical (UF, agency, document type, secrecy) | One-hot / embedding encoding |
| Mixed | Concatenate the encodings into one unit-norm vector |

---

### Your options -- choose the level of involvement

Winnex offers **three ways** to take Tracer-GOV into production. Pick the one
that fits your institution's team and budget; all of them end with the same
Madhava guarantee **and** the same WORM audit trail.

| Option | What you get | Best for |
|---|---|---|
| **A. Winnex implementation service** | Winnex builds your complete pipeline: embedding-model selection for your legal/government domain, the inference/encoding step, the RAG orchestration (retrieval + LLM answer) if you want it, Madhava tuning, jurisdiction/WORM/compliance configuration, and the go-live. You use the UI and read the proofs. | Institutions that want it done, correct, and provable, without building ML in-house. |
| **B. Winnex full inference stack** | Our ready-made embedding / inference infrastructure (a separate product) wired to Tracer-GOV: vectors generated for you at scale, retrieval with proof, and optional LLM answers -- no model glue on your side. | Institutions that prefer a managed stack over running their own models. |
| **C. Your existing stack** | Bring your own embeddings and/or your own LLM. Tracer-GOV's Madhava bridge consumes the float32 vectors your stack produces -- the proof, the WORM audit and the compliance reports work the same on top of your pipeline. | Institutions with an existing ML/LLM stack that just want the guaranteed retrieval layer + audit + UI. |

### The wider Winnex AI product family

Tracer-GOV is one deployment of Madhava, and the integration does not stop
here. Winnex also ships:

- **OpenAI-compatible API plug** -- expose Madhava behind an OpenAI-style
  endpoint, so tools and agents that already speak the OpenAI API can call it
  with zero new code.
- **Inference stack** -- the managed embedding/LLM infrastructure used in
  Option B, also available standalone for non-Liferay projects.

You can start with Tracer-GOV on top of whatever stack your institution has
today (Option C), let Winnex build it (Option A), or run the full Winnex stack
(Option B). If your project is not Liferay, the OpenAI-compatible plug and the
inference stack let you use Madhava's guarantee anywhere.

> **To budget an inference or RAG implementation, email
> [info@winnex.ai](mailto:info@winnex.ai)**. Tell us your data format, your
> volume, your current stack, your jurisdiction/mode needs, and whether you
> want retrieval-with-proof only or retrieval + LLM answers, and we will quote
> the right option for you.

---

## 1. Start the engine

```bash
# 1. Configure the API key (copy the example, edit the value)
cp tracer-gov-service/.env.example tracer-gov-service/.env

# 2. Start
docker compose up -d

# 3. Verify
curl -s http://localhost:8601/v1/health
# {"status":"ok","engine":"tracer-gov + winnex-madhava 1.8.8",...}
```

---

## 2. Call the API (cURL)

### Build an index (once per jurisdiction)

```bash
curl -X POST http://localhost:8601/v1/tracer/build \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-key>" \
  -d '{
    "vectors": [[0.1, -0.3, ...], [0.2, 0.1, ...]],
    "jurisdiction": "br-gv"
  }'
```

Response:
```json
{
  "status": "built",
  "jurisdiction": "br-gv",
  "N": 30,
  "dim": 32,
  "engine": "tracer-gov + winnex-madhava 1.8.8"
}
```

### Audited search (with government metadata)

```bash
curl -X POST http://localhost:8601/v1/tracer/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-key>" \
  -d '{
    "query": [0.05, 0.2, ...],
    "k": 5,
    "jurisdiction": "br-gv",
    "requesting_agency": "SUS",
    "operator_id": "op-9",
    "sensitivity": "restricted",
    "purpose": "Epidemiological trend analysis"
  }'
```

Response (the proof is in the numbers):
```json
{
  "audit_id": "c9945cf6add601db...",
  "jurisdiction": "br-gv",
  "bound_violations": 0,
  "bound_pairs": 30,
  "total_excluded": 10,
  "sound": true,
  "engine_used": "winnex-madhava (pip, C++20 core)",
  "worm": { "block_hash": "bd3aa4e3c6b86c16..." }
}
```

**What to check in the response:**
- `bound_violations: 0` -> the guarantee (nothing relevant was lost).
- `sound: true` -> same guarantee as a flag.
- `worm.block_hash` -> the WORM receipt for the audit trail.

### Get the proof / verify the audit

```bash
# The mathematical proof
curl -s "http://localhost:8601/v1/tracer/audit/<audit_id>/proof" \
  -H "X-API-Key: <your-key>"

# Verify the WORM record
curl -s -X POST http://localhost:8601/v1/tracer/verify \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-key>" \
  -d '{"audit_id": "<audit_id>"}'
# -> {"found": true, "chain_integrity_verified": true, "chain_violations": 0}
```

---

## 3. Consume the OSGi service (Liferay module)

In any Liferay module, inject the bridge and search with proof:

```java
@Reference
protected volatile TracerGovService tracerGovService;

public void runAuditedSearch() {
    // 1. Build the request (query vector + government metadata)
    TracerGovSearchRequest request = new TracerGovSearchRequest();
    request.setQuery(queryVector);            // List<Float>, unit-norm
    request.setK(5);
    request.setJurisdiction("br-gv");         // or us-gv, eu-gv, ...
    request.setRequestingAgency("SUS");
    request.setOperatorId("op-9");
    request.setSensitivity("restricted");

    // 2. Call the bridge (HTTP -> FastAPI -> winnex-madhava)
    TracerGovSearchResponse response = tracerGovService.search(request);

    // 3. Read the proof
    if (response.isSound()) {
        // 0 bound violations: nothing relevant was lost
        long pairs = response.getBoundPairs();
        String wormHash = response.getWormHash();
    } else {
        // investigate
        String status = response.getServiceStatus(); // OK / DEGRADED / UNREACHABLE
        String error = response.getError();
    }
}
```

### Where the vectors come from

The engine does **not** embed text. You must supply **float32 vectors**
(unit-norm for cosine). See the [Model Integration Guide](../tracer-med-liferay/docs/MODEL_INTEGRATION_GUIDE.md)
from Tracer-MED for the full float32 contract, or use an embedding model
(BGE, BlueBERT, OpenAI, etc.) in your ingestion pipeline.

---

## 4. Screen demo (what the portlet shows)

### Liferay login

![Liferay Login](docs/screenshots/01-liferay-login.png)

### Tracer-GOV portlet with results + proof

![Tracer-GOV Portlet Results](docs/screenshots/02-tracergov-portlet-results.png)

The portlet shows: the jurisdiction form, the **sound proof** banner
(0 bound violations), the audit block (audit_id, worm_hash, violations,
excluded) and the results table.

---

## 5. Live end-to-end demo

```bash
./scripts/e2e.sh http://localhost:8601 <your-key>
```

Runs the full flow and prints:
```
== health ==      -> {"status":"ok","engine":"tracer-gov + winnex-madhava 1.8.8"}
== build ==       -> {"status":"built","jurisdiction":"br-gv","N":30,"dim":32}
== search ==      -> audit_id: ... | violations: 0 | sound: True
== proof+verify== -> PROOF: sound=True viol=0 pairs=30 | VERIFY: found=True chain=True
```

---

## API reference

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/v1/health` | Engine status |
| `GET` | `/v1/stats` | Simple metrics |
| `POST` | `/v1/tracer/build` | Build the index for a jurisdiction/mode |
| `POST` | `/v1/tracer/search` | **Audited search** (writes WORM + proof) |
| `GET` | `/v1/tracer/audit/{id}` | Retrieve an audit record |
| `GET` | `/v1/tracer/audit/{id}/proof` | The mathematical proof |
| `POST` | `/v1/tracer/verify` | Verify a WORM record |
| `GET` | `/v1/worm/verify` | Full WORM chain integrity |

Auth: header `X-API-Key` (constant-time). Mode `internal` also requires an
internal credential (fail-closed).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | Wrong or missing API key | Set `WINNEX_TRACER_API_KEY` and send `X-API-Key` |
| `409 No index built` | Corpus not indexed for that jurisdiction | `POST /v1/tracer/build` first |
| Portlet shows "service unreachable" | Microservice not reachable | Check the container and `baseUrl` in System Settings |
| `bound_violations > 0` | Data does not respect the float32 contract | Normalize vectors; use the same embedding model |
| `chain_integrity_verified: false` | WORM tampered | Investigate immediately |

---

## Legal

Business Source License 1.1 (BSL 1.1) - source-available, not OSI
open-source. Free for Brazilian government agencies. Becomes GPL v2.0+ on
2036-01-01. Commercial use requires a license from Winnex AI
(`pay@winnex.ai`). Tracer-GOV is not a medical device; compliance reports are
self-assessment templates.

---

*Winnex AI -- "Replace probability with proof, in the service of government."*
*BSL 1.1 | pay@winnex.ai | CNPJ 58.364.637/0001-47*
