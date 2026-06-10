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

**All four phases are complete and verified end-to-end.** The system can:

* Parse a financial PDF into a hierarchical section tree with page tracking
* Slice sections into retrieval-sized chunks (atomic for short sections, sliding-window narrative chunks for long ones)
* Embed every chunk into a 384-dim L2-normalized vector
* Persist vectors to a local ChromaDB collection, queryable by metadata
* **Build a parallel BM25 sparse index for hybrid retrieval**
* **Answer questions with strict citation enforcement** — every claim references a specific section + page
* **Refuse to fabricate** — when retrieved chunks don't support the question, the system returns "I cannot find this in the documents" with `confidence: not_found`

The full pipeline runs end-to-end:
* `POST /ingest` — PDF in → parses → chunks → embeds → indexes → builds BM25
* `POST /ask` — question in → hybrid retrieval (BM25 + dense + RRF + rerank) → Gemini with structured output → citation-verified answer

**Smoke-tested on Apple's 10-K**:
- 135 chunks indexed with vector norms within `1.0 ± 1e-6`
- 4 of 5 real questions answered with **high confidence** + page citations (Ernst & Young auditors p55, R&D $34.5B p32, net revenue $416B p32, product categories)
- Gibberish queries correctly gated to `not_found`

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
Phase 4a — Sparse Index (services/bm25_index.py)
  ├─ rank_bm25 BM25Okapi over chunk_text from Chroma
  ├─ Tokenizer: lowercase + whitespace + strip ASCII punct
  └─ Persists to storage/bm25/<collection>/{bm25.pkl, chunk_ids.json, manifest.json}
  ↓
Phase 4b — Hybrid Retrieval (services/retrieval.py + services/reranker.py)
  ├─ Dense top-50 (Chroma) + Sparse top-50 (BM25)
  ├─ RRF fusion (k=60) → top-20 candidates
  ├─ BGE-reranker-base cross-encoder → top-5
  └─ Emits debug/retrieve_trace.json
  ↓
list[RetrievedChunk]
  ↓
Phase 4c — Answering (services/llm.py + prompts.py + answering.py)
  ├─ Gemini 2.5 Flash via google-genai SDK
  ├─ Structured JSON output schema → forces {answer, citations} shape
  ├─ Post-LLM verification: drops invalid chunk_index citations
  └─ Confidence: high | low | not_found
  ↓
AnswerResult → /ask response
```

Architecture rules live in `CLAUDE.md`. Phase-specific design docs are in `notes/phase_3_design.md` and `notes/phase_4_design.md`.

---

## 🧰 Stack

| Layer | Choice | Why |
|---|---|---|
| PDF parsing | PyMuPDF (`fitz`) | Span-level access, font metadata for header heuristics |
| Embedding model | `BAAI/bge-small-en-v1.5` | 384-dim, MIT license, CPU-friendly, strong on English financial prose |
| Vector store | ChromaDB (local persistent) | Pure-Python wheel on Windows, no Docker, built-in metadata filtering |
| Sparse index | `rank_bm25` | Pure-Python BM25 sidecar, no extra infra |
| Hybrid fusion | Reciprocal Rank Fusion (RRF, k=60) | Score-scale immune; no tuning needed |
| Reranker | `BAAI/bge-reranker-base` cross-encoder | Same vendor as embedder, MIT, no new library |
| LLM | Gemini 2.5 Flash via `google-genai` | Fast (1–2s), free tier, structured output with JSON schema |
| API | FastAPI + Uvicorn | Async, type-safe, simple |

**OSS-only for retrieval; LLM uses free-tier Gemini.** Runs on Windows 11 with Python 3.12 and CPU only — no Docker, no paid embeddings, no paid vector DB.

---

## 📁 Repository Layout

```
Financial_rag/
├── config.py                  # env-backed constants (loads .env automatically)
├── main.py                    # FastAPI app: /health, /ingest, /ask
├── pipeline/
│   └── pipeline_flow.py       # End-to-end runner for one PDF (debug-friendly)
├── services/
│   ├── extractor.py           # Phase 1: structure builder (frozen)
│   ├── chunking.py            # Phase 2: retrieval-sized chunks
│   ├── embedding.py           # Phase 3a: BGE-small encoder + validation
│   ├── indexing.py            # Phase 3b: ChromaDB upsert + read handle
│   ├── bm25_index.py          # Phase 4a: rank_bm25 sparse index
│   ├── reranker.py            # Phase 4b: BGE-reranker-base cross-encoder
│   ├── retrieval.py           # Phase 4b: RRF hybrid retrieve() entry point
│   ├── llm.py                 # Phase 4c: Gemini client (provider-agnostic)
│   ├── prompts.py             # Phase 4c: system prompt + JSON schema
│   └── answering.py           # Phase 4c: answer_question() orchestrator
├── storage/                   # gitignored
│   ├── docs/                  # Ingested PDFs (per doc_id folder)
│   ├── chroma/                # Persistent vector store (SQLite + HNSW)
│   └── bm25/                  # Persistent BM25 pickle + manifest
├── debug/                     # gitignored — per-phase JSON diagnostics
├── notes/
│   ├── phase_3_design.md      # Phase 3 design + smoke test results
│   └── phase_4_design.md      # Phase 4 design + smoke test results
├── smoke_phase_4.py           # End-to-end smoke test script
├── test_gemini_key.py         # Standalone Gemini key + quota diagnostic
├── CLAUDE.md                  # Frozen architecture rules and layer contracts
├── TODO.md                    # Phase-by-phase implementation checklist
├── requirements.txt
├── .env.example               # Template — copy to .env and add GEMINI_API_KEY
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

# Set up your Gemini API key
Copy-Item .env.example .env
notepad .env   # paste your key after GEMINI_API_KEY=, save, close
# Get a free key at https://aistudio.google.com/app/apikey

# Start the API server
python main.py
# Server runs on http://localhost:5000
# Interactive docs: http://localhost:5000/docs (FastAPI Swagger UI)
```

### Use the API

```powershell
# Ingest a PDF
$file = Get-Item "path\to\your.pdf"
$resp = Invoke-RestMethod -Uri "http://localhost:5000/ingest" -Method Post -Form @{ file = $file }
$docId = $resp.doc_id

# Ask a question
$body = @{ doc_id = $docId; question = "What was the company's net revenue?" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/ask" -Method Post -Body $body -ContentType "application/json"
```

**First-run note:** the first `/ingest` downloads BGE-small (~130 MB) + BGE-reranker (~280 MB) from HuggingFace to `%USERPROFILE%\.cache\huggingface\`. Subsequent runs use the cached models.

---

## 🐛 Debug Artifacts

Every phase emits a JSON to `debug/` for inspection.

| File | Phase | Contents |
|---|---|---|
| `structured.json` | 1 | Section tree with headers, `section_path`, page ranges, content blocks |
| `chunk_doc.json` | 2 | All chunks with text, ids, section refs, `chunk_type` |
| `embed_stats.json` | 3a | Counts, embedding dim, model name, norm summary |
| `index_report.json` | 3b | IndexHandle: collection name, count, embedding model + dim |
| `retrieve_trace.json` | 4b | Last query: dense scores, sparse scores, RRF fused, rerank scores per stage |
| `answer_trace.json` | 4c | Last query: rendered prompt, raw LLM response, parsed citations, confidence |

The `retrieve_trace.json` + `answer_trace.json` pair is the best debugging artifact in the project — they show every score for every stage of every question.

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

### Phase 4 — Retrieval & Answering ✅ Complete

* [x] BM25 sparse sidecar (`rank_bm25` lowercase+whitespace tokenizer)
* [x] Hybrid retrieval with Reciprocal Rank Fusion (k=60)
* [x] BGE-reranker-base cross-encoder for top-K reordering
* [x] Gemini 2.5 Flash via `google-genai` with structured JSON output
* [x] Citation-enforced system prompt
* [x] Post-LLM citation verification (drops invalid chunk_index)
* [x] Two-tier "not found" behavior (score gate + LLM self-report)
* [x] `POST /ask` wired with HTTP 502/503/429 error mapping
* [x] Provider-agnostic LLM interface (hot-swappable to Ollama/Groq/OpenAI)

### Phase 5+ — Polish & Production (planned)

* [ ] Deterministic chunk_ids (hash of section_id + chunk_index) so re-ingest is idempotent
* [ ] Background ingest workers (async, not synchronous in request handler)
* [ ] Streaming `/ask` responses (Server-Sent Events)
* [ ] Multi-document cross-collection Q&A
* [ ] Eval harness (retrieval recall, answer faithfulness)
* [ ] Replace `rank_bm25` with `bm25s` for latency at scale
* [ ] Cold-start model preloading on FastAPI startup

---

## 🎯 Design Principles

* Structure before semantics
* Hierarchy before chunking
* Retrieval before generation
* Citations before confidence
* **Single responsibility per layer** — no cross-layer leakage (Embedder cannot persist; Indexer cannot embed; Retrieval cannot call the LLM)
* **Loud failures over silent papering-over** — when an upstream layer produces something unusual, the next layer warns visibly rather than masks it
* **Hot-swappable provider boundaries** — the LLM client lives behind a `generate(prompt, system, temperature, response_schema)` interface so changing providers is a one-file replacement

---

## 🔒 Philosophy

> If structure is wrong → retrieval fails silently.
> If retrieval is wrong → generation hallucinates confidently.
> If generation hallucinates → users lose trust.
> So we fix structure first, retrieval second, and force generation to cite or refuse.

---

## 📌 Status

![Parsing](https://img.shields.io/badge/Parsing-Complete-brightgreen)
![Chunking](https://img.shields.io/badge/Chunking-Complete-brightgreen)
![Embedding](https://img.shields.io/badge/Embedding-Complete-brightgreen)
![Indexing](https://img.shields.io/badge/Indexing-Complete-brightgreen)
![Retrieval](https://img.shields.io/badge/Retrieval-Complete-brightgreen)
![Answering](https://img.shields.io/badge/Answering-Complete-brightgreen)
![Backend](https://img.shields.io/badge/Backend-FastAPI-green)
![VectorDB](https://img.shields.io/badge/VectorDB-ChromaDB-blue)
![Sparse](https://img.shields.io/badge/Sparse-rank__bm25-blue)
![Embedding%20Model](https://img.shields.io/badge/Embedding-BGE--small-blue)
![Reranker](https://img.shields.io/badge/Reranker-BGE--reranker--base-blue)
![LLM](https://img.shields.io/badge/LLM-Gemini%202.5%20Flash-orange)
![Python](https://img.shields.io/badge/Python-3.12-blue)

---

This repository represents a correctness-first foundation for a production-grade RAG system operating on real-world financial documents.

It is intentionally scoped, disciplined, and built to be extended — not rushed.
