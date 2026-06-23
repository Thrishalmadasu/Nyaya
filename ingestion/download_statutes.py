"""Download Indian statute text from accessible government and legal sources.

Strategy per statute:
- BNS 2023 / BNSS 2023 / BSA 2023: Indian Kanoon full-text pages (clean English).
  The egazette.gov.in PDFs are bilingual Hindi/English two-column scans that
  PyMuPDF cannot section-split, so they are no longer used.
- IPC 1860 / CrPC 1973 / Constitution: Indian Kanoon full-text pages (confirmed accessible)
"""
from __future__ import annotations

import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

CORPUS_DIR = Path(__file__).parent.parent / "corpus" / "statutes"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Statutes sourced as PDF where available; text HTML as fallback.
# type: "pdf" → save as .pdf then process with PyMuPDF
# type: "html" → fetch Indian Kanoon page, extract judgments div, save as .txt
STATUTE_SOURCES = [
    {
        # Sourced from Indian Kanoon (clean English full text), not the egazette
        # PDF: the official gazette is a bilingual Hindi/English two-column scan
        # that PyMuPDF cannot section-split, so it fell back to meaningless "Para"
        # chunks. The Indian Kanoon HTML parses into all 358 real sections.
        "name": "BNS 2023",
        "filename": "bns_2023.txt",
        "type": "html",
        "urls": ["https://indiankanoon.org/doc/149679501/"],
        "code_regime": "BNS",
        "year": 2023,
    },
    {
        # Indian Kanoon full text (see BNS note above) — parses into 531 sections.
        "name": "BNSS 2023",
        "filename": "bnss_2023.txt",
        "type": "html",
        "urls": ["https://indiankanoon.org/doc/91117739/"],
        "code_regime": "BNS",
        "year": 2023,
    },
    {
        # Indian Kanoon full text (see BNS note above) — parses into 170 sections.
        "name": "BSA 2023",
        "filename": "bsa_2023.txt",
        "type": "html",
        "urls": ["https://indiankanoon.org/doc/70224818/"],
        "code_regime": "BNS",
        "year": 2023,
    },
    {
        "name": "IPC 1860",
        "filename": "ipc_1860.txt",
        "type": "html",
        "urls": ["https://indiankanoon.org/doc/1569253/"],
        "code_regime": "IPC",
        "year": 1860,
    },
    {
        "name": "CrPC 1973",
        "filename": "crpc_1973.txt",
        "type": "html",
        "urls": [
            "https://indiankanoon.org/doc/1684044/",   # CrPC 1973 full act
            "https://indiankanoon.org/doc/1587841/",
        ],
        "code_regime": "IPC",
        "year": 1973,
    },
    {
        "name": "Constitution of India",
        "filename": "constitution_india.txt",
        "type": "html",
        "urls": ["https://indiankanoon.org/doc/237570/"],
        "code_regime": "CONST",
        "year": 1950,
    },
]


def _fetch_html_text(url: str) -> str | None:
    """Fetch Indian Kanoon act page and extract full text."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        div = soup.find("div", class_="judgments") or soup.find("div", class_="maindoc")
        if not div:
            return None
        return div.get_text(separator="\n", strip=True)
    except Exception as exc:
        print(f"    [html error] {exc}")
        return None


def _fetch_pdf(url: str, dest: Path) -> bool:
    """Download a PDF to dest. Returns True on success."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=90, stream=True)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "pdf" not in ct and "octet" not in ct:
            return False
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return dest.stat().st_size > 10_000
    except Exception as exc:
        print(f"    [pdf error] {exc}")
        return False


def download_all(force: bool = False) -> list[dict]:
    """Download all statutes. Returns list of successfully saved entries."""
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    saved = []

    for entry in STATUTE_SOURCES:
        dest = CORPUS_DIR / entry["filename"]
        if dest.exists() and not force:
            print(f"  [skip] {entry['name']} already saved ({dest.stat().st_size // 1024} KB)")
            saved.append({**entry, "path": dest})
            continue

        print(f"  [fetch] {entry['name']} ({entry['type']}) ...")
        ok = False

        if entry["type"] == "pdf":
            for url in entry["urls"]:
                ok = _fetch_pdf(url, dest)
                if ok:
                    print(f"  [ok] {entry['name']} → {dest.name} ({dest.stat().st_size // 1024} KB)")
                    break
                time.sleep(1)
            if not ok:
                print(
                    f"  [skip] {entry['name']}: all URLs failed. "
                    f"Download manually from egazette.gov.in and place at corpus/statutes/{dest.name}"
                )

        elif entry["type"] == "html":
            for url in entry["urls"]:
                text = _fetch_html_text(url)
                if text and len(text) > 5000:
                    dest.write_text(text, encoding="utf-8")
                    print(f"  [ok] {entry['name']} → {dest.name} ({len(text) // 1000} KB text)")
                    ok = True
                    break
                time.sleep(1)
            if not ok:
                print(f"  [error] {entry['name']}: could not fetch text")

        if ok:
            saved.append({**entry, "path": dest})
        time.sleep(1.5)

    return saved


if __name__ == "__main__":
    print("Fetching Indian statute texts...")
    results = download_all()
    print(f"\nSaved {len(results)}/{len(STATUTE_SOURCES)} statutes.")
