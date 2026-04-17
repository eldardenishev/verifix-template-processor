from __future__ import annotations
import subprocess
import shutil
from pathlib import Path
from app.config import LIBREOFFICE_PATH, TEMP_DIR


def convert_doc_to_docx(doc_path: Path) -> Path:
    """
    Converts a .doc file to .docx using LibreOffice headless mode.
    Returns the path to the converted .docx file.
    """
    if not doc_path.exists():
        raise FileNotFoundError(f"File not found: {doc_path}")

    if doc_path.suffix.lower() == ".docx":
        return doc_path  # already docx

    output_dir = TEMP_DIR / "converted"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy to temp dir to avoid path issues
    temp_input = output_dir / doc_path.name
    shutil.copy2(doc_path, temp_input)

    try:
        result = subprocess.run(
            [
                LIBREOFFICE_PATH,
                "--headless",
                "--convert-to", "docx",
                "--outdir", str(output_dir),
                str(temp_input),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"LibreOffice conversion failed (code {result.returncode}): {result.stderr}"
            )
    except FileNotFoundError:
        raise RuntimeError(
            f"LibreOffice not found at '{LIBREOFFICE_PATH}'. "
            "Install LibreOffice or set LIBREOFFICE_PATH environment variable."
        )

    converted_path = output_dir / (doc_path.stem + ".docx")
    if not converted_path.exists():
        raise RuntimeError(
            f"Conversion succeeded but output file not found at {converted_path}. "
            f"LibreOffice stdout: {result.stdout}"
        )

    return converted_path
