"""Phase 4 end-to-end smoke test.

Runs a fixed set of questions through retrieve() + answer_question() against
the existing financial_docs collection. Writes results to debug/phase_4_smoke.json.

Run with: python smoke_phase_4.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.retrieval import retrieve
from services.answering import answer_question


QUESTIONS = [
    "What was Apple's total net revenue?",
    "What are Apple's primary product categories?",
    "Who are Apple's auditors?",
    "What risks does Apple face from operations in China?",
    "How much did Apple spend on research and development?",
    "What is the moisture content of Apple's products?",
]


def run_one(question: str) -> dict:
    t0 = time.perf_counter()
    retrieved = retrieve(question, top_k=5)
    t_retrieve = time.perf_counter() - t0

    t0 = time.perf_counter()
    result = answer_question(question, retrieved)
    t_answer = time.perf_counter() - t0

    return {
        "question": question,
        "retrieved_count": len(retrieved),
        "top_score": retrieved[0]["score"] if retrieved else None,
        "answer": result["answer"],
        "confidence": result["confidence"],
        "citations": result["citations"],
        "sources_used": result["sources_used"],
        "retrieve_seconds": round(t_retrieve, 2),
        "answer_seconds": round(t_answer, 2),
    }


def main():
    results = []
    for q in QUESTIONS:
        print(f"\n{'=' * 70}")
        print(f"Q: {q}")
        print("=" * 70)
        try:
            r = run_one(q)
            results.append(r)
            print(f"\n[Confidence: {r['confidence']}]")
            print(f"Answer: {r['answer']}")
            print(f"Citations: {len(r['citations'])} | Retrieve {r['retrieve_seconds']}s | Answer {r['answer_seconds']}s")
        except Exception as e:
            print(f"FAILED: {type(e).__name__}: {e}")
            results.append({"question": q, "error": f"{type(e).__name__}: {e}"})

    os.makedirs("debug", exist_ok=True)
    out_path = os.path.join("debug", "phase_4_smoke.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n\nResults written to {out_path}")


if __name__ == "__main__":
    main()
