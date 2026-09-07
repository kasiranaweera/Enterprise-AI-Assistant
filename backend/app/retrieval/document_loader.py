"""
Loads mock enterprise documents from backend/data/sample_docs and
chunks them with metadata, matching the schema in the spec:

{
  "department": "payments",
  "document_type": "incident",
  "access_level": "internal",
  "created_date": "2025-01-01"
}

Filenames encode metadata as: <type>__<department>__<access>__<date>__<slug>.md
e.g. incident__payments__internal__2025-03-14__payment-gateway-outage.md
This keeps the POC data self-describing without a separate DB.
"""
import re
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "sample_docs"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120


@dataclass
class Chunk:
    doc_id: str
    chunk_id: str
    text: str
    metadata: dict


def _parse_filename(path: Path) -> dict:
    stem = path.stem
    parts = stem.split("__")
    if len(parts) != 5:
        return {
            "document_type": "unknown",
            "department": "general",
            "access_level": "internal",
            "created_date": "2025-01-01",
            "title": stem,
        }
    doc_type, dept, access, date, slug = parts
    return {
        "document_type": doc_type,
        "department": dept,
        "access_level": access,
        "created_date": date,
        "title": slug.replace("-", " "),
    }


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= size:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def load_all_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    if not DATA_DIR.exists():
        return chunks
    for path in sorted(DATA_DIR.glob("*.md")):
        meta = _parse_filename(path)
        doc_id = path.stem
        raw = path.read_text(encoding="utf-8")
        for i, piece in enumerate(_chunk_text(raw)):
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    chunk_id=f"{doc_id}::chunk{i}",
                    text=piece,
                    metadata={**meta, "doc_id": doc_id},
                )
            )
    return chunks


def list_documents() -> list[dict]:
    """List metadata for all document files in DATA_DIR."""
    docs = []
    if not DATA_DIR.exists():
        return docs
    for path in sorted(DATA_DIR.glob("*.md")):
        meta = _parse_filename(path)
        docs.append({
            "doc_id": path.stem,
            "filename": path.name,
            "title": meta.get("title", path.stem),
            "department": meta.get("department", "general"),
            "document_type": meta.get("document_type", "unknown"),
            "access_level": meta.get("access_level", "internal"),
            "created_date": meta.get("created_date", ""),
            "size_bytes": path.stat().st_size,
        })
    return docs


def save_document(
    content: str,
    title: str,
    department: str = "general",
    document_type: str = "guideline",
    access_level: str = "internal",
    created_date: str = "2025-01-01",
) -> str:
    """Save a new document markdown file to DATA_DIR."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-") or "document"
    filename = f"{document_type}__{department}__{access_level}__{created_date}__{slug}.md"
    target_path = DATA_DIR / filename
    target_path.write_text(content, encoding="utf-8")
    return target_path.stem


def delete_document(doc_id: str) -> bool:
    """Delete a document markdown file matching doc_id."""
    if not DATA_DIR.exists():
        return False
    for path in DATA_DIR.glob("*.md"):
        if path.stem == doc_id:
            path.unlink()
            return True
    return False

