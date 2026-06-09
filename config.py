import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent

# === Phase 3: Embedding & Indexing ===

EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", "32"))

CHROMA_PATH = os.environ.get("CHROMA_PATH", str(ROOT_DIR / "storage" / "chroma"))
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "financial_docs")

# === Phase 4: Retrieval ===

BM25_PATH = os.environ.get("BM25_PATH", str(ROOT_DIR / "storage" / "bm25"))
RERANKER_MODEL = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-base")
RERANK_ENABLED = os.environ.get("RERANK_ENABLED", "true").lower() == "true"

RETRIEVAL_TOP_K = int(os.environ.get("RETRIEVAL_TOP_K", "5"))
RERANK_TOP_N = int(os.environ.get("RERANK_TOP_N", "5"))
DENSE_CANDIDATES = int(os.environ.get("DENSE_CANDIDATES", "50"))
SPARSE_CANDIDATES = int(os.environ.get("SPARSE_CANDIDATES", "50"))

RETRIEVAL_FUSION = os.environ.get("RETRIEVAL_FUSION", "rrf")
RRF_K = int(os.environ.get("RRF_K", "60"))
HYBRID_ALPHA = float(os.environ.get("HYBRID_ALPHA", "0.5"))

# === Phase 4: Answering ===

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-2.5-flash")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.1"))
LLM_MAX_OUTPUT_TOKENS = int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "1024"))

NOT_FOUND_THRESHOLD = float(os.environ.get("NOT_FOUND_THRESHOLD", "0.005"))
TOP_K_FOR_PROMPT = int(os.environ.get("TOP_K_FOR_PROMPT", "5"))
