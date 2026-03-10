import os
import json


from services.extractor import parse_pdf_blocks
from services.chunking import returning_allchunks

# Ensure debug directory exists
os.makedirs("debug", exist_ok=True)


parse=parse_pdf_blocks(r"storage\docs\f081b0e2-5fd6-4100-89f9-b7f5f49874b0\Apple 10-k.pdf")
json_struct=json.dumps(parse, indent=2, ensure_ascii=False)
structured_doc="debug/structured.json"
with open(structured_doc, "w", encoding="utf-8", errors="ignore") as w:
    w.write(json_struct)
print(f"Written to {structured_doc}")
# result=parse.get("sections", [])

# for s in result:
#     s['section_type']="atomic"  # the dict is mutable so it will add this on the original sections without append.

# all_chunks=returning_allchunks(result)


# json_chunk=json.dumps(all_chunks, indent=2, ensure_ascii=False)
# chunk_doc="debug/chunk_doc.json"
# with open(chunk_doc, "w", encoding="utf-8", errors="ignore") as w:
#     w.write(json_chunk)
# print(f"Written to {chunk_doc}")