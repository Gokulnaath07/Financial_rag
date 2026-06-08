# Financial RAG Pipeline - Project TODO

This TODO list is based on the "Frozen Architecture Plan" for the financial document RAG pipeline.

## Implementation Order (STRICT)

Claude must implement functions in this exact order:

1. `structured_spans()`
2. `merge_multiline_headers()`
3. `build_section_tree()`
4. `compute_page_end()`
5. `compute_section_stats()`
6. `validate_sections()`

Only after extractor completion should chunking begin.

## Phase 1: Extractor Refactoring (Structural Intelligence)

**Target File**: `services/extractor.py`
**Goal**: Build a robust, hierarchical section tree without any chunking logic.

- [X] **1. Adjustments to `structured_spans()`**

  - [X] Implement precise Header Level Assignment:
    - [X] `ratio >= 1.6` → `level = 1`
    - [X] `ratio >= 1.35` → `level = 2`
    - [X] `ratio >= 1.15` → `level = 3`
    - [X] `else` → `level = 4` (or body if not header_candidate)
  - [X] Assign `"section_level": None` for body spans.
  - [X] Maintain the level jump clamp rule: `if previous_level and abs(level - previous_level) > 2: level = previous_level + 1`.
- [X] **2. Multi-line Header Merging**

  - [X] Delete `headers_by_proximity()` and `sort_headers()`.
  - [X] Implement `merge_multiline_headers(structured_spans)`:
    - [X] Merge consecutive `header_candidate` spans.
    - [X] **Crucial**: Stop merging once a non-header span appears (only merge consecutive headers).
    - [X] Conditions for merge: SAME page, y-distance <= 50, NO body spans between them.
    - [X] Merged text should simply be joined with a space.
  - [X] Application: Must happen *after* sorting the structured spans.
- [X] **3. Stack-Based Section Tree Building**

  - [X] Delete `attach_text_to_header()`.
  - [X] Implement `build_section_tree(sorted_spans)` using a stack logic:
    - [X] Iterate through `sorted_spans`.
    - [X] If `header_candidate`: Pop from stack `while stack and stack[-1]["section_level"] >= current_level:`
    - [X] Compute `section_path = parent_path + [header_text]`.
    - [X] Create a new section dictionary (`section_id` via uuid4, `header`, `section_level`, `section_path`, `page_start`, empty `page_end`, `content_blocks: []`).
    - [X] Append to global `sections` list and push to `section_stack`.
    - [X] If NOT `header_candidate` (body text): Attach to `stack[-1]["content_blocks"]`.
    - [X] *Handle Orphan Body Text*: If `section_stack` is empty and a body span appears, attach it to a synthetic root section.
      - **Root Section Definition**: `{"section_id": "root", "header": "__ROOT__", "section_level": 0, "section_path": [], "page_start": 1, "page_end": None, "content_blocks": []}`
- [X] **4. End-of-Section & Stats Computation**

  - [X] Implement `compute_page_end(sections)`:
    - [X] `page_end` = next section's `page_start - 1`.
    - [X] Last section's `page_end` = document total pages.
  - [X] Implement `compute_section_stats(sections)`:
    - [X] Join `content_blocks` using `"\n"` to get full text (`full_text = "\n".join(section["content_blocks"])`).
    - [X] Compute `char_count = len(full_text)`.
    - [X] Compute `token_estimate = len(full_text.split())`.
- [X] **5. Section Validation Layer (Strictly read-only post-stats)**

  - [X] Implement `validate_sections(sections)`:
    - [X] *Rule*: Validation must never recompute `token_estimate`. It only checks values.
    - [X] Flag and remove completely empty sections.
    - [X] Warn on "tiny" sections (`token_estimate < 20`).
    - [X] Flag oversized sections (`token_estimate > 8000`).
    - [X] Error if `page_start > page_end`.
    - [X] Warning if `section_level` jumps by > 2.
    - [X] Identify and merge duplicate consecutive headers.
    - [X] Ensure every `section_path` is unique.
    - [X] Ensure `section_path` depth matches `section_level` (`len(section_path) == section_level`).
  - [X] Print a cleanly formatted summary/diagnostic report of the extraction to the terminal.
- [X] **6. Update Pipeline Flow in `parse_pdf_blocks()`**

  - [X] Enforce the exact sequence:
    1. `extract_rawspans()` -> `grouping_by_pages()`
    2. Iterate through pages to extend `structured_spans`
    3. `structured.sort(...)` by `(page_no, y, x)`
    4. `merge_multiline_headers(structured)`
    5. `build_section_tree(structured)`
    6. `compute_page_end(sections)`
    7. `compute_section_stats(sections)`
    8. `validate_sections(sections)`
  - [X] Return the full Document object and remove the direct JSON file writing logic from the extractor itself.

---

## Phase 2: Chunker Design (Retrieval Optimizer)

**Target File**: `services/chunking.py`
**Goal**: Optimally slice the validated hierarchical sections for hybrid search.

- [X] **1. Chunking Entry Logic**

  - [X] Implement `chunk_sections(document)`.
  - [X] Iterate through valid sections and apply logic:
    - [X] If `token_estimate <= 500`: Handle as `"atomic"`.
    - [X] If `token_estimate > 500`: Handle as `"narrative"`.
- [X] **2. Narrative Chunking (Sliding Window)**

  - [X] Update / refactor `chunking_narrative_section(section)`:
    - [X] Split section content primarily on **paragraph boundaries**.
    - [X] Apply a sliding window with `max_tokens = 600`.
    - [X] Overlap should be `100` tokens (or approx last 2 sentences).
    - [X] Every chunk must strictly inherit: `header`, `document_id`, `section_id`, and `section_path`.
    - [X] Maintain a `chunk_index` that resets per section (0, 1, 2...).
- [X] **3. Chunk Validation Layer**

  - [X] Create chunk validation rules to run after chunking:
    - [X] If `token_count < 30`, merge with the previous chunk.
    - [X] If `token_count > 800`, dynamically split the chunk.
    - [X] Check for exact duplicate `chunk_text` and remove them.
    - [X] Assert overlap correctness for narrative chunks.
- [X] **4. Final Diagnostic Report**

  - [X] Print document statistics across chunks (Total Chunks, Avg Chunk Tokens, Largest Chunk Tokens).

---

## Phase 3: Embedding & Indexing (Retrieval Backbone)

**Target Files**: `services/embedding.py`, `services/indexing.py`, `config.py`
**Goal**: Encode chunks into normalized dense vectors and persist them in a queryable store.
**Design Reference**: `notes/phase_3_design.md` (full architecture, contracts, risks, gotchas).
**Stack**: `BAAI/bge-small-en-v1.5` (sentence-transformers) + ChromaDB (local persistent). OSS-only, no Docker, Python 3.12.

- [X] **1. Add embedding + vector libs to `requirements.txt`**

  - [X] Pin `sentence-transformers` and `chromadb`.
  - [X] Get user signoff before running `pip install`.
- [X] **2. Add `config.py` with env-backed defaults**

  - [X] `EMBED_MODEL` (default `BAAI/bge-small-en-v1.5`)
  - [X] `CHROMA_PATH` (default `storage/chroma`)
  - [X] `COLLECTION_NAME` (default `financial_docs`)
- [X] **3. Create `services/embedding.py` — Embedder layer**

  - [X] Module-level model singleton (load once per process).
  - [X] `embed_chunks(chunks, batch_size=32)` with BGE `"passage: "` prefix.
  - [X] L2-normalize all output vectors.
  - [X] `embed_query(text)` stub with `"query: "` prefix (Phase 4 will call).
  - [X] Assert + warn when input exceeds model max tokens (don't silently truncate).
  - [X] Include teaching comment showing raw HF tokenize → forward → pool → normalize equivalent.
- [X] **4. Add `validate_embedded_chunks(embedded)` gate**

  - [X] Dim consistency across all vectors.
  - [X] Norm within tolerance (||v|| ≈ 1.0 ± 1e-3).
  - [X] No NaN / Inf values.
  - [X] `chunk_id` uniqueness.
  - [X] Required metadata fields present.
  - [X] Log + drop invalid (mirror Phase 2's `validate_chunks` style).
- [X] **5. Create `services/indexing.py` — Indexer layer**

  - [X] `index_chunks(embedded, store_path, collection_name)` — idempotent upsert on `chunk_id`.
  - [X] `section_path` stored as `" > ".join(path)` (Chroma metadata = primitives only).
  - [X] `open_index(store_path, collection_name)` — read-only handle for Phase 4.
  - [X] `index_diagnostics(handle)` — count, dim, model, sample metadata.
  - [X] Hard-fail if `embedding` field missing on input.
- [X] **6. Extend `pipeline/pipeline_flow.py`**

  - [X] Add steps: `embed_chunks → validate_embedded_chunks → index_chunks → index_diagnostics`.
  - [X] Preserve existing `structured.json` + `chunk_doc.json` dumps.
- [X] **7. Emit Phase 3 debug diagnostics**

  - [X] `debug/embed_stats.json` — counts, dim, model, norm summary. NO raw vectors.
  - [X] `debug/index_report.json` — collection count, sample metadata.
- [X] **8. Wire `main.py /ingest` to full pipeline**

  - [X] Run parse → chunk → embed → validate → index synchronously.
  - [X] Return `{doc_id, chunk_count, indexed: true}`.
  - [X] Leave `/ask` untouched (Phase 4 owns retrieval).
- [X] **9. Confirm `storage/chroma/` gitignore coverage**

  - [X] Already covered by `storage/` rule. Note in commit message.
- [X] **10. Smoke test on Apple 10-K**

  - [X] Run `pipeline_flow.py` end-to-end.
  - [X] Record chunk count, embedding dim, index count in `notes/phase_3_design.md` "Open Items After Implementation".

---
