import json
import logging
import os
from collections import defaultdict
from datetime import datetime

import chromadb

from config import (
    CHROMA_PATH,
    COLLECTION_NAME,
    DENSE_CANDIDATES,
    SPARSE_CANDIDATES,
    RRF_K,
    RETRIEVAL_TOP_K,
    RERANK_ENABLED,
)
from services.embedding import embed_query
from services.bm25_index import open_bm25_index, bm25_search
from services.reranker import rerank as cross_encoder_rerank


logger = logging.getLogger(__name__)


def _rrf_fuse(
    dense_ids: list[str],
    sparse_ids: list[str],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = sum 1/(k + rank_R(d)) across both rankings."""

    scores: dict[str, float] = defaultdict(float)

    for rank, cid in enumerate(dense_ids, start=1):
        scores[cid] += 1.0 / (k + rank)

    for rank, cid in enumerate(sparse_ids, start=1):
        scores[cid] += 1.0 / (k + rank)

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return fused


def _hydrate(
    collection,
    fused: list[tuple[str, float]],
    fused_score_map: dict[str, float],
) -> list[dict]:
    """Fetch text + metadata from Chroma for each fused id, return RetrievedChunk dicts in fused order."""

    if not fused:
        return []

    all_ids = [cid for cid, _ in fused]
    bulk = collection.get(ids=all_ids, include=["documents", "metadatas"])

    fetched_ids = bulk.get("ids") or []
    documents = bulk.get("documents") or []
    metadatas = bulk.get("metadatas") or []

    by_id: dict[str, dict] = {}
    for i, cid in enumerate(fetched_ids):
        doc = documents[i] if i < len(documents) else ""
        meta = metadatas[i] if i < len(metadatas) else {}
        by_id[cid] = {
            "document": doc or "",
            "metadata": meta or {},
        }

    hydrated: list[dict] = []
    for cid, _ in fused:
        if cid not in by_id:
            continue
        meta = by_id[cid]["metadata"]
        hydrated.append({
            "chunk_id": cid,
            "chunk_text": by_id[cid]["document"],
            "score": fused_score_map[cid],
            "section_path": meta.get("section_path", ""),
            "page_start": int(meta.get("page_start", 0)),
            "page_end": int(meta.get("page_end", 0)),
            "header": meta.get("header", ""),
        })

    return hydrated


def _write_retrieve_trace(
    query: str,
    dense_hits: list[str],
    sparse_hits: list[tuple[str, float]],
    fused: list[tuple[str, float]],
    reranked: list[dict],
    config_used: dict,
) -> None:
    """Write the last-call retrieval trace to debug/retrieve_trace.json (overwrites per call)."""

    debug_dir = "debug"
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, "retrieve_trace.json")

    dense_stage = [
        {"chunk_id": cid, "rank": i + 1, "score": 0.0}
        for i, cid in enumerate(dense_hits)
    ]
    sparse_stage = [
        {"chunk_id": cid, "rank": i + 1, "score": float(score)}
        for i, (cid, score) in enumerate(sparse_hits)
    ]
    fused_stage = [
        {"chunk_id": cid, "rank": i + 1, "score": float(score)}
        for i, (cid, score) in enumerate(fused)
    ]
    reranked_stage = [
        {"chunk_id": c["chunk_id"], "rank": i + 1, "score": float(c["score"])}
        for i, c in enumerate(reranked)
    ]

    trace = {
        "query": query,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "config": config_used,
        "stages": {
            "dense": dense_stage,
            "sparse": sparse_stage,
            "fused": fused_stage,
            "reranked": reranked_stage,
        },
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(trace, f, indent=2)
    except Exception as e:
        logger.warning("Could not write retrieve trace to %s: %s", path, e)


def retrieve_diagnostics(
    query: str,
    n_dense: int,
    n_sparse: int,
    n_fused: int,
    n_reranked: int,
    top_chunk: dict | None,
) -> None:
    """Print a read-only report for the last retrieval call."""

    q_display = query if len(query) <= 80 else query[:77] + "..."

    if top_chunk:
        top_repr = (
            f'{top_chunk.get("chunk_id", "?")} | '
            f'"{top_chunk.get("header", "")}" | '
            f'pages {top_chunk.get("page_start", 0)}-{top_chunk.get("page_end", 0)}'
        )
    else:
        top_repr = "<none>"

    print("\n=== Retrieval Diagnostics ===")
    print(f'  Query           : "{q_display}"')
    print(f"  Dense Candidates: {n_dense}")
    print(f"  Sparse Candidates: {n_sparse}")
    print(f"  Fused (RRF)     : {n_fused}")
    print(f"  Reranked Top-N  : {n_reranked}")
    print(f"  Top Chunk       : {top_repr}")
    print("=============================\n")


def retrieve(
    query: str,
    top_k: int | None = None,
    alpha: float | None = None,
    rerank: bool | None = None,
    doc_id: str | None = None,
) -> list[dict]:
    """Hybrid dense+sparse retrieval with RRF fusion and optional cross-encoder rerank."""

    top_k = top_k if top_k is not None else RETRIEVAL_TOP_K
    rerank_enabled = rerank if rerank is not None else RERANK_ENABLED

    if not query or not query.strip():
        return []

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception as e:
        logger.warning(
            "Collection '%s' not found at '%s': %s. Returning empty results.",
            COLLECTION_NAME, CHROMA_PATH, e,
        )
        return []

    try:
        bm25_handle = open_bm25_index()
    except FileNotFoundError as e:
        logger.warning(
            "BM25 index unavailable (%s). Returning empty results; run build_bm25_index() via /ingest.",
            e,
        )
        return []

    qvec = embed_query(query)

    where_clause = {"document_id": doc_id} if doc_id else None
    dense_results = collection.query(
        query_embeddings=[qvec],
        n_results=DENSE_CANDIDATES,
        where=where_clause,
    )
    dense_id_lists = dense_results.get("ids") or [[]]
    dense_ids: list[str] = dense_id_lists[0] if dense_id_lists else []

    sparse_hits = bm25_search(bm25_handle, query, SPARSE_CANDIDATES)
    sparse_ids = [cid for cid, _ in sparse_hits]

    fused = _rrf_fuse(dense_ids, sparse_ids, k=RRF_K)
    fused = fused[:20]
    fused_score_map = dict(fused)

    candidates = _hydrate(collection, fused, fused_score_map)

    if rerank_enabled and candidates:
        final = cross_encoder_rerank(query, candidates, top_n=top_k)
    else:
        final = candidates[:top_k]

    config_used = {
        "dense_candidates": DENSE_CANDIDATES,
        "sparse_candidates": SPARSE_CANDIDATES,
        "rrf_k": RRF_K,
        "fused_pool": 20,
        "rerank_enabled": rerank_enabled,
        "top_k": top_k,
        "doc_id": doc_id,
    }
    _write_retrieve_trace(query, dense_ids, sparse_hits, fused, final, config_used)

    top_chunk = final[0] if final else None
    retrieve_diagnostics(
        query,
        len(dense_ids),
        len(sparse_hits),
        len(fused),
        len(final),
        top_chunk,
    )

    return final
