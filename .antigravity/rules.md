# Antigravity Architecture Guardrails
Financial RAG Pipeline

This file enforces the **Frozen Architecture** defined in CLAUDE.md.
Generated code must comply with these constraints.

--------------------------------------------------
1. Architecture Layers
--------------------------------------------------

The system follows a strict three-layer architecture:

Extractor → Chunker → Retrieval

Each layer has isolated responsibilities.

--------------------------------------------------
Extractor Layer
--------------------------------------------------

File: services/extractor.py

Allowed responsibilities:
- PDF span extraction
- Header detection
- Section hierarchy construction
- Section metadata generation
- Section validation

Forbidden actions:
- Chunk generation
- Token-based splitting
- Retrieval logic
- Embedding generation
- Vector database interaction

Extractor output must be:

Document → list[Section]

--------------------------------------------------
Chunker Layer
--------------------------------------------------

File: services/chunking.py

Allowed responsibilities:
- Slice sections into retrieval chunks
- Sliding window chunking
- Chunk validation

Forbidden actions:
- Header detection
- Section hierarchy modification
- Section path rewriting
- Modifying section content_blocks

Chunker output must be:

Section → list[Chunk]

--------------------------------------------------
2. Cross-Layer Import Restrictions
--------------------------------------------------

Extractor MUST NOT import:

services.chunking
retrieval
vector
embedding
llm

Chunker MUST NOT import:

services.extractor

--------------------------------------------------
3. Schema Integrity
--------------------------------------------------

The following models must not change without approval:

Document
Section
Chunk

Required invariants:

len(section_path) == section_level  
sections ordered by page_start  
chunk_index resets per section  
token_estimate derived from section text only

--------------------------------------------------
4. Library Restrictions
--------------------------------------------------

Allowed libraries:

fitz (PyMuPDF)  
uuid  
typing  
dataclasses  
Python standard library

Forbidden without approval:

langchain  
llamaindex  
tiktoken  
pandas  
numpy  
transformers  
vector database clients

--------------------------------------------------
5. Extractor Pipeline Order
--------------------------------------------------

Extractor must follow this pipeline exactly:

raw spans
→ structured spans
→ sort (page_no, y, x)
→ header merge
→ section tree
→ compute metadata
→ validation

Function implementation order:

structured_spans()  
merge_multiline_headers()  
build_section_tree()  
compute_page_end()  
compute_section_stats()  
validate_sections()

--------------------------------------------------
6. Header Processing Rules
--------------------------------------------------

Header detection requires BOTH:

is_header candidate flag  
font size ratio threshold

Header merging rules:

- only consecutive header spans
- same page
- y-distance ≤ 50
- stop merging when a body span appears

--------------------------------------------------
7. Section Tree Constraints
--------------------------------------------------

Hierarchy must follow stack rules:

push header when level increases  
pop stack until parent level when level decreases

Additional constraints:

section_level change ≤ 2  
parent_section_id inherited from stack top  
root section used for orphan body text

Root section definition:

section_id = "root"  
section_level = 0  
section_path = []

--------------------------------------------------
8. Validation Rules
--------------------------------------------------

Validation must be read-only.

Validation must NOT recompute:

token_estimate  
char_count

Validation must enforce:

len(section_path) == section_level  
sections ordered by page_start  
remove empty sections  
warn on tiny sections  
warn on oversized sections

--------------------------------------------------
9. Chunking Rules
--------------------------------------------------

Chunking must occur ONLY in the Chunker layer.

Chunk types:

atomic ≤ 500 tokens  
narrative > 500 tokens

Narrative chunk constraints:

max_tokens = 600  
overlap = 100  
paragraph-aware splitting

Chunks must inherit:

document_id  
section_id  
section_path  
header

--------------------------------------------------
10. File Ownership
--------------------------------------------------

Extractor logic must exist only in:

services/extractor.py

Chunking logic must exist only in:

services/chunking.py

--------------------------------------------------
11. Safety Enforcement
--------------------------------------------------

If a generated change violates any rule in this file:

Reject the change.  
Do not implement unsafe architecture modifications.  
Request clarification instead.