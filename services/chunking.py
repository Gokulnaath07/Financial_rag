import uuid


def chunk_sections(document: dict) -> list[dict]:
    """Chunking entry point.

    Input:  Fully validated Document object from the Extractor layer.
    Output: List of Chunk dicts across all sections.

    Dispatching rule:
        token_estimate <= 500  ->  ONE atomic chunk
        token_estimate >  500  ->  chunking_narrative_section()
    """

    document_id = document["document_id"]
    all_chunks = []

    for section in document["sections"]:
        if section["token_estimate"] <= 500:
            # Atomic: single chunk wrapping entire section content
            chunk_text = "\n".join(section["content_blocks"])
            chunk = {
                "chunk_id": str(uuid.uuid4()),
                "document_id": document_id,
                "section_id": section["section_id"],
                "header": section["header"],
                "section_path": section["section_path"],
                "chunk_index": 0,
                "chunk_text": chunk_text,
                "page_start": section["page_start"],
                "page_end": section["page_end"],
                "chunk_type": "atomic",
                "token_count": len(chunk_text.split()),
                "char_count": len(chunk_text),
            }
            all_chunks.append(chunk)
        else:
            # Narrative: sliding-window chunking
            narrative_chunks = chunking_narrative_section(section, document_id)
            all_chunks.extend(narrative_chunks)

    all_chunks = validate_chunks(all_chunks)
    print_chunk_diagnostics(all_chunks)
    return all_chunks


def chunking_narrative_section(section: dict, document_id: str) -> list[dict]:
    """Split a large section (>500 tokens) into overlapping chunks.

    Uses paragraph-boundary-aware sliding window:
        max_tokens = 600
        overlap    = 100

    Every chunk strictly inherits header, document_id, section_id, section_path.
    chunk_index resets per section (0, 1, 2...).
    """

    max_tokens = 600
    overlap = 100

    blocks = section["content_blocks"]
    if not blocks:
        return []

    block_tokens = [len(b.split()) for b in blocks]

    chunks = []
    chunk_index = 0
    start = 0

    while start < len(blocks):
        # Accumulate blocks from start until we hit max_tokens
        end = start
        current_tokens = 0

        while end < len(blocks) and current_tokens + block_tokens[end] <= max_tokens:
            current_tokens += block_tokens[end]
            end += 1

        # If a single block exceeds max_tokens, include it anyway to guarantee progress
        if end == start:
            end = start + 1

        chunk_text = "\n".join(blocks[start:end])
        chunk = {
            "chunk_id": str(uuid.uuid4()),
            "document_id": document_id,
            "section_id": section["section_id"],
            "header": section["header"],
            "section_path": section["section_path"],
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "page_start": section["page_start"],
            "page_end": section["page_end"],
            "chunk_type": "narrative",
            "token_count": len(chunk_text.split()),
            "char_count": len(chunk_text),
        }
        chunks.append(chunk)
        chunk_index += 1

        # All blocks consumed
        if end >= len(blocks):
            break

        # Calculate overlap: walk backwards from end to collect ~overlap tokens
        overlap_tokens = 0
        new_start = end
        for j in range(end - 1, start - 1, -1):
            if overlap_tokens + block_tokens[j] > overlap:
                break
            overlap_tokens += block_tokens[j]
            new_start = j

        # Ensure forward progress to prevent infinite loop
        if new_start <= start:
            new_start = end

        start = new_start

    return chunks


def validate_chunks(chunks: list[dict]) -> list[dict]:
    """Post-chunking validation.

    Rules:
        1. Remove exact duplicate chunk_text.
        2. Merge tiny chunks (token_count < 30) into the previous chunk in the same section.
        3. Dynamically split oversized chunks (token_count > 800).
        4. Re-index chunk_index per section after all mutations.
        5. Assert overlap correctness for consecutive narrative chunks.
    """

    if not chunks:
        return chunks

    # --- 1. Remove exact duplicate chunk_text ---
    seen_texts = set()
    deduped = []
    for chunk in chunks:
        if chunk["chunk_text"] in seen_texts:
            print(
                f"  [CHUNK VALIDATION] Removed duplicate chunk: "
                f"{chunk['chunk_id']} (section: {chunk['header']})"
            )
            continue
        seen_texts.add(chunk["chunk_text"])
        deduped.append(chunk)
    chunks = deduped

    # --- 2. Merge tiny chunks (< 30 tokens) with previous in same section ---
    merged = []
    for chunk in chunks:
        if (
            chunk["token_count"] < 30
            and merged
            and merged[-1]["section_id"] == chunk["section_id"]
        ):
            prev = merged[-1]
            prev["chunk_text"] = prev["chunk_text"] + "\n" + chunk["chunk_text"]
            prev["token_count"] = len(prev["chunk_text"].split())
            prev["char_count"] = len(prev["chunk_text"])
            prev["page_end"] = max(prev["page_end"], chunk["page_end"])
            print(
                f"  [CHUNK VALIDATION] Merged tiny chunk ({chunk['token_count']} tokens) "
                f"into previous chunk {prev['chunk_id']}"
            )
        else:
            merged.append(chunk)
    chunks = merged

    # --- 3. Split oversized chunks (> 800 tokens) ---
    final = []
    for chunk in chunks:
        if chunk["token_count"] > 800:
            print(
                f"  [CHUNK VALIDATION] Splitting oversized chunk {chunk['chunk_id']} "
                f"({chunk['token_count']} tokens)"
            )
            sub_chunks = _split_oversized_chunk(chunk)
            final.extend(sub_chunks)
        else:
            final.append(chunk)
    chunks = final

    # --- 4. Re-index chunk_index per section ---
    section_counters = {}
    for chunk in chunks:
        sid = chunk["section_id"]
        if sid not in section_counters:
            section_counters[sid] = 0
        chunk["chunk_index"] = section_counters[sid]
        section_counters[sid] += 1

    # --- 5. Assert overlap correctness for narrative chunks ---
    _check_overlap_correctness(chunks)

    return chunks


def _split_oversized_chunk(chunk: dict) -> list[dict]:
    """Emergency-split a chunk exceeding 800 tokens into <=600-token sub-chunks."""

    max_tokens = 600
    words = chunk["chunk_text"].split()
    sub_chunks = []
    start = 0

    while start < len(words):
        end = min(start + max_tokens, len(words))
        sub_text = " ".join(words[start:end])
        sub_chunk = {
            "chunk_id": str(uuid.uuid4()),
            "document_id": chunk["document_id"],
            "section_id": chunk["section_id"],
            "header": chunk["header"],
            "section_path": chunk["section_path"],
            "chunk_index": 0,  # will be re-indexed by validate_chunks
            "chunk_text": sub_text,
            "page_start": chunk["page_start"],
            "page_end": chunk["page_end"],
            "chunk_type": chunk["chunk_type"],
            "token_count": len(sub_text.split()),
            "char_count": len(sub_text),
        }
        sub_chunks.append(sub_chunk)
        start = end

    return sub_chunks


def _check_overlap_correctness(chunks: list[dict]) -> None:
    """Warn if consecutive narrative chunks in the same section share no overlap."""

    prev = None
    for chunk in chunks:
        if (
            prev is not None
            and prev["section_id"] == chunk["section_id"]
            and prev["chunk_type"] == "narrative"
            and chunk["chunk_type"] == "narrative"
        ):
            prev_words = prev["chunk_text"].split()
            curr_words = chunk["chunk_text"].split()

            # Compare tail of previous chunk with head of current chunk
            tail_size = min(100, len(prev_words))
            head_size = min(100, len(curr_words))
            tail_words = set(prev_words[-tail_size:])
            head_words = set(curr_words[:head_size])
            shared = len(tail_words & head_words)

            if shared < 5:
                print(
                    f"  [CHUNK VALIDATION WARNING] Low overlap between "
                    f"narrative chunks {prev['chunk_id']} and {chunk['chunk_id']} "
                    f"(shared words: {shared})"
                )
        prev = chunk


def print_chunk_diagnostics(chunks: list[dict]) -> None:
    """Print document statistics across chunks."""

    print("\n=== Chunk Diagnostics ===")

    if not chunks:
        print("  No chunks generated.")
        print("=========================\n")
        return

    total = len(chunks)
    token_counts = [c["token_count"] for c in chunks]
    avg_tokens = sum(token_counts) / total
    max_tok = max(token_counts)
    min_tok = min(token_counts)
    atomic_count = sum(1 for c in chunks if c["chunk_type"] == "atomic")
    narrative_count = sum(1 for c in chunks if c["chunk_type"] == "narrative")

    print(f"  Total Chunks        : {total}")
    print(f"  Atomic Chunks       : {atomic_count}")
    print(f"  Narrative Chunks    : {narrative_count}")
    print(f"  Avg Chunk Tokens    : {avg_tokens:.1f}")
    print(f"  Min Chunk Tokens    : {min_tok}")
    print(f"  Largest Chunk Tokens: {max_tok}")
    print("=========================\n")
