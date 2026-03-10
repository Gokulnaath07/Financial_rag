Here is a polished, GitHub-ready landing README — clean, structured, and aligned with your original tone (correctness-first, deliberate, not hype-driven).

---

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

If an answer cannot be traced to a specific section and page, it is not considered correct.

---

## 🧠 System Architecture

This system is built layer by layer, with strict invariants at each stage.

```
PDF / TXT
   ↓
Raw Span Extraction (PyMuPDF)
   ↓
Structural Parsing
   ├─ Clean spans
   ├─ Global median font scaling
   ├─ Centralized header detection
   ├─ Section level assignment (1–4)
   ├─ Global ordering
   └─ Header-only clamp (no depth skipping)
   ↓
Hierarchical Section Tree (Stack-Based)
   ├─ Nested section modeling
   ├─ section_path construction
   ├─ page_start / page_end tracking
   └─ Content aggregation
   ↓
Header-Aware Chunking
   ↓
Embedding Generation
   ↓
Vector Database (Hybrid Search)
   ↓
Retrieval + Reranking
   ↓
Citation-Constrained LLM Answer
```

Downstream layers are not allowed to compensate for upstream structural errors.

---

## 🧩 Current Focus: Structural Parsing

The parsing layer currently guarantees:

* Global reading-order preservation
* Explicit `is_header` structural tagging
* Deterministic section level assignment (1–4)
* Header-only depth clamp (prevents illegal hierarchy jumps)
* Page-continuous processing (no per-page resets)

This ensures hierarchy is stable before building the section tree.

Parsing is ~70% complete.

---

## 🛣️ Roadmap

### Phase 1 — Structural Parsing (In Progress)

* [x] Raw span extraction
* [x] Centralized header detection
* [x] Section level assignment
* [x] Hierarchy stabilization (clamp)
* [ ] Span-to-line reconstruction
* [ ] Stack-based section tree
* [ ] `section_path` + page tracking

### Phase 2 — Chunking

* [ ] Section-safe chunk boundaries
* [ ] Metadata-preserving chunks

### Phase 3 — Embedding & Indexing

* [ ] Embedding generation
* [ ] Weaviate setup
* [ ] Hybrid search configuration

### Phase 4 — Retrieval & Answering

* [ ] Hybrid retrieval pipeline
* [ ] Optional reranking
* [ ] Strict citation enforcement
* [ ] "Not found" behavior

---

## 🎯 Design Principles

* Structure before semantics
* Hierarchy before chunking
* Retrieval before generation
* Citations before confidence

---

## 🔒 Philosophy

If structure is wrong → retrieval fails silently.
If retrieval is wrong → generation hallucinates confidently.

So we fix structure first.

---

## 📌 Status

![Parsing](https://img.shields.io/badge/Parsing-~70%25%20Complete-blue)
![Section%20Tree](https://img.shields.io/badge/Section%20Tree-In%20Progress-yellow)
![Chunking](https://img.shields.io/badge/Chunking-Planned-lightgrey)
![Embedding](https://img.shields.io/badge/Embedding-Planned-lightgrey)
![Retrieval](https://img.shields.io/badge/Retrieval-Planned-lightgrey)
![Backend](https://img.shields.io/badge/Backend-FastAPI-green)
![VectorDB](https://img.shields.io/badge/VectorDB-Weaviate-orange)
![LLM](https://img.shields.io/badge/LLM-Gemini-lightblue)

---

This repository represents a correctness-first foundation for a production-grade RAG system operating on real-world financial documents.

It is intentionally scoped, disciplined, and built to be extended — not rushed.

