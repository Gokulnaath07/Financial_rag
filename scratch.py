from services.extractor import parse_pdf_blocks
import json

print(json.dumps(parse_pdf_blocks(r"storage\docs\f081b0e2-5fd6-4100-89f9-b7f5f49874b0\occidental_ars.pdf"), indent=2, ensure_ascii=False))