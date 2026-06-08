# RAG Financial Document Question Answering API

> 📄 ➜ 🧠 ➜ 🔍 ➜ ✍️ ➜ ✅
> **From messy financial PDFs to citation-backed answers — without guessing**

---

## 🚀 What This Project Is About

Most RAG systems optimize generation.

This project optimizes something more fundamental:

> **Structural correctness before retrieval ever begins.**

Real-world financial documents are noisy, visually structured but machine-ambiguous, and prone to silent parsing errors. Instead of relying on prompt tricks or model upgrades, this system invests in upstream discipline — where most real RAG failures actually originate.

The goal is simple:

> If an answer cannot be traced to a specific section and page, it is not considered correct.

---

## ✅ What Works Today

Phases 1 through 3 of the pipeline are complete and verified end-to-end on real 10-K filings. The system can:

* Parse a financial PDF into a hierarchical section tree with page tracking
* Slice sections into retrieval-sized chunks (atomic for short sections, sliding-window narrative chunks for long ones)
* Embed every chunk into a 384-dim L2-normalized vector
* Persist vectors to a local ChromaDB collection, queryable by metadata

The full pipeline runs end-to-end via `POST /ingest`. Retrieval and answering (Phase 4) is the next milestone — the `/ask` endpoint currently returns a stub.

**Smoke-tested on Apple's 10-K** — 135 chunks produced, 135 indexed, vector norms within `1.0 ± 1e-6`.

---

## 🧠 System Architecture

The system is built layer by layer, with strict invariants at each stage. Downstream layers are not allowed to compensate for upstream structural errors.

```
PDF
  ↓
Phase 1 — Extractor (services/extractor.py)
  ├─ Raw span extraction (PyMuPDF)
  ├─ Centralized header detection (font ratio + heuristics)
  ├─ Stack-based hierarchical section tree
  ├─ section_path + page_start / page_end tracking
  └─ Validation gate (empties, orphans, level invariants)
  ↓
list[Section]
  ↓
Phase 2 — Chunker (services/chunking.py)
  ├─ Atomic chunks for sections ≤ 500 tokens
  ├─ Narrative chunks for larger sections (max 600 tokens, 100 overlap)
  ├─ Validation cascade (dedup → tiny-merge → oversized-split → reindex)
  └─ Diagnostic report
  ↓
list[Chunk]
  ↓
Phase 3a — Embedder (services/embedding.py)
  ├─ BAAI/bge-small-en-v1.5 (passage: / query: prefix convention)
  ├─ Module-level model singleton
  ├─ L2-normalized, 384-dim vectors
  └─ Validation gate (dim consistency, norm tolerance, NaN/Inf, id uniqueness)
  ↓
list[EmbeddedChunk]
  ↓
Phase 3b — Indexer (services/indexing.py)
  ├─ ChromaDB persistent client at storage/chroma/
  ├─ Upsert by chunk_id (idempotent)
  └─ Read-only handle for Phase 4
  ↓
Persisted vector store
  ↓
[Phase 4 — Retrieval & Answering — PLANNED]
  ├─ BM25 sparse sidecar
  ├─ Hybrid retrieval (dense + sparse, optional reranker)
  └─ Citation-constrained LLM answer
```

The frozen architecture rules are documented in `CLAUDE.md`. Phase 3 design rationale and smoke test results live in `notes/phase_3_design.md`.

---

## 🧰 Stack

| Layer | Choice | Why |
|---|---|---|
| PDF parsing | PyMuPDF (`fitz`) | Span-level access, font metadata for header heuristics |
| Embedding model | `BAAI/bge-small-en-v1.5` | 384-dim, MIT license, CPU-friendly, strong on English financial prose |
| Vector store | ChromaDB (local persistent) | Pure-Python wheel on Windows, no Docker, built-in metadata filtering |
| API | FastAPI + Uvicorn | Async, type-safe, simple |
| Hybrid sparse (Phase 4) | `rank_bm25` *(planned)* | Pure-Python BM25 sidecar, no extra infra |
| LLM (Phase 4) | TBD *(planned)* | OSS-only constraint |

**OSS-only constraint:** no paid APIs, no Docker. Runs on Windows 11 with Python 3.12 and CPU only.

---

## 📁 Repository Layout

```
Financial_rag/
├── config.py                  # env-backed constants (EMBED_MODEL, CHROMA_PATH, COLLECTION_NAME)
├── main.py                    # FastAPI app: /health, /ingest, /ask
├── pipeline/
│   └── pipeline_flow.py       # End-to-end runner for one PDF (debug-friendly)
├── services/
│   ├── extractor.py           # Phase 1: structure builder (frozen)
│   ├── chunking.py            # Phase 2: retrieval-sized chunks
│   ├── embedding.py           # Phase 3a: BGE-small encoder + validation
│   └── indexing.py            # Phase 3b: ChromaDB upsert + read handle
├── storage/                   # gitignored
│   ├── docs/                  # Ingested PDFs (per doc_id folder)
│   └── chroma/                # Persistent vector store (SQLite + HNSW)
├── debug/                     # gitignored — per-phase JSON diagnostics
├── notes/
│   └── phase_3_design.md      # Phase 3 design rationale + smoke test results
├── CLAUDE.md                  # Frozen architecture rules and layer contracts
├── TODO.md                    # Phase-by-phase implementation checklist
├── requirements.txt
└── Readme.md                  # this file
```

- Generate embeddings for the chunk
- Store them in vector database
- Preserve chunk metadata for retrival
  
---

## ▶️ Quickstart

```powershell
# Clone and enter
git clone https://github.com/Gokulnaath07/Financial_rag.git
cd Financial_rag

# Create venv (Python 3.12 recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies (~1.5–2 GB on first install — includes torch, transformers, chromadb)
pip install -r requirements.txt

# Option A: run the full pipeline directly on a PDF (writes diagnostics to debug/)
# Edit pipeline/pipeline_flow.py to point at your PDF, then:
python -m pipeline.pipeline_flow

# Option B: start the API server
python main.py
# Server runs on http://localhost:5000

# Ingest a PDF via the API
$file = Get-Item "path\to\your.pdf"
Invoke-RestMethod -Uri "http://localhost:5000/ingest" -Method Post -Form @{ file = $file }
```

**First-run note:** the first `/ingest` (or `pipeline_flow`) call downloads BGE-small (~130 MB) from HuggingFace to `%USERPROFILE%\.cache\huggingface\`. Subsequent runs use the cached model.

---

## 🐛 Debug Artifacts

Every phase emits a JSON to `debug/` for inspection. Inspect these to see what each layer produced without running the API.

| File | Phase | Contents |
|---|---|---|
| `structured.json` | 1 | Section tree with headers, `section_path`, page ranges, content blocks |
| `chunk_doc.json` | 2 | All chunks with text, ids, section refs, `chunk_type` |
| `embed_stats.json` | 3a | Counts, embedding dim, model name, norm summary (no raw vectors) |
| `index_report.json` | 3b | IndexHandle: collection name, count, embedding model + dim |

---

## 🛣️ Roadmap

### Phase 1 — Structural Parsing ✅ Complete

* [x] Raw span extraction (PyMuPDF)
* [x] Centralized header detection
* [x] Section level assignment (1–4)
* [x] Hierarchy stabilization (level-jump clamp)
* [x] Multi-line header merging
* [x] Stack-based section tree
* [x] `section_path` + page tracking
* [x] Validation gate (empties, orphans, invariants)

### Phase 2 — Chunking ✅ Complete

* [x] Atomic / narrative dispatch (500-token threshold)
* [x] Sliding window with 100-token overlap
* [x] Metadata-preserving chunks (header, section_id, section_path inherited)
* [x] Multi-pass validation (dedup → tiny-merge → oversized-split → reindex)
* [x] Diagnostic report

### Phase 3 — Embedding & Indexing ✅ Complete

* [x] BGE-small singleton loader
* [x] `passage:` / `query:` prefix convention
* [x] L2-normalized 384-dim vectors
* [x] Embedded-chunk validation gate
* [x] ChromaDB persistent store (idempotent upsert)
* [x] Read-only index handle for Phase 4
* [x] Full pipeline wired into `POST /ingest`

### Phase 4 — Retrieval & Answering 🚧 Planned

* [ ] BM25 sparse sidecar (`services/bm25_index.py` with `rank_bm25`)
* [ ] Hybrid retrieval (dense + sparse fusion)
* [ ] Optional reranking
* [ ] LLM call wired into `/ask` with retrieved context
* [ ] Strict citation enforcement (section + page must accompany every answer)
* [ ] "Not found" behavior when retrieval scores fall below threshold

### Phase 5+ — Production Concerns *(later)*

* [ ] Background ingest workers (async, not synchronous in request handler)
* [ ] Multi-document collection management + filtering
* [ ] Polish Phase 2 narrative splitter (current gap: chunks occasionally land in the 600–800 token range)
* [ ] Evaluation harness (retrieval recall, answer quality)

---

## 🎯 Design Principles

* Structure before semantics
* Hierarchy before chunking
* Retrieval before generation
* Citations before confidence
* **Single responsibility per layer** — no cross-layer leakage (Embedder cannot persist; Indexer cannot embed)
* **Loud failures over silent papering-over** — when an upstream layer produces something unusual, the next layer warns visibly rather than masks it

---

## 🔒 Philosophy

> If structure is wrong → retrieval fails silently.
> If retrieval is wrong → generation hallucinates confidently.
> So we fix structure first.

---

## 📌 Status

![Parsing](https://img.shields.io/badge/Parsing-Complete-brightgreen)
![Chunking](https://img.shields.io/badge/Chunking-Complete-brightgreen)
![Embedding](https://img.shields.io/badge/Embedding-Complete-brightgreen)
![Indexing](https://img.shields.io/badge/Indexing-Complete-brightgreen)
![Retrieval](https://img.shields.io/badge/Retrieval-Planned-lightgrey)
![Answering](https://img.shields.io/badge/Answering-Planned-lightgrey)
![Backend](https://img.shields.io/badge/Backend-FastAPI-green)
![VectorDB](https://img.shields.io/badge/VectorDB-ChromaDB-blue)
![Embedding%20Model](https://img.shields.io/badge/Embedding-BGE--small-blue)
![Python](https://img.shields.io/badge/Python-3.12-blue)

---

This repository represents a correctness-first foundation for a production-grade RAG system operating on real-world financial documents.

It is intentionally scoped, disciplined, and built to be extended — not rushed.
