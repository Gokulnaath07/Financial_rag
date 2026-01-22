# RAG Financial Document Question Answering API

> 📄 ➜ 🧠 ➜ ✅
> **From messy PDFs to citation-backed answers — without guessing**

---

## 🚀 What This Project Is About

Most RAG systems focus on *generation*.
This project focuses on something less glamorous — and far more important:

> **Making sure the input to the LLM is actually trustworthy.**

This API enables users to ask natural-language questions over complex financial documents and receive **answers that are grounded, traceable, and defensible**.

Instead of chasing prompt tricks or model upgrades, the system deliberately invests in the **upstream layers** where most real-world RAG failures originate.

---

## ❓ Why This Exists

If you’ve worked with real PDFs, this will sound familiar:

📄 PDFs look structured — but aren’t
📉 OCR introduces noise and broken paragraphs
📑 Headers are obvious to humans, invisible to machines
⚠️ Small parsing errors silently ruin retrieval

Most demos ignore this complexity.

This project does not.

The goal is not just to *answer questions* — it’s to **explain why an answer is correct**.

---

## 👥 Who This Is For

Designed for users who care about **correctness and traceability**:

* 💼 Finance analysts
* 🧾 HR teams
* 🔍 Auditors & compliance professionals

If an answer cannot be traced back to a specific page or section, it is treated as incorrect.

---

## 🧩 What the System Does (Current Scope)

This project is intentionally scoped to the **ingestion and structural organization layers** of a RAG pipeline. The goal at this stage is not to optimize chunk size or embeddings, but to ensure that document content is **correctly structured, ordered, and attributed** before chunking occurs.

```
PDF / TXT
   ↓
OCR (if needed)
   ↓
Structural Parsing
   ↓
Header-Aware Grouping
   ↓
Chunking-Ready Sections + Metadata
```

### 1️⃣ Document Ingestion

* Accepts PDF and TXT files with extractable text
* Preserves page boundaries and basic document metadata

> **Note:** OCR is a *designed but not yet implemented* ingestion layer. The current system assumes text availability and focuses on structural correctness downstream.

#### 🔐 Layer Guarantees: Document Ingestion (Current State)

At the end of ingestion, the system guarantees:

* Text content is available as plain text before structural parsing begins
* Page boundaries are preserved when provided by the source document

**Non‑guarantees (by design):**

* OCR accuracy or completeness
* Text normalization for scanned or image-only documents

These constraints are intentional so downstream guarantees do not depend on unfinished OCR behavior.

### 2️⃣ Structural Parsing 🧠

*(Establishes layout correctness)*

* Groups text using layout signals (e.g., Y-coordinate thresholds)
* Stabilizes paragraphs across noisy OCR output
* Preserves reading order across pages
* Prevents text from bleeding across unrelated sections

#### 🔐 Layer Guarantees: Structural Parsing

After structural parsing completes, the system guarantees:

* Text spans are ordered according to the document’s reading flow
* Paragraph boundaries are stable despite OCR-induced noise
* No text span crosses logical section or header boundaries
* Each span retains page-level and positional metadata

Downstream stages rely on these guarantees and do not re-validate layout or ordering assumptions.

### 3️⃣ Header-Aware Grouping 🔗

*(Precursor to chunking)*

* Detects logical headers and section boundaries
* Associates each text span with its corresponding header
* Preserves document hierarchy and semantic intent
* Produces **section-level groupings** suitable for downstream chunking

At this stage, content is **grouped, ordered, and attributed** — but not yet split into retrieval-sized chunks. This guarantees that future chunking operations can occur *within* correct section boundaries rather than across unrelated topics.

---

## 📥 Inputs

* 📄 Unstructured documents (PDF, TXT)
* 💬 Natural-language questions about those documents

---

## 📤 Outputs

* 📝 A natural-language answer
* 📌 Explicit citations pointing to the exact page, section, or header

> ❌ No citations → no answer

---

## ✅ What “Correct” Means Here

An answer is considered correct **only if**:

* ✔️ Every claim is supported by retrieved document content
* ✔️ Citations are explicit and verifiable
* ✔️ No facts, numbers, or interpretations are inferred by the LLM

If the document does not contain the answer, the system is expected to say so.

---

## 🚨 Failure Is a Feature

This system is designed to **fail loudly**, not confidently:

* ❓ Missing information → no answer
* ⚠️ Weak retrieval → no speculation
* 🔎 Ambiguous context → explicit uncertainty

This behavior is intentional.

---

## 🧱 Design Principles

* 🧠 Correctness beats cleverness
* ⬆️ Upstream discipline reduces downstream complexity
* 🔗 Every layer enforces invariants for the next
* 📌 If you can’t cite it, you can’t say it

---

## 🛣️ What’s Next (Planned, Not Pretended)

The following layers are **designed but intentionally not implemented yet**:

* 🧭 Vector indexing and hybrid retrieval
* 🎯 Reranking for precision-sensitive queries
* ✍️ Generation with stricter citation constraints
* 📊 Evaluation and diagnostics endpoints

These will build on the guarantees established here — not replace them.

---

## 📌 Project Status

This repository represents a **correctness-first foundation** for a production-grade RAG system operating on real-world financial documents.

It is intentionally opinionated, narrowly scoped, and designed to be extended — not rushed.
