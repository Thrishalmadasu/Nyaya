"""Scrape landmark Indian case summaries from Indian Kanoon using direct doc IDs.

Indian Kanoon's search HTML structure changes; direct /doc/{id}/ URLs are stable.
Doc IDs are pre-curated for landmark cases across criminal law, fundamental rights,
evidence, bail and sentencing.
"""
from __future__ import annotations

import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PRECEDENTS_DIR = Path(__file__).parent.parent / "corpus" / "precedents"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

BASE_URL = "https://indiankanoon.org"

# Landmark cases with verified Indian Kanoon doc IDs
LANDMARK_CASES = [
    # Fundamental rights
    {"slug": "maneka_gandhi_1978",       "doc_id": "1766147",  "title": "Maneka Gandhi v Union of India (1978)"},
    {"slug": "kesavananda_bharati_1973", "doc_id": "257876",   "title": "Kesavananda Bharati v State of Kerala (1973)"},
    {"slug": "ak_gopalan_1950",          "doc_id": "1687850",  "title": "AK Gopalan v State of Madras (1950)"},
    {"slug": "puttaswamy_privacy_2017",  "doc_id": "91938676", "title": "KS Puttaswamy v Union of India — Privacy (2017)"},
    {"slug": "olga_tellis_1985",         "doc_id": "648543",   "title": "Olga Tellis v Bombay Municipal Corporation (1985)"},
    # Murder and culpable homicide
    {"slug": "punnayya_1976",            "doc_id": "1088241",  "title": "State of AP v Rayavarapu Punnayya (1976)"},
    {"slug": "bachan_singh_1980",        "doc_id": "1090918",  "title": "Bachan Singh v State of Punjab (1980)"},
    {"slug": "machhi_singh_1983",        "doc_id": "1833970",  "title": "Machhi Singh v State of Punjab (1983)"},
    {"slug": "sharad_sarda_1984",        "doc_id": "156811",   "title": "Sharad Biradhichand Sarda v State of Maharashtra (1984)"},
    # Theft, robbery, property offences
    {"slug": "pyare_lal_1963",           "doc_id": "558614",   "title": "Pyare Lal Bhargava v State of Rajasthan (1963)"},
    {"slug": "nanavati_1961",            "doc_id": "1279714",  "title": "KM Nanavati v State of Maharashtra (1961)"},
    # Evidence and circumstantial
    {"slug": "shivaji_bobade_1973",      "doc_id": "625119",   "title": "Shivaji Sahabrao Bobade v State of Maharashtra (1973)"},
    {"slug": "arulvelu_2009",            "doc_id": "889888",   "title": "Arulvelu v State (2009)"},
    {"slug": "toofan_singh_2020",        "doc_id": "58443",    "title": "Toofan Singh v State of Tamil Nadu (2020)"},
    # Private defence
    {"slug": "deo_narain_1973",          "doc_id": "1810",     "title": "Deo Narain v State of UP (1973)"},
    {"slug": "darshan_singh_2010",       "doc_id": "1839958",  "title": "Darshan Singh v State of Punjab (2010)"},
    # Bail and procedure
    {"slug": "gudikanti_1978",           "doc_id": "1901578",  "title": "Gudikanti Narasimhulu v Public Prosecutor (1978)"},
    {"slug": "arnesh_kumar_2014",        "doc_id": "116848",   "title": "Arnesh Kumar v State of Bihar (2014)"},
    {"slug": "satender_antil_2022",      "doc_id": "163072",   "title": "Satender Kumar Antil v CBI (2022)"},
    # Sentencing
    {"slug": "alister_pareira_2012",     "doc_id": "1672119",  "title": "Alister Anthony Pareira v State of Maharashtra (2012)"},
    # Sexual offences
    {"slug": "tukaram_mathura_1979",     "doc_id": "1604151",  "title": "Tukaram v State of Maharashtra — Mathura (1979)"},
    {"slug": "gurmit_singh_1996",        "doc_id": "1985985",  "title": "State of Punjab v Gurmit Singh (1996)"},
    # Domestic violence / 498A
    {"slug": "sushil_sharma_2005",       "doc_id": "1101254",  "title": "Sushil Kumar Sharma v Union of India (2005)"},
    # Constitution and criminal law intersections
    {"slug": "hussainara_khatoon_1979",  "doc_id": "883392",   "title": "Hussainara Khatoon v State of Bihar (1979)"},
    {"slug": "d_k_basu_1997",            "doc_id": "619217",   "title": "DK Basu v State of West Bengal (1997)"},
]


def _fetch_case(doc_id: str) -> str | None:
    """Fetch judgment text from a direct Indian Kanoon doc URL."""
    url = f"{BASE_URL}/doc/{doc_id}/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        judgment_div = (
            soup.find("div", class_="judgments")
            or soup.find("div", class_="maindoc")
        )
        if not judgment_div:
            return None

        text = judgment_div.get_text(separator="\n", strip=True)
        return text[:10000] if text else None

    except Exception as exc:
        print(f"    [error] doc/{doc_id}: {exc}")
        return None


def scrape_all(force: bool = False) -> int:
    """Scrape all landmark cases. Returns count saved."""
    PRECEDENTS_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0

    for case in LANDMARK_CASES:
        dest = PRECEDENTS_DIR / f"{case['slug']}.txt"
        if dest.exists() and not force:
            print(f"  [skip] {case['title']}")
            saved += 1
            continue

        print(f"  [scrape] {case['title']} (doc/{case['doc_id']})...")
        text = _fetch_case(case["doc_id"])

        if text and len(text) > 500:
            header = f"CASE: {case['title']}\nSOURCE: {BASE_URL}/doc/{case['doc_id']}/\n\n"
            dest.write_text(header + text, encoding="utf-8")
            print(f"  [ok] {case['slug']} ({len(text)} chars)")
            saved += 1
        else:
            print(f"  [miss] {case['slug']} — no usable text")

        time.sleep(1.5)

    return saved


if __name__ == "__main__":
    print("Scraping landmark cases from Indian Kanoon (direct doc IDs)...")
    n = scrape_all()
    print(f"\nSaved {n}/{len(LANDMARK_CASES)} cases to corpus/precedents/")
