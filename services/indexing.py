import logging

import chromadb

from config import CHROMA_PATH, COLLECTION_NAME


logger = logging.getLogger(__name__)


def index_chunks(
    embedded_chunks: list[dict],
    store_path: str | None = None,
    collection_name: str | None = None,
) -> dict:
    """Persist embedded chunks into a ChromaDB collection via upsert."""

    store_path = store_path or CHROMA_PATH
    collection_name = collection_name or COLLECTION_NAME

    if not embedded_chunks:
        raise ValueError("index_chunks received an empty embedded_chunks list.")

    for i, c in enumerate(embedded_chunks):
        if "embedding" not in c:
            ref = c.get("chunk_id", f"index={i}")
            raise ValueError(
                f"Chunk {ref} is missing required 'embedding' field. "
                "Indexer cannot compute embeddings; run embed_chunks first."
            )

    client = chromadb.PersistentClient(path=store_path)
    collection = client.get_or_create_collection(name=collection_name)

    ids = [c["chunk_id"] for c in embedded_chunks]
    embeddings = [c["embedding"] for c in embedded_chunks]
    documents = [c["chunk_text"] for c in embedded_chunks]

    metadatas: list[dict] = []
    for c in embedded_chunks:
        # Chroma metadata accepts only primitives — flatten section_path list to string,
        # coerce header None -> "" since Chroma rejects None values.
        metadatas.append({
            "chunk_id": c["chunk_id"],
            "document_id": c["document_id"],
            "section_id": c["section_id"],
            "header": c["header"] if c.get("header") is not None else "",
            "section_path": " > ".join(c["section_path"]),
            "chunk_index": c["chunk_index"],
            "page_start": c["page_start"],
            "page_end": c["page_end"],
            "chunk_type": c["chunk_type"],
            "token_count": c["token_count"],
            "char_count": c["char_count"],
            "embedding_model": c["embedding_model"],
        })

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=documents,
    )

    return {
        "store_path": store_path,
        "collection_name": collection_name,
        "count": collection.count(),
        "embedding_model": embedded_chunks[0]["embedding_model"],
        "embedding_dim": embedded_chunks[0]["embedding_dim"],
    }


def open_index(
    store_path: str | None = None,
    collection_name: str | None = None,
) -> dict:
    """Open an existing collection as a read-only handle for Phase 4."""

    store_path = store_path or CHROMA_PATH
    collection_name = collection_name or COLLECTION_NAME

    client = chromadb.PersistentClient(path=store_path)

    try:
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        raise ValueError(
            f"Collection '{collection_name}' not found at '{store_path}'. "
            "Run index_chunks first."
        ) from e

    embedding_model = ""
    embedding_dim = 0

    sample = collection.peek(limit=1)
    sample_metas = sample.get("metadatas") or []
    sample_embs = sample.get("embeddings") or []

    if sample_metas and sample_embs:
        first_meta = sample_metas[0] or {}
        embedding_model = first_meta.get("embedding_model", "")
        first_emb = sample_embs[0]
        if first_emb is not None:
            embedding_dim = len(first_emb)
    else:
        logger.warning(
            "Collection '%s' at '%s' is empty; embedding_model/dim unknown.",
            collection_name, store_path,
        )

    return {
        "store_path": store_path,
        "collection_name": collection_name,
        "count": collection.count(),
        "embedding_model": embedding_model,
        "embedding_dim": embedding_dim,
    }


def index_diagnostics(handle: dict) -> None:
    """Print a small read-only report from an IndexHandle. No similarity search."""

    store_path = handle["store_path"]
    collection_name = handle["collection_name"]

    client = chromadb.PersistentClient(path=store_path)
    collection = client.get_collection(name=collection_name)

    count = collection.count()
    embedding_model = handle.get("embedding_model", "")
    embedding_dim = handle.get("embedding_dim", 0)

    sample_meta: dict = {}
    peek = collection.peek(limit=1)
    metas = peek.get("metadatas") or []
    if metas:
        sample_meta = metas[0] or {}

    sample_repr = str(sample_meta)
    if len(sample_repr) > 200:
        sample_repr = sample_repr[:197] + "..."

    print("\n=== Index Diagnostics ===")
    print(f"  Collection      : {collection_name}")
    print(f"  Store Path      : {store_path}")
    print(f"  Item Count      : {count}")
    print(f"  Embedding Model : {embedding_model}")
    print(f"  Embedding Dim   : {embedding_dim}")
    print(f"  Sample Metadata : {sample_repr}")
    print("=========================\n")
