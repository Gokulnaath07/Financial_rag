from services.extractor import parse_pdf_blocks, extract_rawspans, grouping_by_pages, structured_spans, sort_headers, headers_by_proximity, attach_text_to_header
import json

# print(json.dumps(parse_pdf_blocks(r"storage\docs\f081b0e2-5fd6-4100-89f9-b7f5f49874b0\occidental_ars.pdf"), indent=2, ensure_ascii=False))

# print(json.dumps(extract_rawspans(r"storage\docs\f081b0e2-5fd6-4100-89f9-b7f5f49874b0\occidental_ars.pdf"), indent=2, ensure_ascii=False))
# print(json.dumps(grouping_by_pages(extract_rawspans(r"storage\docs\f081b0e2-5fd6-4100-89f9-b7f5f49874b0\occidental_ars.pdf")), indent=2, ensure_ascii=False))

# parse_pdf_blocks(r"storage\docs\f081b0e2-5fd6-4100-89f9-b7f5f49874b0\occidental_ars.pdf")


# from services.chunking import returning_allchunks


# parse=parse_pdf_blocks(r"storage\docs\f081b0e2-5fd6-4100-89f9-b7f5f49874b0\occidental_ars.pdf")
# result=parse.get("sections", [])

# for s in result:
#     s['section_type']="atomic"  # the dict is mutable so it will add this on the original sections without append.

# all_chunks=returning_allchunks(result)


# json_chunk=json.dumps(all_chunks, indent=2, ensure_ascii=False)
# chunk_doc="chunk_doc.json"
# with open(chunk_doc, "w", encoding="utf-8", errors="ignore") as w:
#     w.write(json_chunk)
# print(f"Written to {chunk_doc}")