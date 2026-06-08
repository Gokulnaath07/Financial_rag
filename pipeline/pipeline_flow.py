import os
import json

import numpy as np

from services.extractor import parse_pdf_blocks
from services.chunking import chunk_sections
from services.embedding import embed_chunks, validate_embedded_chunks
from services.indexing import index_chunks, index_diagnostics
# Ensure debug directory exists
os.makedirs("debug", exist_ok=True)


parse=parse_pdf_blocks(r"storage\docs\f081b0e2-5fd6-4100-89f9-b7f5f49874b0\Apple 10-k.pdf")
json_struct=json.dumps(parse, indent=2, ensure_ascii=False)
structured_doc="debug/structured.json"
with open(structured_doc, "w", encoding="utf-8", errors="ignore") as w:
    w.write(json_struct)
print(f"Written to {structured_doc}")

chunks=chunk_sections(parse)
chunk_json=json.dumps(chunks, indent=2, ensure_ascii=False)
chunk_doc="debug/chunk_doc.json"
with open(chunk_doc, "w", encoding="utf-8", errors="ignore") as w:
    w.write(chunk_json)
print(f"Written to {chunk_doc}")


embedded = embed_chunks(chunks)
print(f"Embedded {len(embedded)} chunks")

valid = validate_embedded_chunks(embedded)

if valid:
    norms = [float(np.linalg.norm(np.array(e["embedding"]))) for e in valid]
    norm_summary = {
        "min": min(norms),
        "max": max(norms),
        "mean": sum(norms) / len(norms),
        "sample_size": len(norms),
    }
else:
    norm_summary = {"min": 0, "max": 0, "mean": 0, "sample_size": 0}

embed_stats = {
    "input_chunk_count": len(chunks),
    "embedded_chunk_count": len(embedded),
    "valid_chunk_count": len(valid),
    "dropped_count": len(embedded) - len(valid),
    "embedding_model": valid[0]["embedding_model"] if valid else None,
    "embedding_dim": valid[0]["embedding_dim"] if valid else None,
    "norm_summary": norm_summary,
}

embed_stats_path = "debug/embed_stats.json"
with open(embed_stats_path, "w", encoding="utf-8") as w:
    w.write(json.dumps(embed_stats, indent=2, ensure_ascii=False))
print(f"Written to {embed_stats_path}")

handle = index_chunks(valid)
index_diagnostics(handle)

index_report_path = "debug/index_report.json"
with open(index_report_path, "w", encoding="utf-8") as w:
    w.write(json.dumps(handle, indent=2, ensure_ascii=False))
print(f"Written to {index_report_path}")

# result=parse.get("sections", [])

# for s in result:
#     s['section_type']="atomic"  # the dict is mutable so it will add this on the original sections without append.

# all_chunks=returning_allchunks(result)


# json_chunk=json.dumps(all_chunks, indent=2, ensure_ascii=False)
# chunk_doc="debug/chunk_doc.json"
# with open(chunk_doc, "w", encoding="utf-8", errors="ignore") as w:
#     w.write(json_chunk)
# print(f"Written to {chunk_doc}")