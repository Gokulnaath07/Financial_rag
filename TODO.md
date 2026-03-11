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

- [x] **1. Adjustments to `structured_spans()`**
  - [x] Implement precise Header Level Assignment:
    - [x] `ratio >= 1.6` → `level = 1`
    - [x] `ratio >= 1.35` → `level = 2`
    - [x] `ratio >= 1.15` → `level = 3`
    - [x] `else` → `level = 4` (or body if not header_candidate)
  - [x] Assign `"section_level": None` for body spans.
  - [x] Maintain the level jump clamp rule: `if previous_level and abs(level - previous_level) > 2: level = previous_level + 1`.

- [x] **2. Multi-line Header Merging**
  - [x] Delete `headers_by_proximity()` and `sort_headers()`.
  - [x] Implement `merge_multiline_headers(structured_spans)`:
    - [x] Merge consecutive `header_candidate` spans.
    - [x] **Crucial**: Stop merging once a non-header span appears (only merge consecutive headers).
    - [x] Conditions for merge: SAME page, y-distance <= 50, NO body spans between them.
    - [x] Merged text should simply be joined with a space.
  - [x] Application: Must happen *after* sorting the structured spans.

- [x] **3. Stack-Based Section Tree Building**
  - [x] Delete `attach_text_to_header()`.
  - [x] Implement `build_section_tree(sorted_spans)` using a stack logic:
    - [x] Iterate through `sorted_spans`.
    - [x] If `header_candidate`: Pop from stack `while stack and stack[-1]["section_level"] >= current_level:`
    - [x] Compute `section_path = parent_path + [header_text]`.
    - [x] Create a new section dictionary (`section_id` via uuid4, `header`, `section_level`, `section_path`, `page_start`, empty `page_end`, `content_blocks: []`).
    - [x] Append to global `sections` list and push to `section_stack`.
    - [x] If NOT `header_candidate` (body text): Attach to `stack[-1]["content_blocks"]`.
    - [x] *Handle Orphan Body Text*: If `section_stack` is empty and a body span appears, attach it to a synthetic root section.
      - **Root Section Definition**: `{"section_id": "root", "header": "__ROOT__", "section_level": 0, "section_path": [], "page_start": 1, "page_end": None, "content_blocks": []}`

- [x] **4. End-of-Section & Stats Computation**
  - [x] Implement `compute_page_end(sections)`:
    - [x] `page_end` = next section's `page_start - 1`.
    - [x] Last section's `page_end` = document total pages.
  - [x] Implement `compute_section_stats(sections)`:
    - [x] Join `content_blocks` using `"\n"` to get full text (`full_text = "\n".join(section["content_blocks"])`).
    - [x] Compute `char_count = len(full_text)`.
    - [x] Compute `token_estimate = len(full_text.split())`.

- [x] **5. Section Validation Layer (Strictly read-only post-stats)**
  - [x] Implement `validate_sections(sections)`:
    - [x] *Rule*: Validation must never recompute `token_estimate`. It only checks values.
    - [x] Flag and remove completely empty sections.
    - [x] Warn on "tiny" sections (`token_estimate < 20`).
    - [x] Flag oversized sections (`token_estimate > 8000`).
    - [x] Error if `page_start > page_end`.
    - [x] Warning if `section_level` jumps by > 2.
    - [x] Identify and merge duplicate consecutive headers.
    - [x] Ensure every `section_path` is unique.
    - [x] Ensure `section_path` depth matches `section_level` (`len(section_path) == section_level`).
  - [x] Print a cleanly formatted summary/diagnostic report of the extraction to the terminal.

- [x] **6. Update Pipeline Flow in `parse_pdf_blocks()`**
  - [x] Enforce the exact sequence:
    1. `extract_rawspans()` -> `grouping_by_pages()`
    2. Iterate through pages to extend `structured_spans`
    3. `structured.sort(...)` by `(page_no, y, x)`
    4. `merge_multiline_headers(structured)`
    5. `build_section_tree(structured)`
    6. `compute_page_end(sections)`
    7. `compute_section_stats(sections)`
    8. `validate_sections(sections)`
  - [x] Return the full Document object and remove the direct JSON file writing logic from the extractor itself.

---

## Phase 2: Chunker Design (Retrieval Optimizer)
**Target File**: `services/chunking.py`
**Goal**: Optimally slice the validated hierarchical sections for hybrid search.

- [x] **1. Chunking Entry Logic**
  - [x] Implement `chunk_sections(document)`.
  - [x] Iterate through valid sections and apply logic:
    - [x] If `token_estimate <= 500`: Handle as `"atomic"`.
    - [x] If `token_estimate > 500`: Handle as `"narrative"`.

- [x] **2. Narrative Chunking (Sliding Window)**
  - [x] Update / refactor `chunking_narrative_section(section)`:
    - [x] Split section content primarily on **paragraph boundaries**.
    - [x] Apply a sliding window with `max_tokens = 600`.
    - [x] Overlap should be `100` tokens (or approx last 2 sentences).
    - [x] Every chunk must strictly inherit: `header`, `document_id`, `section_id`, and `section_path`.
    - [x] Maintain a `chunk_index` that resets per section (0, 1, 2...).

- [x] **3. Chunk Validation Layer**
  - [x] Create chunk validation rules to run after chunking:
    - [x] If `token_count < 30`, merge with the previous chunk.
    - [x] If `token_count > 800`, dynamically split the chunk.
    - [x] Check for exact duplicate `chunk_text` and remove them.
    - [x] Assert overlap correctness for narrative chunks.

- [x] **4. Final Diagnostic Report**
  - [x] Print document statistics across chunks (Total Chunks, Avg Chunk Tokens, Largest Chunk Tokens).

---
