from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import uvicorn
import uuid
import os
from pydantic import BaseModel

from services.extractor import parse_pdf_blocks
from services.chunking import chunk_sections
from services.embedding import embed_chunks, validate_embedded_chunks
from services.indexing import index_chunks
from services.bm25_index import build_bm25_index
from services.retrieval import retrieve
from services.answering import answer_question
from services.llm import LLMConfigError, LLMRateLimitError, LLMServerError


current_app = FastAPI()


@current_app.get("/health")
def health_check():
    return {"status": "Firstu fast api endpoint"}


@current_app.post("/ingest")
async def ingestDocuments(
    file: UploadFile = File(...),
    doc_type: str | None = Form(None),
):
    doc_id = str(uuid.uuid4())

    half_path = os.path.join("storage", "docs", doc_id)
    os.makedirs(half_path, exist_ok=True)
    save_filename = os.path.basename(file.filename)
    save_path = os.path.join(half_path, save_filename)

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    try:
        document = parse_pdf_blocks(save_path)
        document["document_id"] = doc_id
        chunks = chunk_sections(document)

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="Ingestion failed: no extractable chunks found in document",
            )

        embedded = embed_chunks(chunks)

        if not embedded:
            raise HTTPException(
                status_code=500,
                detail="Ingestion failed: embedding step returned no vectors",
            )

        valid = validate_embedded_chunks(embedded)

        if not valid:
            raise HTTPException(
                status_code=500,
                detail="Ingestion failed: no valid embedded chunks to index",
            )

        handle = index_chunks(valid)
        build_bm25_index()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "doc_type": doc_type,
        "chunk_count": handle["count"],
        "indexed": True,
        "status": "Document ingested and indexed successfully",
    }


class AskRequest(BaseModel):
    doc_id: str
    question: str


@current_app.post("/ask")
async def askQuestion(req: AskRequest):
    dir_path = os.path.join("storage", "docs", req.doc_id)
    if not os.path.exists(dir_path):
        raise HTTPException(status_code=404, detail="Doc ID not found.")

    try:
        retrieved = retrieve(req.question, top_k=5, doc_id=req.doc_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Retrieval failed: {e}")

    try:
        result = answer_question(req.question, retrieved)
    except LLMConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except LLMServerError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return result


if __name__ == "__main__":
    uvicorn.run(
        "main:current_app",
        host="0.0.0.0",
        port=5000,
        reload=True,
    )
