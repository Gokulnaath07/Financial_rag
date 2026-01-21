from services.extractor import parse_pdf_blocks, extract_rawspans, grouping_by_pages, structured_spans, sort_headers, headers_by_proximity, attach_text_to_header
import json

# print(json.dumps(parse_pdf_blocks(r"storage\docs\f081b0e2-5fd6-4100-89f9-b7f5f49874b0\occidental_ars.pdf"), indent=2, ensure_ascii=False))

# print(json.dumps(extract_rawspans(r"storage\docs\f081b0e2-5fd6-4100-89f9-b7f5f49874b0\occidental_ars.pdf"), indent=2, ensure_ascii=False))
# print(json.dumps(grouping_by_pages(extract_rawspans(r"storage\docs\f081b0e2-5fd6-4100-89f9-b7f5f49874b0\occidental_ars.pdf")), indent=2, ensure_ascii=False))

parse_pdf_blocks(r"storage\docs\f081b0e2-5fd6-4100-89f9-b7f5f49874b0\occidental_ars.pdf")

