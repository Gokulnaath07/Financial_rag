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

- [ ] **1. Adjustments to `structured_spans()`**
  - [ ] Implement precise Header Level Assignment:
    - [ ] `ratio >= 1.6` → `level = 1`
    - [ ] `ratio >= 1.35` → `level = 2`
    - [ ] `ratio >= 1.15` → `level = 3`
    - [ ] `else` → `level = 4` (or body if not header_candidate)
  - [ ] Assign `"section_level": None` for body spans.
  - [ ] Maintain the level jump clamp rule: `if previous_level and abs(level - previous_level) > 2: level = previous_level + 1`.

- [ ] **2. Multi-line Header Merging**
  - [ ] Delete `headers_by_proximity()` and `sort_headers()`.
  - [ ] Implement `merge_multiline_headers(structured_spans)`:
    - [ ] Merge consecutive `header_candidate` spans.
    - [ ] **Crucial**: Stop merging once a non-header span appears (only merge consecutive headers).
    - [ ] Conditions for merge: SAME page, y-distance <= 50, NO body spans between them.
    - [ ] Merged text should simply be joined with a space.
  - [ ] Application: Must happen *after* sorting the structured spans.

- [ ] **3. Stack-Based Section Tree Building**
  - [ ] Delete `attach_text_to_header()`.
  - [ ] Implement `build_section_tree(sorted_spans)` using a stack logic:
    - [ ] Iterate through `sorted_spans`.
    - [ ] If `header_candidate`: Pop from stack `while stack and stack[-1]["section_level"] >= current_level:`
    - [ ] Compute `section_path = parent_path + [header_text]`.
    - [ ] Create a new section dictionary (`section_id` via uuid4, `header`, `section_level`, `section_path`, `page_start`, empty `page_end`, `content_blocks: []`).
    - [ ] Append to global `sections` list and push to `section_stack`.
    - [ ] If NOT `header_candidate` (body text): Attach to `stack[-1]["content_blocks"]`.
    - [ ] *Handle Orphan Body Text*: If `section_stack` is empty and a body span appears, attach it to a synthetic root section.
      - **Root Section Definition**: `{"section_id": "root", "header": "__ROOT__", "section_level": 0, "section_path": [], "page_start": 1, "page_end": None, "content_blocks": []}`

- [ ] **4. End-of-Section & Stats Computation**
  - [ ] Implement `compute_page_end(sections)`:
    - [ ] `page_end` = next section's `page_start - 1`.
    - [ ] Last section's `page_end` = document total pages.
  - [ ] Implement `compute_section_stats(sections)`:
    - [ ] Join `content_blocks` using `"\n"` to get full text (`full_text = "\n".join(section["content_blocks"])`).
    - [ ] Compute `char_count = len(full_text)`.
    - [ ] Compute `token_estimate = len(full_text.split())`.

- [ ] **5. Section Validation Layer (Strictly read-only post-stats)**
  - [ ] Implement `validate_sections(sections)`:
    - [ ] *Rule*: Validation must never recompute `token_estimate`. It only checks values.
    - [ ] Flag and remove completely empty sections.
    - [ ] Warn on "tiny" sections (`token_estimate < 20`).
    - [ ] Flag oversized sections (`token_estimate > 8000`).
    - [ ] Error if `page_start > page_end`.
    - [ ] Warning if `section_level` jumps by > 2.
    - [ ] Identify and merge duplicate consecutive headers.
    - [ ] Ensure every `section_path` is unique.
    - [ ] Ensure `section_path` depth matches `section_level` (`len(section_path) == section_level`).
  - [ ] Print a cleanly formatted summary/diagnostic report of the extraction to the terminal.

- [ ] **6. Update Pipeline Flow in `parse_pdf_blocks()`**
  - [ ] Enforce the exact sequence:
    1. `extract_rawspans()` -> `grouping_by_pages()`
    2. Iterate through pages to extend `structured_spans`
    3. `structured.sort(...)` by `(page_no, y, x)`
    4. `merge_multiline_headers(structured)`
    5. `build_section_tree(structured)`
    6. `compute_page_end(sections)`
    7. `compute_section_stats(sections)`
    8. `validate_sections(sections)`
  - [ ] Return the full Document object and remove the direct JSON file writing logic from the extractor itself.

---

## Phase 2: Chunker Design (Retrieval Optimizer)
**Target File**: `services/chunking.py`
**Goal**: Optimally slice the validated hierarchical sections for hybrid search.

- [ ] **1. Chunking Entry Logic**
  - [ ] Implement `chunk_sections(document)`.
  - [ ] Iterate through valid sections and apply logic:
    - [ ] If `token_estimate <= 500`: Handle as `"atomic"`.
    - [ ] If `token_estimate > 500`: Handle as `"narrative"`.

- [ ] **2. Narrative Chunking (Sliding Window)**
  - [ ] Update / refactor `chunking_narrative_section(section)`:
    - [ ] Split section content primarily on **paragraph boundaries**.
    - [ ] Apply a sliding window with `max_tokens = 600`.
    - [ ] Overlap should be `100` tokens (or approx last 2 sentences).
    - [ ] Every chunk must strictly inherit: `header`, `document_id`, `section_id`, and `section_path`.
    - [ ] Maintain a `chunk_index` that resets per section (0, 1, 2...).

- [ ] **3. Chunk Validation Layer**
  - [ ] Create chunk validation rules to run after chunking:
    - [ ] If `token_count < 30`, merge with the previous chunk.
    - [ ] If `token_count > 800`, dynamically split the chunk.
    - [ ] Check for exact duplicate `chunk_text` and remove them.
    - [ ] Assert overlap correctness for narrative chunks.

- [ ] **4. Final Diagnostic Report**
  - [ ] Print document statistics across chunks (Total Chunks, Avg Chunk Tokens, Largest Chunk Tokens).

---
