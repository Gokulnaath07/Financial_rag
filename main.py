from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import uvicorn 
import uuid
import os
from pydantic import BaseModel #pydantic for validation(whether the data has correct type in some cases it will convert the sent data eg 123 int to "123"string if string is expected)
from services.extractor import extract_txt


current_app=FastAPI()

@current_app.get("/health")
def health_check():
    return {"status": "Firstu fast api endpoint"}

@current_app.post("/ingest")
async def ingestDocuments(
    file: UploadFile =File(...),
    doc_type: str | None=Form(None)
):
    #need a document ID to track documents
    doc_id=str(uuid.uuid4())

    #make sure it gets saved in right folder
    half_path=os.path.join("storage", "docs", doc_id)
    os.makedirs(half_path, exist_ok=True)
    #Give perfect name to the file obtained 
    save_filename=os.path.basename(file.filename)
    # save_path=f"storage/docs/{doc_id}_{file.filename}"
    save_path=os.path.join(half_path, save_filename)

    #Now read and write the data to the file
    contents=await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    return{"doc_id": doc_id,
           "filename": file.filename,
           "doc_type": doc_type,
           "status": "Document ingested successfully"
    }

class AskRequest(BaseModel):
    doc_id: str
    question: str

@current_app.post("/ask")
async def askQuestion(req: AskRequest):
    """matches=[]
    if os.path.exists("storage/docs"):
        for name in os.listdir("storage/docs"):
            if name.startswith(f"{req.doc_id}_"):
                matches.append(name)
        #matches=[name for name in os.listdir("storage/docs") if name.startswith(f"{req.doc_id}_")]
    stored_filename=matches[0]
    stored_path=os.path.join("storage/docs", stored_filename)
    if stored_filename.lower().endswith(".txt"):
        with open(stored_path, "r", encoding="utf-8", errors="ignore") as r:
            text=r.read()
        return {
            "answer": f"This is the preview of the text document: {text[:200]}.....",
            "citations": [],
            "sources_used": []
        }
        


    if not matches:
        raise HTTPException(status_code=404, detail="The doc ID provided doesnot exists, Please check the ID again.")
    return{
        "answer": "Rag not implemented yet",
        "citations": [],
        "sources_used": []
    }"""

    dir_path = os.path.join("storage", "docs", req.doc_id)
    if not os.path.exists(dir_path):
        raise HTTPException(status_code=404, detail="The Doc ID provided does not exist, Please check the ID again.")
    
    matches =[]
    for name in os.listdir(dir_path):
        if os.path.isfile(os.path.join(dir_path, name)):
            matches.append(name)
    
    if not matches:
        raise HTTPException(status_code=404, detail="No files found under this Doc ID.")
    
    # txt_files=[]
    # for name in matches:
    #     if name.lower().endswith(".txt"):
    #         txt_files.append(name)
    
    # stored_filename=matches[0] if matches else txt_files[0]
    # if stored_filename.lower().endswith(".txt"):
    #     with open (os.path.join(dir_path, stored_filename), "r", encoding="utf-8", errors="ignore") as r:
    #         text=r.read()
    #     return {
    #         "answer" : f"The preview of the given document for the {req.doc_id} is : {text[:200]}...RAG is not implemented yet",
    #         "citations": [],
    #         "sources_used": []
    #     }

    stored_filename=matches[0]
    text=extract_txt(os.path.join(dir_path, stored_filename))

    if not text.strip(): 
        """.strip() while extraction because the python sees 
    empty spaces as text so whenever the file is image based it will give either " " or newline\n or 
    something empty. so python wont consider it as valid text."""
        
        return {
            "answer": "The extracted text is empty. Probably the pdf is scanned or image based. RAG not implemented yet.",
            "citations": [],
            "sources_used": []
        }
    return {
        "answer" : f"RAG not implemented yet. But the extracted text is: {text[:200]}",
        "citations": [],
        "sources_used": []
    }

if __name__ == "__main__":
    uvicorn.run("main:current_app", 
                host="0.0.0.0", 
                port=5000, 
                reload=True)