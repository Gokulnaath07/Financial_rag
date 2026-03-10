import os
import re
import statistics
import uuid
from collections import defaultdict
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

def parse_pdf_blocks(file_path: str) -> dict:
    """Full extractor pipeline:
    raw spans -> structured spans -> sort -> header merge
    -> section tree -> page_end -> stats -> validation -> Document"""

    # 1. Extract raw spans
    rawspans, total_pages = extract_rawspans(file_path)

    # 2. Build structured spans (includes internal sort + level clamping)
    structured = structured_spans(rawspans)

    # 3. Explicit sort by (page_no, y, x) — safety net
    structured.sort(key=lambda s: (s["page_no"], s["bbox"][1], s["bbox"][0]))

    # 4. Merge multi-line headers
    merged = merge_multiline_headers(structured)

    # 5. Build section tree
    sections = build_section_tree(merged)

    # 6. Compute page_end
    sections = compute_page_end(sections, total_pages)

    # 7. Compute section stats
    sections = compute_section_stats(sections)

    # 8. Validate sections
    sections = validate_sections(sections)

    # Return Document object
    return {
        "document_id": str(uuid.uuid4()),
        "file_name": os.path.basename(file_path),
        "total_pages": total_pages,
        "sections": sections,
    }

def extract_rawspans(file_path: str):

    raw_spans=[]

    doc=fitz.open(file_path)
    total_pages = len(doc)


    for index, pages in enumerate(doc):
        pages_dicts=pages.get_text("dict")
        blocks=pages_dicts.get("blocks", [])
        for block in blocks:

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
    return raw_spans, total_pages

def grouping_by_pages(spans: list[dict]) -> dict[int, list[dict]]:

    pages=defaultdict(list)

    for s in spans:
        pages[s['page_no']].append(s)

    return dict(pages)


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


def section_role(span_size: float, median_size: float) -> int:
    ratio = span_size / median_size
    if ratio >= 1.6:
        return 1
    elif ratio >= 1.35:
        return 2
    elif ratio >= 1.15:
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
        is_header = looks_like_headers(s['text'], s['size'], median_size)
        level = section_role(s['size'], median_size) if is_header else None
        structured_spans.append(
            {
                "is_header": is_header,
                "section_level": level,
                "text": s['text'],
                "size": s['size'],
                "bbox": s['bbox'],
                "page_no": s['page_no']
            }
        )
    structured_spans.sort(key=lambda s: (s["page_no"], s["bbox"][1], s["bbox"][0]))
    if structured_spans:
        previous_level = None
        for i in range(len(structured_spans)):
            if not structured_spans[i]['is_header']:
                continue
            current_lvl = structured_spans[i]['section_level']
            if previous_level is not None and abs(current_lvl - previous_level) > 2:
                structured_spans[i]['section_level'] = previous_level + 1
            previous_level = structured_spans[i]['section_level']
    return structured_spans

def merge_multiline_headers(sorted_spans: list[dict]) -> list[dict]:
    """Merge consecutive header spans that are on the same page and within
    y-distance <= 50.  Stop merging immediately when a body span appears."""

    merged = []
    header_group = []

    def flush_header_group():
        if not header_group:
            return
        if len(header_group) == 1:
            merged.append(header_group[0])
        else:
            combined_text = " ".join(s["text"] for s in header_group)
            merged.append({
                "is_header": True,
                "section_level": min(s["section_level"] for s in header_group),
                "text": combined_text,
                "size": max(s["size"] for s in header_group),
                "bbox": (
                    min(s["bbox"][0] for s in header_group),
                    min(s["bbox"][1] for s in header_group),
                    max(s["bbox"][2] for s in header_group),
                    max(s["bbox"][3] for s in header_group),
                ),
                "page_no": header_group[0]["page_no"],
            })

    for span in sorted_spans:
        if span["is_header"]:
            if header_group:
                last = header_group[-1]
                same_page = span["page_no"] == last["page_no"]
                y_distance = abs(span["bbox"][1] - last["bbox"][3])
                if same_page and y_distance <= 50:
                    header_group.append(span)
                else:
                    flush_header_group()
                    header_group = [span]
            else:
                header_group = [span]
        else:
            flush_header_group()
            header_group = []
            merged.append(span)

    flush_header_group()
    return merged


def build_section_tree(merged_spans: list[dict]) -> list[dict]:
    """Build a hierarchical section tree from merged spans using stack-based logic.

    Input: structurally merged spans (output of merge_multiline_headers).
    Output: ordered list of Section dicts with parent references and content_blocks.
    """

    sections = []
    section_stack = []

    for span in merged_spans:
        if span["is_header"]:

            if span["section_level"] is None:
                continue

            current_level = span["section_level"]

            while section_stack and section_stack[-1]["section_level"] >= current_level:
                section_stack.pop()

            if section_stack:
                parent_id = section_stack[-1]["section_id"]
                parent_path = section_stack[-1]["section_path"]
            else:
                parent_id = None
                parent_path = []

            section_path = parent_path + [span["text"]]

            section = {
                "section_id": str(uuid.uuid4()),
                "parent_section_id": parent_id,
                "header": span["text"],
                "section_level": len(section_path),
                "section_path": section_path,
                "page_start": span["page_no"],
                "page_end": None,
                "content_blocks": [],
                "char_count": 0,
                "token_estimate": 0,
            }
       

            sections.append(section)
            section_stack.append(section)
        else:
            # Body text — attach to current section on top of stack
            if not section_stack:
                # Orphan body text before first header — create synthetic root
                root = {
                    "section_id": "root",
                    "parent_section_id": None,
                    "header": "__ROOT__",
                    "section_level": 0,
                    "section_path": [],
                    "page_start": 1,
                    "page_end": None,
                    "content_blocks": [],
                    "char_count": 0,
                    "token_estimate": 0,
                }
                sections.append(root)
                section_stack.append(root)

            section_stack[-1]["content_blocks"].append(span["text"])

    return sections


def compute_page_end(sections: list[dict], total_pages: int) -> list[dict]:
    """Set page_end for each section.

    page_end = next section's page_start - 1.
    Last section's page_end = document total pages.
    """

    for i in range(len(sections) - 1):
        sections[i]["page_end"] = sections[i + 1]["page_start"] - 1
        # Ensure page_end is never less than page_start (same-page sections)
        if sections[i]["page_end"] < sections[i]["page_start"]:
            sections[i]["page_end"] = sections[i]["page_start"]

    if sections:
        sections[-1]["page_end"] = total_pages

    return sections


def compute_section_stats(sections: list[dict]) -> list[dict]:
    """Populate char_count and token_estimate for each section."""

    for section in sections:
        full_text = "\n".join(section["content_blocks"])
        section["char_count"] = len(full_text)
        section["token_estimate"] = len(full_text.split())

    return sections


def validate_sections(sections: list[dict]) -> list[dict]:
    """Validate, clean, and report on the section list.

    Read-only for stats — never recomputes token_estimate or char_count.
    Returns a cleaned sections list ready for chunking.
    """

    diagnostics = {
        "total_in": len(sections),
        "removed_empty": 0,
        "merged_duplicates": 0,
        "warnings": [],
        "errors": [],
    }

    # --- 1. Merge duplicate consecutive headers ---
    merged = []
    for section in sections:
        if (
            merged
            and merged[-1]["header"] == section["header"]
            and merged[-1]["section_level"] == section["section_level"]
        ):
            merged[-1]["content_blocks"].extend(section["content_blocks"])
            if section["page_end"] is not None:
                if merged[-1]["page_end"] is None or section["page_end"] > merged[-1]["page_end"]:
                    merged[-1]["page_end"] = section["page_end"]
            diagnostics["merged_duplicates"] += 1
        else:
            merged.append(section)
    sections = merged

    # --- 2. Remove empty sections (no content_blocks AND no children) ---
    parent_ids = {s["parent_section_id"] for s in sections if s["parent_section_id"]}
    cleaned = []
    for s in sections:
        has_content = len(s["content_blocks"]) > 0
        has_children = s["section_id"] in parent_ids
        if not has_content and not has_children:
            diagnostics["removed_empty"] += 1
            diagnostics["warnings"].append(
                f"Removed empty section: '{s['header']}' (level {s['section_level']}, page {s['page_start']})"
            )
        else:
            cleaned.append(s)
    sections = cleaned

    # --- 3. Per-section checks ---
    seen_paths = set()
    previous_level = None

    for s in sections:
        # page_start > page_end
        if s["page_end"] is not None and s["page_start"] > s["page_end"]:
            diagnostics["errors"].append(
                f"page_start ({s['page_start']}) > page_end ({s['page_end']}) in '{s['header']}'"
            )

        # Tiny section
        if s["token_estimate"] < 20:
            diagnostics["warnings"].append(
                f"Tiny section ({s['token_estimate']} tokens): '{s['header']}'"
            )

        # Oversized section
        if s["token_estimate"] > 8000:
            diagnostics["warnings"].append(
                f"Oversized section ({s['token_estimate']} tokens): '{s['header']}'"
            )

        # Section level jump > 2
        if previous_level is not None and abs(s["section_level"] - previous_level) > 2:
            diagnostics["warnings"].append(
                f"Level jump > 2: {previous_level} -> {s['section_level']} at '{s['header']}'"
            )
        previous_level = s["section_level"]

        # len(section_path) must equal section_level
        if len(s["section_path"]) != s["section_level"]:
            diagnostics["errors"].append(
                f"Path depth ({len(s['section_path'])}) != section_level ({s['section_level']}) in '{s['header']}'"
            )

        # Unique section_path
        path_key = tuple(s["section_path"])
        if path_key in seen_paths:
            diagnostics["warnings"].append(
                f"Duplicate section_path: {s['section_path']}"
            )
        seen_paths.add(path_key)

    # --- 4. Ensure ordering by page_start then hierarchy ---
    sections.sort(key=lambda s: (s["page_start"], s["section_level"]))

    # --- 5. Diagnostic report ---
    _print_validation_report(diagnostics, len(sections))

    return sections


def _print_validation_report(diagnostics: dict, final_count: int):
    """Print a formatted extraction validation report."""

    print("\n" + "=" * 60)
    print("  EXTRACTOR VALIDATION REPORT")
    print("=" * 60)
    print(f"  Sections in:       {diagnostics['total_in']}")
    print(f"  Sections out:      {final_count}")
    print(f"  Removed (empty):   {diagnostics['removed_empty']}")
    print(f"  Merged (dupes):    {diagnostics['merged_duplicates']}")

    if diagnostics["errors"]:
        print(f"\n  ERRORS ({len(diagnostics['errors'])}):")
        for e in diagnostics["errors"]:
            print(f"    [ERROR] {e}")

    if diagnostics["warnings"]:
        print(f"\n  WARNINGS ({len(diagnostics['warnings'])}):")
        for w in diagnostics["warnings"]:
            print(f"    [WARN]  {w}")

    if not diagnostics["errors"] and not diagnostics["warnings"]:
        print("\n  All checks passed.")

    print("=" * 60 + "\n")
