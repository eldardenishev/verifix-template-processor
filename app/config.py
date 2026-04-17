import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SOURCES_PATH = BASE_DIR / "sources" / "sources.json"

LIBREOFFICE_PATH = os.getenv("LIBREOFFICE_PATH", "libreoffice")
TEMP_DIR = Path(os.getenv("TEMP_DIR", "/tmp/verifix"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

CONTEXT_WINDOW = 50  # characters around entity for context extraction
