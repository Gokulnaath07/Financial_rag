SYSTEM_PROMPT = '''You are a financial document analyst. You answer questions strictly using the provided document excerpts.

CITATION RULES (NON-NEGOTIABLE):
1. Every factual claim in your answer MUST cite a specific chunk by index (e.g., "Apple's net revenue was $383B [Chunk 2]").
2. You may ONLY use information from the provided chunks. Do not use outside knowledge about the company or industry.
3. If the chunks do not contain information sufficient to answer the question, you MUST respond with exactly: "I cannot find this in the documents." Do not guess. Do not synthesize across irrelevant chunks.
4. Output MUST conform to the JSON schema: {"answer": string, "citations": [{"chunk_index": integer, "claim": string}]}.

STYLE:
- Be concise. Quote numbers and dates verbatim from the chunks.
- If chunks conflict, note the conflict and cite both.
'''

CHUNK_TEMPLATE = """[Chunk {idx} | Section: {section_path} | Pages {page_start}-{page_end}]
{chunk_text}
"""

PROMPT_TEMPLATE = """QUESTION:
{question}

DOCUMENT EXCERPTS:
{chunks_block}

Answer the question using ONLY the excerpts above. Follow the citation rules. Respond in the required JSON format."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk_index": {"type": "integer"},
                    "claim": {"type": "string"},
                },
                "required": ["chunk_index", "claim"],
            },
        },
    },
    "required": ["answer", "citations"],
}


def build_user_prompt(question: str, retrieved_chunks: list[dict]) -> str:
    """Assemble the LLM user prompt from question + numbered chunk excerpts."""

    non_empty = [c for c in retrieved_chunks if c.get("chunk_text", "").strip()]

    chunk_blocks = []
    for idx, chunk in enumerate(non_empty, start=1):
        chunk_blocks.append(
            CHUNK_TEMPLATE.format(
                idx=idx,
                section_path=chunk["section_path"],
                page_start=chunk["page_start"],
                page_end=chunk["page_end"],
                chunk_text=chunk["chunk_text"],
            )
        )

    chunks_block = "\n".join(chunk_blocks)

    return PROMPT_TEMPLATE.format(question=question, chunks_block=chunks_block)
