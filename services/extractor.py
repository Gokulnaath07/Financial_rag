import statistics
from pypdf import PdfReader
import fitz #pymupdf

def extract_txt(file_path: str) ->str:

    if file_path.lower().endswith(".pdf"):
        text=""
        pageReader=PdfReader(file_path)

        for page in pageReader.pages:
            if page.extract_text():
                text+=page.extract_text() + "\n"
        return text
    if file_path.lower().endswith(".txt"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as r:
            text=r.read()
        return text
    return ""

def parse_pdf_blocks(file_path: str):
    """PDF primitives
            ↓
    RAW spans        (direct from PyMuPDF)
            ↓
    STRUCTURED spans (normalized, typed, consistent)
            ↓
    GROUPED units    (lines, paragraphs, sections)"""

    extract_rawspans= extract_rawspans(file_path)
    structured= structured_spans(extract_rawspans)
    sorted_headers= sort_headers(structured)
    header_lines=headers_by_proximity(sorted_headers)
    return {
        "raw_spans": extract_rawspans,
        "structured_spans": structured,
        "sorted_headers": sorted_headers,
        "header_lines": header_lines
    }

def extract_rawspans(file_path: str):

    raw_spans=[]
    
    doc=fitz.open(file_path)


    for index, pages in enumerate(doc):
        pages_dicts=pages.get_text("dict")
        blocks=pages_dicts.get("blocks", [])
        for block in blocks:
            if block.get("type") !=0:
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    
                    if not span['text']:
                        continue
                    raw_spans.append(
                        {
                            "page_no": index + 1,
                            "text": span['text'],
                            "size": span['size'],
                            "bbox": span['bbox']
                        }
                    )
    return raw_spans


def structured_spans(raw_spans: list[dict]) -> list[dict]:
    

    cleaned= [s for s in raw_spans if s["text"].strip()]

    if not cleaned:
        return []
    
    sizes=[s['size'] for s in cleaned]

    median_size= statistics.median(sizes)

    structured_spans=[]
    for s in cleaned:
        is_header_canditate= "header_candidate" if (s['size'] >= median_size * 1.3 and 
                                                    any(c.isalpha() for c in s['text'])) else "body"
        
        structured_spans.append(
            {
                "role": is_header_canditate,
                "text": s['text'],
                "size": s['size'],
                "bbox": s['bbox'],
                "page_no": s['page_no']
            }
        )
    return structured_spans

def sort_headers(structured_spans: list[dict]) -> list[dict]:

    sorted_headers=[s for s in structured_spans if s['role']=="header_candidate"]
    sorted_headers.sort(key=lambda s: (s["page_no"], s["bbox"][1], s["bbox"][0]))


    return sorted_headers

def headers_by_proximity(spans, threshold=50):

    pass