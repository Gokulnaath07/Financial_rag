import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", "32"))

CHROMA_PATH = os.environ.get("CHROMA_PATH", str(ROOT_DIR / "storage" / "chroma"))
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "financial_docs")
