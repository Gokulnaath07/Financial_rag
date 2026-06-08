import logging
import threading

import numpy as np
from sentence_transformers import SentenceTransformer

from config import EMBED_MODEL, EMBED_BATCH_SIZE


# sentence-transformers.encode() under the hood:
#   tokenizer(text, padding=True, truncation=True, return_tensors='pt')
#   model(**inputs).last_hidden_state
#   mean_pool(hidden_states, attention_mask)
#   F.normalize(pooled, p=2, dim=1) if normalize_embeddings=True
# This wrapper handles batching, normalization, and device placement.


logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None
_model_lock = threading.Lock()
_model_name_loaded: str | None = None


def _get_model(model_name: str) -> SentenceTransformer:
    """Load model once per process, cache by name."""
    global _model, _model_name_loaded
    with _model_lock:
        if _model is None or _model_name_loaded != model_name:
            _model = SentenceTransformer(model_name)
            _model_name_loaded = model_name
        return _model


def embed_chunks(
    chunks: list[dict],
    model_name: str | None = None,
    batch_size: int | None = None,
) -> list[dict]:
    """Encode chunk_text into L2-normalized dense vectors.

    Returns EmbeddedChunk dicts = original Chunk fields + embedding, embedding_model, embedding_dim.
    """

    if not chunks:
        return []

    model_name = model_name or EMBED_MODEL
    batch_size = batch_size or EMBED_BATCH_SIZE

    model = _get_model(model_name)
    max_seq_length = model.max_seq_length

    # BGE convention: passage prefix for indexing-side encoding
    texts = ["passage: " + c["chunk_text"] for c in chunks]

    for c in chunks:
        if c["token_count"] > max_seq_length:
            logger.warning(
                "Chunk %s token_count=%d exceeds model max_seq_length=%d; "
                "sentence-transformers will truncate at encode time.",
                c["chunk_id"], c["token_count"], max_seq_length,
            )

    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    embedded = []
    for chunk, vector in zip(chunks, vectors):
        new_chunk = dict(chunk)
        new_chunk["embedding"] = vector.tolist()
        new_chunk["embedding_model"] = model_name
        new_chunk["embedding_dim"] = int(vector.shape[0])
        embedded.append(new_chunk)

    assert len(embedded) == len(chunks)
    dims = {e["embedding_dim"] for e in embedded}
    assert len(dims) == 1, f"Inconsistent embedding dims: {dims}"

    for sample in embedded[:5]:
        norm = float(np.linalg.norm(np.array(sample["embedding"])))
        assert abs(norm - 1.0) < 1e-3, f"Vector not normalized: norm={norm}"

    return embedded


def embed_query(text: str, model_name: str | None = None) -> list[float]:
    """Encode a single query string with BGE query prefix. Used by Phase 4."""

    model_name = model_name or EMBED_MODEL
    model = _get_model(model_name)
    vector = model.encode(
        "query: " + text,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vector.tolist()


def validate_embedded_chunks(embedded: list[dict]) -> list[dict]:
    """Post-embedding validation gate. Logs + drops invalid entries."""

    if not embedded:
        print_embed_diagnostics(0, 0, {})
        return []

    input_count = len(embedded)
    dropped_by_reason = {
        "dim_mismatch": 0,
        "norm_violation": 0,
        "nan_inf": 0,
        "duplicate_id": 0,
        "missing_metadata": 0,
    }

    required_fields = [
        "chunk_id", "document_id", "section_id", "header",
        "section_path", "page_start", "page_end", "chunk_type",
    ]

    # --- 1. Determine majority dim ---
    dim_counts: dict[int, int] = {}
    for e in embedded:
        d = e.get("embedding_dim")
        if isinstance(d, int):
            dim_counts[d] = dim_counts.get(d, 0) + 1
    majority_dim = max(dim_counts, key=dim_counts.get) if dim_counts else None

    seen_ids: set[str] = set()
    valid: list[dict] = []

    for e in embedded:
        missing = [f for f in required_fields if f not in e]
        if missing:
            print(
                f"  [EMBED VALIDATION] Dropped {e.get('chunk_id', '?')}: "
                f"missing metadata fields {missing}"
            )
            dropped_by_reason["missing_metadata"] += 1
            continue

        if e.get("embedding_dim") != majority_dim:
            print(
                f"  [EMBED VALIDATION] Dropped {e['chunk_id']}: "
                f"dim {e.get('embedding_dim')} != majority {majority_dim}"
            )
            dropped_by_reason["dim_mismatch"] += 1
            continue

        vec = np.array(e["embedding"])
        if not np.isfinite(vec).all():
            print(
                f"  [EMBED VALIDATION] Dropped {e['chunk_id']}: "
                f"vector contains NaN or Inf"
            )
            dropped_by_reason["nan_inf"] += 1
            continue

        norm = float(np.linalg.norm(vec))
        if abs(norm - 1.0) > 1e-3:
            print(
                f"  [EMBED VALIDATION] Dropped {e['chunk_id']}: "
                f"norm {norm:.6f} outside tolerance"
            )
            dropped_by_reason["norm_violation"] += 1
            continue

        if e["chunk_id"] in seen_ids:
            print(
                f"  [EMBED VALIDATION] Dropped duplicate chunk_id {e['chunk_id']}"
            )
            dropped_by_reason["duplicate_id"] += 1
            continue
        seen_ids.add(e["chunk_id"])

        valid.append(e)

    print_embed_diagnostics(input_count, len(valid), dropped_by_reason)
    return valid


def print_embed_diagnostics(
    input_count: int,
    valid_count: int,
    dropped_by_reason: dict,
) -> None:
    """Print embedding validation statistics."""

    print("\n=== Embedding Validation Diagnostics ===")
    print(f"  Input Count   : {input_count}")
    print(f"  Valid Count   : {valid_count}")
    print(f"  Dropped Total : {input_count - valid_count}")
    if dropped_by_reason:
        for reason, count in dropped_by_reason.items():
            print(f"    - {reason:18s}: {count}")
    print("========================================\n")
