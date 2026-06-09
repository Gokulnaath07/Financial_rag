import json
import logging
import os
import pickle
import re
from datetime import datetime

import chromadb
from rank_bm25 import BM25Okapi

from config import BM25_PATH, CHROMA_PATH, COLLECTION_NAME


logger = logging.getLogger(__name__)


_PUNCT_STRIP = ".,;:!?()[]{}<>\"'/\\"


def _tokenize(text: str) -> list[str]:
    """Lowercase whitespace tokenizer; preserves tickers (AAPL), filings (10-K), percentages (12.3%)."""
    if not text:
        return []
    tokens = text.lower().split()
    out: list[str] = []
    for tok in tokens:
        stripped = tok.strip(_PUNCT_STRIP)
        if stripped:
            out.append(stripped)
    return out


def build_bm25_index(
    store_path: str | None = None,
    collection_name: str | None = None,
    bm25_path: str | None = None,
) -> dict:
    """Build BM25 sparse index from existing Chroma collection and persist to disk."""

    store_path = store_path or CHROMA_PATH
    collection_name = collection_name or COLLECTION_NAME
    bm25_path = bm25_path or BM25_PATH

    client = chromadb.PersistentClient(path=store_path)

    try:
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        raise ValueError(
            f"Collection '{collection_name}' not found at '{store_path}'. "
            "Run index_chunks first."
        ) from e

    fetched = collection.get(include=["documents", "metadatas"])
    ids = fetched.get("ids") or []
    documents = fetched.get("documents") or []

    if not ids:
        raise ValueError(
            f"Collection '{collection_name}' is empty; cannot build BM25 index."
        )

    tokenized_docs = [_tokenize(doc or "") for doc in documents]
    bm25 = BM25Okapi(tokenized_docs)

    target_dir = os.path.join(bm25_path, collection_name)
    os.makedirs(target_dir, exist_ok=True)

    pkl_path = os.path.join(target_dir, "bm25.pkl")
    ids_path = os.path.join(target_dir, "chunk_ids.json")
    manifest_path = os.path.join(target_dir, "manifest.json")

    with open(pkl_path, "wb") as f:
        pickle.dump(bm25, f)

    with open(ids_path, "w", encoding="utf-8") as f:
        json.dump(ids, f)

    source_chroma_count = collection.count()
    handle = {
        "bm25_path": target_dir,
        "collection_name": collection_name,
        "doc_count": len(ids),
        "tokenizer": "lowercase_whitespace_v1",
        "built_at": datetime.utcnow().isoformat() + "Z",
        "source_chroma_count": source_chroma_count,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(handle, f, indent=2)

    print("\n=== BM25 Index Diagnostics ===")
    print(f"  Collection      : {collection_name}")
    print(f"  BM25 Path       : {target_dir}")
    print(f"  Doc Count       : {handle['doc_count']}")
    print(f"  Tokenizer       : {handle['tokenizer']}")
    print(f"  Built At        : {handle['built_at']}")
    print(f"  Source Chroma   : {source_chroma_count} (drift: 0)")
    print("==============================\n")

    return handle


def open_bm25_index(
    bm25_path: str | None = None,
    collection_name: str | None = None,
) -> dict:
    """Load a persisted BM25 index from disk into a runtime handle."""

    bm25_path = bm25_path or BM25_PATH
    collection_name = collection_name or COLLECTION_NAME

    target_dir = os.path.join(bm25_path, collection_name)
    pkl_path = os.path.join(target_dir, "bm25.pkl")
    ids_path = os.path.join(target_dir, "chunk_ids.json")
    manifest_path = os.path.join(target_dir, "manifest.json")

    if not os.path.exists(pkl_path):
        raise FileNotFoundError(
            f"BM25 index not found at {target_dir}. Run build_bm25_index() first."
        )

    with open(pkl_path, "rb") as f:
        bm25 = pickle.load(f)

    with open(ids_path, "r", encoding="utf-8") as f:
        chunk_ids = json.load(f)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_collection(name=collection_name)
        live_count = collection.count()
        if live_count != manifest.get("doc_count"):
            logger.warning(
                "BM25 drift detected for '%s': manifest doc_count=%d vs live Chroma count=%d. "
                "Consider rebuilding BM25 index.",
                collection_name, manifest.get("doc_count", -1), live_count,
            )
    except Exception as e:
        logger.warning(
            "Could not verify BM25 drift against Chroma collection '%s': %s",
            collection_name, e,
        )

    return {
        "bm25": bm25,
        "chunk_ids": chunk_ids,
        "manifest": manifest,
    }


def bm25_search(handle: dict, query: str, top_k: int = 50) -> list[tuple[str, float]]:
    """Score query against BM25 index, return top_k (chunk_id, score) pairs sorted desc."""

    if not handle or not handle.get("chunk_ids"):
        return []

    tokenized_query = _tokenize(query)
    if not tokenized_query:
        return []

    bm25 = handle["bm25"]
    chunk_ids = handle["chunk_ids"]

    scores = bm25.get_scores(tokenized_query)

    ranked = sorted(
        zip(chunk_ids, scores),
        key=lambda x: x[1],
        reverse=True,
    )

    results: list[tuple[str, float]] = []
    for cid, score in ranked[:top_k]:
        fscore = float(score)
        if fscore == 0.0:
            continue
        results.append((cid, fscore))

    return results


def bm25_diagnostics(handle: dict) -> None:
    """Print a read-only report from a BM25 runtime or build handle."""

    if "manifest" in handle:
        manifest = handle["manifest"]
    else:
        manifest = handle

    collection_name = manifest.get("collection_name", "")
    bm25_path_val = manifest.get("bm25_path", "")
    doc_count = manifest.get("doc_count", 0)
    tokenizer = manifest.get("tokenizer", "")
    built_at = manifest.get("built_at", "")
    source_chroma = manifest.get("source_chroma_count", 0)

    live_count = source_chroma
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_collection(name=collection_name)
        live_count = collection.count()
    except Exception:
        pass

    drift = live_count - doc_count

    print("\n=== BM25 Index Diagnostics ===")
    print(f"  Collection      : {collection_name}")
    print(f"  BM25 Path       : {bm25_path_val}")
    print(f"  Doc Count       : {doc_count}")
    print(f"  Tokenizer       : {tokenizer}")
    print(f"  Built At        : {built_at}")
    print(f"  Source Chroma   : {live_count} (drift: {drift})")
    print("==============================\n")
