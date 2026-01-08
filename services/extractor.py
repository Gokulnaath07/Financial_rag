from pypdf import PdfReader

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