# CLAUDE.md - Project Instructions and Guidelines

## Core Architectural Principle
This project follows a strict **"Frozen Architecture"** for Financial RAG document processing. 
As an AI coding agent, you must **NOT** deviate from the defined layer responsibilities:

1. **Extractor** (`services/extractor.py`) = **Structure Builder**
   - Answers: "What is this document structurally?"
   - Must output a pristine, nested hierarchical section tree.
   - Absolutely NO chunking logic or text manipulation here.
2. **Chunker** (`services/chunking.py`) = **Retrieval Optimizer**
   - Answers: "How should this structure be sliced for semantic retrieval?"
   - Translates sections into atomic or narrative overlapping chunks optimized for max 600 tokens.
3. **Validation** = **Structural Integrity Gate**
   - Each phase (Extractor and Chunker) enforces post-processing validation.
   - Diagnostically flags or removes bad data before the pipeline proceeds.

*Critical Rule: NO CROSS-LAYER LOGIC LEAKAGE.*

### Extractor Output Contract
Extractor must return a fully structured Document object containing validated Section objects but no chunks.
**Extractor implementation is frozen.** Claude must not modify `services/extractor.py`.

## Primary Data Models
Never change these schemas without explicit instruction or approval. Code implementation should match these contracts.

### 1. Document
```python
{
    "document_id": str,
    "file_name": str,
    "total_pages": int,
    "sections": list[Section]
}
```

### 2. Section
```python
{
    "section_id": str,          # uuid4
    "parent_section_id": str | None, # parent reference
    "header": str,              # Extracted header text
    "section_level": int,       # Stack-based hierarchy level (1, 2, 3...)
    "section_path": list[str],  # E.g. ["PART I", "Item 1", "Company Background"]
    "page_start": int,
    "page_end": int,
    "content_blocks": list[str],
    "char_count": int,
    "token_estimate": int       # Used for early chunking logic
}
```

*Root Section Note*: A synthetic root section with `section_level = 0` and `section_id = "root"` may be created to attach orphan body text before the first header.

### 3. Chunk
```python
{
    "chunk_id": str,
    "document_id": str,
    "section_id": str,
    "header": str,
    "section_path": list[str],
    "chunk_index": int,         # Resets per section: 0, 1, 2...
    "chunk_text": str,
    "page_start": int,
    "page_end": int,
    "chunk_type": str,          # "atomic" | "narrative"
    "token_count": int,
    "char_count": int
}
```

## Agent Coding Guidelines
- **Always adhere to `TODO.md`**: Follow the exact sequence. Extractor phase (Phase 1) is complete. The current focus is on Phase 2 (Chunker Design).
- **Python Conventions**: Use standard Python conventions. Keep imports clean and localized to the top of the file unless strictly necessary for scoped logic.
- **No side-effects in Extractor**: Ensure `extractor.py` just orchestrates and returns the parsed objects. It should not contain hardcoded JSON file dumping logic inside extraction methods; that belongs in a pipeline or orchestration script.
- **Stack-based Tree Building**: Use a standard python list `[]` as a stack for building hierarchy, utilizing `.pop()` and tracking depth using `section_level`.
- **Estimation Math**: For Phase 1 and 2, `token_estimate = len(text.split())` is an acceptable proxy. Do not introduce heavy embedding-based tokenizers like `tiktoken` yet unless required by the next phase.
- **Span Ordering**: `structured_spans` must preserve page and positional ordering so that sorting by `(page_no, y, x)` produces deterministic structure for the subsequent steps.
- **Header Detection Rule**: A span must satisfy BOTH the `is_header` candidate flag AND the font size ratio threshold before being treated as a section header.
- **Header Merge Rule**: Only consecutive header spans may be merged. Merging must stop immediately when a body span appears.
- **Section Creation Rule**: Every new section must inherit its `parent_section_id` from the current top of the stack.
- **Section Level Constraint**: Section levels must increase or decrease by at most 2 between consecutive headers.
- **Always ask before adding new libraries**: Rely strictly on `fitz` (PyMuPDF) and standard library items first.

## Hard Rules

Extractor MUST NOT:
- create chunks
- split text for token size
- modify section hierarchy after tree building

Chunker MUST NOT:
- detect headers
- modify section levels
- change section_path
- modify section `content_blocks` (text rewriting is forbidden)

## Implementation Order (STRICT)

### Phase 1: Extractor Pipeline Flow (COMPLETE)
```text
raw spans → structured spans → [sort] → header merge → section tree → metadata → validation
```

*(Extractor phase functions `structured_spans`, `merge_multiline_headers`, `build_section_tree`, `compute_page_end`, `compute_section_stats`, and `validate_sections` are now complete.)*

### Phase 2: Chunker Pipeline Flow (CURRENT)
```text
validated sections → chunking entry logic → narrative chunking → chunk validation → diagnostic report
```

Claude must implement Phase 2 functions in this exact order:

1. `chunk_sections()`
2. `chunking_narrative_section()`
3. Chunk validation logic
4. Final diagnostic reporting

## Function Contracts

To ensure responsibilities stay isolated, functions must adhere to these exact definitions:

### Phase 1: Extractor (Completed)

- **`structured_spans(raw_spans)`**:
  - Input: grouped page spans / raw spans
  - Output: structured span objects with `is_header` candidate flag and assigned `section_level`.

- **`merge_multiline_headers(sorted_structured_spans)`**:
  - Input: sorted structured spans
  - Output: spans with consecutively adjacent header lines merged.

- **`build_section_tree(merged_spans)`**:
  - Input: structurally merged spans
  - Output: ordered list of hierarchical `Section` objects.

- **`compute_page_end(sections)`**:
  - Input: sections list
  - Output: sections list with updated `page_end` values.

- **`compute_section_stats(sections)`**:
  - Input: sections list
  - Output: sections list with fully populated `char_count` and `token_estimate`.

- **`validate_sections(sections)`**:
  - Input: sections list
  - Output: cleaned, corrected, and strictly validated sections list ready for chunking.
  - *Invariant Check 1*: Must enforce that `len(section_path) == section_level` to guarantee hierarchy consistency.
  - *Invariant Check 2*: Sections must remain ordered by `page_start` and header hierarchy.
  - *Invariant Check 3*: Sections with no `content_blocks` and no children must be removed.

### Phase 2: Chunker (Current Focus)

- **`chunk_sections(document)`**:
  - Input: Fully validated Document object from the Extractor layer.
  - Output: Iterates over sections and dispatches to appropriate chunking logic.
  - *Chunking Rule*:
    - If `section.token_estimate <= 500` → create ONE atomic chunk.
    - If `section.token_estimate > 500` → call `chunking_narrative_section(section)`.

- **`chunking_narrative_section(section)`**:
  - Input: A single Section object.
  - Output: List of overlapping Chunk objects, split by paragraph boundaries with sliding window.
  - *Invariant Check*: Chunks must STRICTLY inherit `header`, `document_id`, `section_id`, and `section_path`.
  - *Sliding Window Parameters (Narrative Sections Only)*:
    - `max_tokens = 600`
    - `overlap = 100`
    - These parameters apply only when `section.token_estimate > 500`.
    - Atomic sections (≤500 tokens) must remain intact and produce exactly one chunk.
