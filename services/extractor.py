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

    doc=fitz.open(file_path)

    for index, page in enumerate(doc):
        # if index>=2: check only first 2 pages
        #     break
        page_dict=page.get_text("dict")
        blocks= page_dict.get("blocks",[])

        spans=[]
        #print(f"Page {index +1} has {len(blocks)} blocks.")
        for block in blocks:
            if block.get("type")!=0:
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span['text'].strip()
                    if not text:
                        continue
                    # print(
                    #     f"Page no: {index + 1} | " 
                    #     f"Text: {text[:50]!r} | "
                    #     f"Font: {span['font']} |"
                    #     f"Size: {span['size']}"
                    # )
                    spans.append(
                        {
                            "element_type": "text",
                            "text": text,
                            "font": span['font'],
                            "size": span['size'],
                            "bbox": span['bbox']
                        }
                    )
        structured_spans = []
        sizes=[s['size'] for s in spans]
        if not sizes:
            continue
        median_size= statistics.median(sizes)

        for s in spans:
            header_candidate=(s['size'] >= median_size * 1.3 and 
                              any(c.isalpha() for c in s['text'])
                              )
            
            structured_spans.append(
                {
                    "role": "header_candidate" if header_candidate else "body",
                    "text": s['text'],
                    "font": s['font'],
                    "size": s['size'],
                    "bbox": s['bbox']
                }
            )
            if header_candidate:

                print(
                    f"Page no: {index+1} | "
                    f"Role: {'header_candidate'} | "
                    f"Text: {s['text']!r}" 
                    
                )

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