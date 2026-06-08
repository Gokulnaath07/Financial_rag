# Phase 3 — Embedding & Indexing: Design

**Status:** Design approved, pending TODO.md write & implementation start
**Stack:** BGE-small + ChromaDB (OSS, no Docker)
**Constraints:** Free / OSS only · Windows 11 · Python 3.12.6 · CPU only
**Date:** 2026-06-07

---

## Environment Verified

| Check | Result | Implication |
|---|---|---|
| Python | 3.12.6 | sentence-transformers & chromadb have clean wheels |
| Desktop redirected to OneDrive? | No (Desktop → `C:\Users\Albus\Desktop`) | `storage/chroma/` safe from SQLite locking issue |
| sentence-transformers installed? | No | Install in step 1 |
| chromadb installed? | No | Install in step 1 |

---

## Architecture

Two new layers + validation gate, mirroring Phase 1/2 separation.

```
Phase 2 output            ──►  Embedder           ──►  Indexer            ──►  Phase 4
list[Chunk dict]               list[EmbeddedChunk]     persisted store
                               ↑                       ↑
                               vector + metadata       writes/reads only
                               NEVER persists          NEVER computes embeddings
```

### Layer A — Embedder (`services/embedding.py`)
*Single responsibility: encode chunk text into normalized dense vectors.*

#### `embed_chunks(chunks, model_name=None, batch_size=32)`
- **Input:** `list[Chunk dict]` from `chunk_sections()`.
- **Output:** `list[EmbeddedChunk dict]` = original Chunk fields + `embedding: list[float]` + `embedding_model: str` + `embedding_dim: int`.
- **Invariants:**
  1. Output length == input length, in order.
  2. Every embedding is L2-normalized (||v|| ≈ 1.0 ± 1e-3).
  3. All embeddings share identical dim.
  4. No mutation of Phase 2 fields.
  5. No I/O. No vector store calls.
- **Rules:**
  - Uses BGE `"passage: "` prefix on indexing.
  - Model loaded once (module-level singleton).
  - Asserts + warns when truncating to model max (512 tokens) — surfaces Phase 2 oversized chunks instead of silently masking them.

#### `embed_query(text, model_name=None)`
Stub. Phase 4 calls this with `"query: "` prefix. Defined here so Phase 4 cannot invent its own encoder.

### Validation gate — `validate_embedded_chunks(embedded)`
- Dim consistency
- All vectors normalized (norm within tolerance)
- No NaN / Inf
- `chunk_id` uniqueness
- Required metadata fields present
- Logs + drops invalid entries (matches Phase 2's `validate_chunks` style)

### Layer B — Indexer (`services/indexing.py`)
*Single responsibility: persist vectors + metadata, expose read-only handle.*

#### `index_chunks(embedded_chunks, store_path, collection_name)`
- **Input:** validated EmbeddedChunk list + persistence location.
- **Output:** `IndexHandle = {store_path, collection_name, count, embedding_model, embedding_dim}`.
- **Invariants:**
  1. Idempotent on `chunk_id` (upsert, not duplicate).
  2. Persists everything needed for cold reload.
  3. NEVER computes embeddings. Hard-fail if `embedding` missing.
- **Rules:**
  - Collection name: `"financial_docs"` (single-collection strategy).
  - `section_path: list[str]` stored as `" > ".join(path)` since Chroma metadata accepts only primitives.

#### `open_index(store_path, collection_name) -> IndexHandle`
Read-only handle. Phase 4 retrieval entry point.

#### `index_diagnostics(handle)`
Reports count, dim, model name, sample metadata. No similarity search — that belongs to Phase 4.

---

## Hard Rules

Embedder MUST NOT:
- persist anything
- open vector store
- accept queries
- modify chunk text

Indexer MUST NOT:
- call embedding model
- tokenize
- modify metadata semantics
- perform similarity search (outside its own diagnostic round-trip)

---

## Stack Decisions

### Embedding model: `BAAI/bge-small-en-v1.5`
- 384-dim, ~130 MB on disk, MIT license
- Top of MTEB for its size class
- CPU-friendly: ~30–80 chunks/sec on modern laptop CPUs
- Pedagogically teaches `passage:` / `query:` prefix asymmetry
- **Fallback:** `intfloat/e5-base-v2` if quality on financial language is insufficient

### Vector store: ChromaDB (local persistent)
- Pure-Python wheel on Windows — no Docker, no compiler
- Persists to `storage/chroma/` (SQLite + parquet)
- Idiomatic `add` / `query` / `get` API
- Built-in metadata filtering (`where={"document_id": ...}`)
- **Rejected:**
  - Weaviate — Docker on Windows, friction-heavy
  - Qdrant — Docker for persistence
  - FAISS — no metadata layer; would require parallel SQLite
  - LanceDB — viable fallback, slightly less common in tutorials

### Hybrid search: Deferred to Phase 4
- Chroma lacks first-class BM25
- Phase 4 will add `services/bm25_index.py` (using `rank_bm25`, pure Python)
- Keeps Phase 3 single-purpose and teaches dense vs sparse as distinct concepts

---

## Default Decisions (Approved)

- **Embedding granularity:** chunks only (no section-level)
- **Collection strategy:** single `"financial_docs"`, filter by `document_id`
- **Similarity:** L2-normalize + cosine
- **Model override:** env var `EMBED_MODEL`
- **`config.py`:** add now, env-backed defaults
- **Hardware:** CPU only

---

## Pipeline Integration

Extend `pipeline/pipeline_flow.py`:

```
parse_pdf_blocks(pdf) → document         → debug/structured.json
chunk_sections(document) → chunks        → debug/chunk_doc.json
embed_chunks(chunks) → embedded          → debug/embed_stats.json   (counts, dim, norm summary — NOT raw vectors)
validate_embedded_chunks(embedded) → valid
index_chunks(valid, "storage/chroma", "financial_docs") → handle
index_diagnostics(handle)                → debug/index_report.json
```

**`main.py /ingest`:** run full pipeline synchronously; return `{doc_id, chunk_count, indexed: true}`. `/ask` stays untouched (belongs to Phase 4).

---

## Phase 3 TODO Checklist (10 steps)

1. Add `sentence-transformers` and `chromadb` to `requirements.txt`
2. Add `config.py` with env-backed `EMBED_MODEL`, `CHROMA_PATH`, `COLLECTION_NAME`
3. Create `services/embedding.py` — model singleton, `embed_chunks()`, `embed_query()` stub
4. Add `validate_embedded_chunks()` to `services/embedding.py`
5. Create `services/indexing.py` — `index_chunks()`, `open_index()`, `index_diagnostics()`
6. Extend `pipeline/pipeline_flow.py` — parse → chunk → embed → validate → index
7. Emit `debug/embed_stats.json` + `debug/index_report.json` (no raw vectors)
8. Wire `main.py /ingest` to full pipeline; return `chunk_count` + `indexed`
9. Confirm `storage/chroma/` is gitignored (likely already via `storage/`)
10. Smoke test on Apple 10-K, record expected counts in this file

---

## Risks & Gotchas

- **Phase 2 gap interaction:** chunks may exceed 600 tokens; embedder MUST assert + log when truncating to model max (512). Don't silently truncate — that papers over upstream bugs.
- **First-run model download:** ~130 MB blocks first `/ingest`. Document a warm-up step in README or pre-download at import.
- **`section_path` transform:** Chroma metadata = primitives only. Always `" > ".join(path)` on write, split on read. Document in both layers' docstrings so the transform is never re-implemented ad hoc.
- **Cross-layer leakage temptation:** retrieval feels "one function away" once the index exists. Resist. Indexer exposes `open_index` and stops.
- **Pedagogical sugar:** `sentence-transformers` hides tokenize → forward → mean-pool → normalize. Add a 4-line comment in `embedding.py` showing the raw `transformers` equivalent so the convenience wrapper is demystified.

---

## Open Items After Implementation

### Smoke test results — 2026-06-07
Run: `python -m pipeline.pipeline_flow` on `storage/docs/f081b0e2.../Apple 10-k.pdf`.

| Metric | Value |
|---|---|
| Chunks produced (Phase 2 output) | 135 |
| Embedded successfully | 135 / 135 |
| Validation drops | 0 (dim, norm, NaN, dup, metadata — all clean) |
| Embedding dim | 384 (BGE-small ✓) |
| Norm range | min 0.99999994, max 1.00000014, mean 1.00000002 |
| Indexed in Chroma | 135 / 135 |
| Collection | `financial_docs` |
| Store path | `storage/chroma/` (SQLite + HNSW binaries) |
| Wall time | ~2–5 min (first run: model download dominates) |

### Token-limit warnings (surfaces Phase 2 gap)
17+ chunks exceeded BGE max_seq_length=512 (range observed: 578–600 tokens). The embedder warned loudly per chunk; sentence-transformers truncated at encode time. **This is designed behavior** — the warnings reveal that Phase 2's narrative splitter occasionally over-produces in the 600–800 gap before the emergency splitter catches it. Logged here as input for a future Phase 2 polish pass.

### Still open
- Decision on whether `bge-small` quality is sufficient or upgrade to `e5-base` — defer until retrieval evaluation in Phase 4
- BM25 layer design for Phase 4 (`services/bm25_index.py` with `rank_bm25`)
- `/ask` rewiring spec for Phase 4 (hybrid retrieval + LLM call + citation enforcement)

---

## Related Memory

- `[[obsidian-vaults]]` — vault locations
- `[[subagent-learning]]` — agent usage pattern for this project
- `[[phase-3-stack]]` — condensed stack decision (summary of this doc)
