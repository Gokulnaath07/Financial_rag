import json
import os
import re
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

    rawspans= extract_rawspans(file_path)
    """
    “The header or body role is assigned while iterating over spans grouped by page number.
    Each iteration processes spans from a single page, 
    and the header/body classification is applied within the structured_spans function before the results are extended into the global structured list.”"""
    # group_pages=grouping_by_pages(rawspans)
    # structured= []

    # for page_no, page_spans in group_pages.items():
    #     """Using extend:
    #             structured = []
    #             page_list = [{"text":"A"},{"text":"B"}]
    #             structured.extend(page_list) # -> [{"text":"A"},{"text":"B"}]

    #             Using append:
    #             structured = []
    #             structured.append(page_list) # -> [[{"text":"A"},{"text":"B"}]]"""
    #     structured.extend(structured_spans(page_spans))
    structured= structured_spans(rawspans)
    structured.sort(key=lambda s: (s['page_no'], s['bbox'][1], s['bbox'][0]))
    # sections=build_section_tree(structured)
    
    # sorted_headers= sort_headers(structured)
    # header_lines=headers_by_proximity(sorted_headers)
    output_text_to_headers="Text_headers.json"
    output_headers="Headers_grouped.json"
    # with open(output_text_to_headers, "w", encoding="utf-8", errors="ignore") as w:
    #     w.write(json.dumps(sections, indent=2, ensure_ascii=False))
    # if os.path.exists(output_text_to_headers):
    #     print(f"Written to {output_text_to_headers}")
    # with open (output_headers, "w", encoding="utf-8", errors="ignore") as w:
    #     w.write(json.dumps(header_lines, indent=2, ensure_ascii=False))
    # if os.path.exists(output_headers):
    #     print(f"Written to {output_headers}")
    return {
        "structured":structured,
        # "headers":header_lines,
        # "sections":sections
    }

def extract_rawspans(file_path: str):

    raw_spans=[]
    
    doc=fitz.open(file_path)


    for index, pages in enumerate(doc):
        pages_dicts=pages.get_text("dict")
        blocks=pages_dicts.get("blocks", [])
        for block in blocks:
            # if block.get("type") !=0:
            #     continue we did this for earlier version now we are taking all types of blocks

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
from collections import defaultdict

def grouping_by_pages(spans: list[dict]) -> dict[int, list[dict]]:

    pages=defaultdict(list)

    for s in spans:
        pages[s['page_no']].append(s)

    return dict(pages)

import re

def looks_like_headers(text: str, size: float, median_size: float) -> bool:
    t = text.strip()
    if not t:
        return False

    # ---------------------------
    # Negative Filters (Early Exit)
    # ---------------------------

    # Likely sentence
    if t.endswith("."):
        return False

    # Too long → probably body
    if len(t.split()) > 12:
        return False

    # Zip code pattern (addresses)
    if re.search(r"\b\d{5}(-\d{4})?\b", t):
        return False

    # Short comma-heavy lines (addresses like "Cupertino, California")
    if "," in t and len(t.split()) <= 4:
        return False

    # Mostly lowercase words → likely sentence fragment
    words = t.split()
    if words:
        lower_ratio = sum(1 for w in words if w.islower()) / len(words)
        if lower_ratio > 0.6:
            return False

    # ---------------------------
    # Strong Structural Patterns
    # ---------------------------

    # ALL CAPS short lines
    if t.isupper() and len(t) < 80:
        return True

    # Common financial headers
    if t.startswith(("ITEM", "Item", "PART ", "Part ")):
        return True

    # Numbered sections (e.g., 1. Introduction, Section 2.3 Risk Factors)
    if re.match(r"^(section\s+)?\d+(\.\d+)*[\).]?\s+[A-Z]", t, re.IGNORECASE):
        return True

    # ---------------------------
    # Font-Based Boost (Secondary Signal)
    # ---------------------------

    # Larger-than-normal font and looks like a title
    if (
        size >= median_size * 1.3
        and t[0].isupper()
        and len(t.split()) <= 10
    ):
        return True

    return False


def section_role(span_size: float, median_size:float)->int:
    relative_size=span_size/median_size
    if relative_size > 1.6:
        return 1
    elif relative_size > 1.35:
        return 2
    elif relative_size > 1.15:
        return 3
    else:
        return 4
    
def structured_spans(raw_spans: list[dict]) -> list[dict]:
    

    cleaned= [s for s in raw_spans if s["text"].strip()]

    if not cleaned:
        return []
    
    sizes=[s['size'] for s in cleaned]

    median_size= statistics.median(sizes)
    
    

    structured_spans=[]
    for s in cleaned:
        is_header_canditate= True if (looks_like_headers(s['text'], s['size'], median_size)) else False
        section_level=section_role(s['size'], median_size) if is_header_canditate else 4
        structured_spans.append(
            {
                "is_header": is_header_canditate,
                "section_level": section_level,
                "text": s['text'],
                "size": s['size'],
                "bbox": s['bbox'],
                "page_no": s['page_no']
            }
        )
    structured_spans.sort(key=lambda s: (s["page_no"], s["bbox"][1], s["bbox"][0]))
    if structured_spans:
        previous_level=None
        for i in range(len(structured_spans)):
            if not structured_spans[i]['is_header']:
                continue
            current_lvl=structured_spans[i]['section_level']
            if previous_level is not None:
                if current_lvl - previous_level >1:
                    structured_spans[i]['section_level']=previous_level +1
            previous_level=structured_spans[i]['section_level']
    return structured_spans

def build_section_tree():
    pass













































# def attach_text_to_header(spans: list[dict]):
    
#     sections=[]
#     current_sections=None

#     for span in spans:
#         if span['role']=="header_candidate":
#                 # If a section is already open, close it before starting a new one
#             if current_sections: 
#                 sections.append(current_sections)
# ## Start a new section at this header also new headers has been initiated
#             current_sections={
#                 "header": span['text'],
#                 "page_no": span["page_no"],
#                 "content": []
#             }
#         else:
#             if current_sections:
#                 current_sections['content'].append(span['text'])
                
#     # Append the final section if one is still open after iteration
#     if current_sections:
#         sections.append(current_sections)
#     return sections

# def sort_headers(structured_spans: list[dict]) -> list[dict]:

#     sorted_headers=[s for s in structured_spans if s['role']=="header_candidate"]
#     sorted_headers.sort(key=lambda s: (s["page_no"], s["bbox"][1], s["bbox"][0]))


#     return sorted_headers

# def headers_by_proximity(spans, threshold=50):

#     header_blocks=[]
#     current_blocks_grp=[]

#     for span in spans:
#         if not current_blocks_grp:
#             current_blocks_grp.append(span)
#             continue

#         prev_y=current_blocks_grp[-1]["bbox"][1]
#         current_y=span["bbox"][1]

#         if abs(current_y-prev_y) <=threshold:
#             current_blocks_grp.append(span)
#         else:
#             header_blocks.append(current_blocks_grp)
#             current_blocks_grp=[span]

# # if there is a headerblock remaining doesnot go with the last batch this is to add that to the list
#     if current_blocks_grp:
#         header_blocks.append(current_blocks_grp)
#     return header_blocks