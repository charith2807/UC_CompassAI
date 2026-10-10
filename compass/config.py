"""Shared paths and settings. Every stage imports from here."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Keep Hugging Face model downloads inside the project, not in ~/.cache.
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))

DATA = ROOT / "data"
RAW_DIR = DATA / "raw"
MANIFEST = RAW_DIR / "manifest.jsonl"
# PDFs downloaded by hand (SharePoint blocks crawlers); sources recorded in a committed file.
MANUAL_DIR = RAW_DIR / "manual"
MANUAL_SOURCES = DATA / "manual_sources.jsonl"
NORMALIZED_DIR = DATA / "normalized"
CHUNKS_DIR = DATA / "chunks"
EMBEDDINGS_DIR = DATA / "embeddings"
BM25_DIR = DATA / "bm25"
CHROMA_DIR = ROOT / "chroma"

# Crawl
SITE = "https://www.ucumberlands.edu"
SITEMAP_URL = f"{SITE}/sitemap.xml"
USER_AGENT = "CumberlandsCompassAI/0.1 (student RAG course project; +https://github.com/charith2807/UC_CompassAI)"
REQUEST_DELAY_SECONDS = 1.0
# URLs the sitemap doesn't list, e.g. the PDFs your team already verified.
EXTRA_SEEDS: list[str] = [
    "https://www.ucumberlands.edu/sites/default/files/downloads/VisitorsGuide.pdf",
]
