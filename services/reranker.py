import logging
import threading

from sentence_transformers import CrossEncoder

from config import RERANKER_MODEL


logger = logging.getLogger(__name__)

_cross_encoder: CrossEncoder | None = None
_cross_encoder_lock = threading.Lock()
_cross_encoder_name_loaded: str | None = None


def _get_cross_encoder(model_name: str) -> CrossEncoder:
    """Load cross-encoder once per process, cache by name."""
    global _cross_encoder, _cross_encoder_name_loaded
    with _cross_encoder_lock:
        if _cross_encoder is None or _cross_encoder_name_loaded != model_name:
            _cross_encoder = CrossEncoder(model_name)
            _cross_encoder_name_loaded = model_name
        return _cross_encoder


def rerank(
    query: str,
    candidates: list[dict],
    top_n: int = 5,
    model_name: str | None = None,
) -> list[dict]:
    """Rescore candidate chunks with a cross-encoder; preserves all fields except score."""

    if not candidates:
        return []

    model_name = model_name or RERANKER_MODEL
    model = _get_cross_encoder(model_name)

    pairs = [(query, c["chunk_text"]) for c in candidates]
    logits = model.predict(pairs)

    rescored: list[dict] = []
    for candidate, logit in zip(candidates, logits):
        new_candidate = dict(candidate)
        new_candidate["score"] = float(logit)
        rescored.append(new_candidate)

    rescored.sort(key=lambda c: c["score"], reverse=True)
    return rescored[:top_n]
