"""Section-aware chunker for Indian statute PDFs and precedent text files."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class TextChunk:
    text: str
    metadata: dict = field(default_factory=dict)


# Patterns for splitting statute text into sections
_SECTION_PATTERNS = [
    re.compile(r"(?m)^(\d+[A-Z]?\.\s+[A-Z][^\n]{5,80})\n"),  # "103. Murder.—"
    re.compile(r"(?m)^Section\s+(\d+[A-Za-z]?)[\.\s—]"),
    re.compile(r"(?m)^(\d+[A-Za-z]?)\.\s+[A-Z]"),
]

# Pattern for Constitution articles
_ARTICLE_PATTERN = re.compile(r"(?m)^(\d+[A-Z]?)\.\s+[A-Z]")

# A single section's body is embedded as one chunk when it fits the window,
# otherwise split into overlapping windows so the tail is never dropped.
_SECTION_WINDOW = 1500
_SECTION_OVERLAP = 200


def _window_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping windows. Returns [text] if it already fits."""
    if len(text) <= size:
        return [text]
    step = max(1, size - overlap)
    windows = []
    for start in range(0, len(text), step):
        piece = text[start : start + size].strip()
        if piece:
            windows.append(piece)
        if start + size >= len(text):
            break
    return windows


def _extract_pdf_text(path: Path) -> str:
    doc = fitz.open(str(path))
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return "\n".join(pages)


def _chunk_statute(
    text: str,
    source_act: str,
    code_regime: str,
    year: int,
    is_constitution: bool = False,
) -> list[TextChunk]:
    """Split statute text by section/article markers."""
    chunks: list[TextChunk] = []

    if is_constitution:
        # Split on Article markers
        parts = re.split(r"(?m)^(\d+[A-Z]?)\.\s+", text)
    else:
        # Split on Section markers (digit + period + uppercase text)
        parts = re.split(r"(?m)^(\d+[A-Z]?)\.\s+", text)

    # parts alternates: [pre_text, section_num, section_body, section_num, ...]
    i = 1
    while i + 1 < len(parts):
        section_num = parts[i].strip()
        section_body = parts[i + 1].strip()

        if len(section_body) < 30:
            i += 2
            continue

        prefix = "Article" if is_constitution else "Section"
        section_id = f"{prefix} {section_num}"

        # Extract title from first line of body
        first_line = section_body.split("\n")[0][:120].strip()
        section_title = re.sub(r"[—\-]+$", "", first_line).strip()

        # Long sections are split into overlapping sub-chunks rather than
        # truncated at 1500 chars. Every sub-chunk keeps the same section_id and
        # section_title (so citation lookup by section_id is unaffected) and
        # records its 1-based part index.
        windows = _window_text(section_body, _SECTION_WINDOW, _SECTION_OVERLAP)
        for part_idx, part_body in enumerate(windows, start=1):
            chunk_text = f"{section_id}. {part_body}"
            chunks.append(
                TextChunk(
                    text=chunk_text,
                    metadata={
                        "source_act": source_act,
                        "section_id": section_id,
                        "section_title": section_title,
                        "code_regime": code_regime,
                        "year": year,
                        "part": str(part_idx),
                    },
                )
            )
        i += 2

    # Fallback: if few sections found, also chunk by sliding window over paragraphs
    # (handles gazette PDFs where section headers are embedded differently)
    if len(chunks) < 10:
        chunk_size = 1200
        overlap = 200
        for idx in range(0, len(text), chunk_size - overlap):
            snippet = text[idx : idx + chunk_size].strip()
            if len(snippet) < 80:
                continue
            # Try to extract a section number from the snippet for the section_id
            sec_match = re.search(r"\b(\d{1,3}[A-Z]?)\.\s+[A-Z]", snippet)
            sec_id = f"Section {sec_match.group(1)}" if sec_match else f"Para {idx // (chunk_size - overlap) + 1}"
            chunks.append(
                TextChunk(
                    text=snippet,
                    metadata={
                        "source_act": source_act,
                        "section_id": sec_id,
                        "section_title": "",
                        "code_regime": code_regime,
                        "year": year,
                    },
                )
            )

    return chunks


def chunk_statute_pdf(
    pdf_path: Path,
    source_act: str,
    code_regime: str,
    year: int,
) -> list[TextChunk]:
    text = _extract_pdf_text(pdf_path)
    is_const = "constitution" in pdf_path.name.lower()
    return _chunk_statute(text, source_act, code_regime, year, is_constitution=is_const)


def chunk_statute_txt(
    txt_path: Path,
    source_act: str,
    code_regime: str,
    year: int,
) -> list[TextChunk]:
    """Chunk a plain-text statute file (e.g. fetched from Indian Kanoon)."""
    text = txt_path.read_text(encoding="utf-8", errors="ignore")
    is_const = "constitution" in txt_path.name.lower()
    return _chunk_statute(text, source_act, code_regime, year, is_constitution=is_const)


def chunk_precedent_file(txt_path: Path) -> list[TextChunk]:
    """Chunk a precedent text file into ~1000-char overlapping chunks."""
    text = txt_path.read_text(encoding="utf-8", errors="ignore")
    case_name = txt_path.stem.replace("_", " ").title()

    chunks: list[TextChunk] = []
    chunk_size = 1000
    overlap = 150

    for i in range(0, len(text), chunk_size - overlap):
        snippet = text[i : i + chunk_size].strip()
        if len(snippet) < 100:
            continue
        chunks.append(
            TextChunk(
                text=snippet,
                metadata={
                    "source_act": "Precedent",
                    "section_id": f"Para {i // (chunk_size - overlap) + 1}",
                    "section_title": case_name,
                    "code_regime": "PRECEDENT",
                    "year": 0,
                },
            )
        )

    return chunks
