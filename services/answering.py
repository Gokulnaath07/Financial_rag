import json
import logging
import os
import re
from datetime import datetime

from config import NOT_FOUND_THRESHOLD, TOP_K_FOR_PROMPT
from services.llm import (
    generate,
    LLMConfigError,
    LLMRateLimitError,
    LLMServerError,
)
from services.prompts import SYSTEM_PROMPT, OUTPUT_SCHEMA, build_user_prompt


logger = logging.getLogger(__name__)

_TRACE_PATH = os.path.join("debug", "answer_trace.json")
_NOT_FOUND_PATTERN = re.compile(
    r"^\s*i\s+cannot\s+find\s+this\s+in\s+the\s+documents\.?\s*$",
    re.IGNORECASE,
)


def _check_not_found(retrieved_chunks: list[dict]) -> bool:
    if not retrieved_chunks:
        return True
    if retrieved_chunks[0]["score"] < NOT_FOUND_THRESHOLD:
        return True
    return False


def _strip_json_fence(text: str) -> str:
    """Strip optional ```json ... ``` code fence Gemini sometimes emits."""
    text = re.sub(r"^\s*```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _verify_citations(
    parsed_citations: list[dict],
    retrieved_chunks: list[dict],
) -> tuple[list[dict], int]:
    """Validate chunk_index ranges, map to citation dicts, count invalid."""

    valid: list[dict] = []
    dropped = 0
    n = len(retrieved_chunks)

    for citation in parsed_citations:
        idx = citation.get("chunk_index")
        if not isinstance(idx, int) or idx < 1 or idx > n:
            dropped += 1
            continue
        chunk = retrieved_chunks[idx - 1]
        valid.append({
            "chunk_id": chunk["chunk_id"],
            "section_path": chunk["section_path"],
            "page_start": chunk["page_start"],
            "page_end": chunk["page_end"],
        })

    return valid, dropped


def _write_answer_trace(
    question: str,
    retrieved_chunks: list[dict],
    prompt: str,
    llm_response: str,
    parsed: dict,
    valid_citations: list[dict],
    confidence: str,
) -> None:
    """Persist a single-call debug trace; overwrites per call."""

    os.makedirs(os.path.dirname(_TRACE_PATH), exist_ok=True)

    retrieved_summary = [
        {
            "chunk_id": c.get("chunk_id"),
            "score": c.get("score"),
            "header": c.get("header"),
        }
        for c in retrieved_chunks
    ]

    trace = {
        "question": question,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "retrieved_chunk_summary": retrieved_summary,
        "prompt": prompt,
        "llm_response": llm_response,
        "parsed_answer": parsed.get("answer", "") if isinstance(parsed, dict) else "",
        "parsed_citations": parsed.get("citations", []) if isinstance(parsed, dict) else [],
        "valid_citations": valid_citations,
        "confidence": confidence,
    }

    serialized = json.dumps(trace, indent=2, ensure_ascii=False)

    # Defense against API key leakage into trace artifacts.
    assert "GEMINI" not in serialized, "Trace appears to contain GEMINI marker."
    assert "AIza" not in serialized, "Trace appears to contain API key prefix."

    with open(_TRACE_PATH, "w", encoding="utf-8") as f:
        f.write(serialized)


def answer_question(question: str, retrieved_chunks: list[dict]) -> dict:
    """Generate a cited answer from retrieved chunks. Never raises on empty input."""

    if _check_not_found(retrieved_chunks):
        result = {
            "answer": "I cannot find this in the documents.",
            "citations": [],
            "sources_used": [],
            "confidence": "not_found",
        }
        _write_answer_trace(question, retrieved_chunks, "", "", {}, [], "not_found")
        _print_answer_diagnostics(question, result)
        return result

    top_chunks = retrieved_chunks[:TOP_K_FOR_PROMPT]
    user_prompt = build_user_prompt(question, top_chunks)

    llm_response = generate(
        user_prompt,
        system=SYSTEM_PROMPT,
        response_schema=OUTPUT_SCHEMA,
    )

    stripped = _strip_json_fence(llm_response)

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as e:
        logger.warning("LLM response was not valid JSON: %s", e)
        result = {
            "answer": "I cannot find this in the documents.",
            "citations": [],
            "sources_used": [],
            "confidence": "low",
        }
        _write_answer_trace(
            question, top_chunks, user_prompt, llm_response, {}, [], "low",
        )
        _print_answer_diagnostics(question, result)
        return result

    raw_citations = parsed.get("citations", []) or []
    valid_citations, dropped = _verify_citations(raw_citations, top_chunks)
    sources_used = [c["chunk_id"] for c in valid_citations]
    answer_text = parsed.get("answer", "") or ""

    if _NOT_FOUND_PATTERN.match(answer_text):
        confidence = "not_found"
    elif not valid_citations:
        confidence = "low"
    else:
        confidence = "high"

    if dropped:
        logger.info("Dropped %d invalid citation(s) from LLM output.", dropped)

    result = {
        "answer": answer_text,
        "citations": valid_citations,
        "sources_used": sources_used,
        "confidence": confidence,
    }

    _write_answer_trace(
        question,
        top_chunks,
        user_prompt,
        llm_response,
        parsed,
        valid_citations,
        confidence,
    )
    _print_answer_diagnostics(question, result)
    return result


def _print_answer_diagnostics(question: str, result: dict) -> None:
    """Print answer generation summary matching Phase 3 banner style."""

    q_preview = question if len(question) <= 80 else question[:77] + "..."
    answer = result.get("answer", "")
    a_preview = answer if len(answer) <= 120 else answer[:117] + "..."

    sources = result.get("sources_used", [])
    short_ids = ", ".join(s[:8] for s in sources[:5])
    if len(sources) > 5:
        short_ids += ", ..."

    print("\n=== Answer Generation Diagnostics ===")
    print(f'  Question        : "{q_preview}"')
    print(f"  Confidence      : {result.get('confidence', '?')}")
    print(f"  Citations       : {len(result.get('citations', []))}")
    print(f"  Sources Used    : {len(sources)} chunks ({short_ids})")
    print(f'  Answer Preview  : "{a_preview}"')
    print("=====================================\n")
