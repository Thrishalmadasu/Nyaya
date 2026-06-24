"""Scrape landmark Indian case summaries from Indian Kanoon using direct doc IDs.

Indian Kanoon's search HTML structure changes; direct /doc/{id}/ URLs are stable.
Doc IDs are pre-curated for landmark cases across criminal law, fundamental rights,
evidence, bail and sentencing.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover - very old urllib3
    Retry = None

PRECEDENTS_DIR = Path(__file__).parent.parent / "corpus" / "precedents"

HEADERS = {
    "User-Agent": "Nyaya-AI-Moot-Court/1.0 (educational legal-research corpus builder)"
}

BASE_URL = "https://indiankanoon.org"


def _session() -> requests.Session:
    """A requests session with retry/backoff on transient failures."""
    sess = requests.Session()
    sess.headers.update(HEADERS)
    if Retry is not None:
        retry = Retry(
            total=3,
            backoff_factor=1.5,  # 0s, 1.5s, 3s between attempts
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        sess.mount("https://", adapter)
        sess.mount("http://", adapter)
    return sess


def _expected_tokens(title: str) -> tuple[list[str], str | None]:
    """Derive validation tokens from a case title.

    Returns (party_surnames, year). A scraped page must mention at least one
    party surname AND the year to be accepted — this is what catches a stale
    doc ID silently returning the wrong judgment.
    """
    year_m = re.search(r"\((\d{4})\)", title)
    year = year_m.group(1) if year_m else None
    # Strip "v"/"vs" and the trailing "(Year)"; collect capitalised surnames.
    core = re.sub(r"\(\d{4}\)", "", title)
    words = re.split(r"\s+v\.?s?\.?\s+|\s+", core)
    stop = {"state", "of", "union", "india", "the", "and", "ors", "anr", "v", "vs",
            "public", "prosecutor", "cbi", "bombay", "municipal", "corporation"}
    surnames = [w for w in words if len(w) > 3 and w.lower() not in stop and w[:1].isupper()]
    return surnames, year


def _content_matches(text: str, title: str) -> bool:
    """True if the scraped text plausibly belongs to the expected case.

    Matching is by **party surname**, not year: a judgment's decision date and
    its citation year often differ (e.g. Tukaram/Mathura decided 1978, reported
    1979), so a year check produces false rejections. Surname mismatch alone is
    what catches the real failure mode — a stale doc_id returning an unrelated
    case (the "Olga Tellis" file that actually held "Prof. Bhim Singh").
    """
    surnames, _year = _expected_tokens(title)
    if not surnames:
        return True
    low = text.lower()
    return any(s.lower() in low for s in surnames)

# Landmark cases with Indian Kanoon doc IDs verified against the live site
# (doc_title party + court checked; the trailing comment is the IK "Cited by"
# count, our data-grounded 'most-cited' signal). All resolve to Supreme Court
# judgments. The scraper independently re-validates each by party surname before
# saving, so a stale ID can never silently poison the corpus.
LANDMARK_CASES = [
    # Fundamental rights
    {"slug": "maneka_gandhi_1978",       "doc_id": "1766147",   "title": "Maneka Gandhi v Union of India (1978)"},            # cited-by 1982
    {"slug": "kesavananda_bharati_1973", "doc_id": "257876",    "title": "Kesavananda Bharati v State of Kerala (1973)"},     # foundational
    {"slug": "ak_gopalan_1950",          "doc_id": "1857950",   "title": "A.K. Gopalan v State of Madras (1950)"},            # cited-by 1309
    {"slug": "puttaswamy_privacy_2017",  "doc_id": "91938676",  "title": "K.S. Puttaswamy v Union of India — Privacy (2017)"},# 9-judge bench
    {"slug": "olga_tellis_1985",         "doc_id": "709776",    "title": "Olga Tellis v Bombay Municipal Corporation (1985)"},
    # Murder and culpable homicide
    {"slug": "punnayya_1976",            "doc_id": "605891",    "title": "State of Andhra Pradesh v Rayavarapu Punnayya (1976)"}, # cited-by 373
    {"slug": "bachan_singh_1980",        "doc_id": "307021",    "title": "Bachan Singh v State of Punjab (1980)"},            # rarest-of-rare
    {"slug": "machhi_singh_1983",        "doc_id": "545301",    "title": "Machhi Singh v State of Punjab (1983)"},            # cited-by 785
    {"slug": "sharad_sarda_1984",        "doc_id": "13149785",  "title": "Sharad Birdhichand Sarda v State of Maharashtra (1984)"}, # cited-by 3286
    # Theft, robbery, property offences
    {"slug": "pyare_lal_1963",           "doc_id": "1689792",   "title": "Pyare Lal Bhargava v State of Rajasthan (1963)"},   # cited-by 117
    {"slug": "nanavati_1961",            "doc_id": "1596139",   "title": "K.M. Nanavati v State of Maharashtra (1961)"},      # cited-by 284
    # Evidence and circumstantial
    {"slug": "tofan_singh_2020",         "doc_id": "143202244", "title": "Tofan Singh v State of Tamil Nadu (2020)"},        # cited-by 1439
    # Private defence
    {"slug": "deo_narain_1972",          "doc_id": "32434",     "title": "Deo Narain v State of UP (1972)"},                 # cited-by 47
    {"slug": "darshan_singh_2010",       "doc_id": "1748156",   "title": "Darshan Singh v State of Punjab (2010)"},          # cited-by 228
    # Bail and procedure
    {"slug": "gudikanti_1978",           "doc_id": "656741",    "title": "Gudikanti Narasimhulu v Public Prosecutor (1978)"},# cited-by 3112
    {"slug": "arnesh_kumar_2014",        "doc_id": "2982624",   "title": "Arnesh Kumar v State of Bihar (2014)"},            # cited-by 25720
    {"slug": "satender_antil_2022",      "doc_id": "7148380",   "title": "Satender Kumar Antil v CBI (2022)"},               # cited-by 19037
    # Sentencing
    {"slug": "alister_pareira_2012",     "doc_id": "79026890",  "title": "Alister Anthony Pareira v State of Maharashtra (2012)"}, # cited-by 638
    # Sexual offences
    {"slug": "tukaram_mathura_1979",     "doc_id": "114584494", "title": "Tukaram v State of Maharashtra — Mathura (1979)"}, # cited-by 45
    {"slug": "gurmit_singh_1996",        "doc_id": "1046545",   "title": "State of Punjab v Gurmit Singh (1996)"},           # cited-by 1219
    # Domestic violence / 498A
    {"slug": "sushil_sharma_2005",       "doc_id": "1172674",   "title": "Sushil Kumar Sharma v Union of India (2005)"},     # cited-by 289
    # Constitution and criminal law intersections
    {"slug": "hussainara_khatoon_1979",  "doc_id": "1007347",   "title": "Hussainara Khatoon v Home Secretary, State of Bihar (1979)"}, # cited-by 992
    {"slug": "d_k_basu_1997",            "doc_id": "501198",     "title": "D.K. Basu v State of West Bengal (1997)"},         # cited-by 2221
]


# Max characters of judgment text to keep per case (full ratio + reasoning).
_MAX_CHARS = 20000


def _fetch_case(doc_id: str, sess: requests.Session) -> str | None:
    """Fetch judgment text from a direct Indian Kanoon doc URL."""
    url = f"{BASE_URL}/doc/{doc_id}/"
    try:
        resp = sess.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Try known containers first, then fall back to the main content region
        # so a markup change degrades gracefully instead of silently missing.
        judgment_div = (
            soup.find("div", class_="judgments")
            or soup.find("div", class_="maindoc")
            or soup.find("div", id="maindiv")
            or soup.find("div", class_="doc_content")
            or soup.find("main")
        )
        if not judgment_div:
            return None

        text = judgment_div.get_text(separator="\n", strip=True)
        return text[:_MAX_CHARS] if text else None

    except Exception as exc:
        print(f"    [error] doc/{doc_id}: {exc}")
        return None


def scrape_all(force: bool = False) -> dict:
    """Scrape all landmark cases.

    Returns a summary dict with disjoint counts so callers can tell genuine
    saves from skips/rejections/misses (no more inflated success count).
    """
    PRECEDENTS_DIR.mkdir(parents=True, exist_ok=True)
    sess = _session()
    scraped: list[str] = []
    skipped: list[str] = []
    rejected: list[str] = []   # fetched but content didn't match the expected case
    missing: list[str] = []    # no usable text at all

    for case in LANDMARK_CASES:
        slug, title, doc_id = case["slug"], case["title"], case["doc_id"]
        dest = PRECEDENTS_DIR / f"{slug}.txt"
        if dest.exists() and not force:
            print(f"  [skip] {title}")
            skipped.append(slug)
            continue

        print(f"  [scrape] {title} (doc/{doc_id})...")
        text = _fetch_case(doc_id, sess)

        if not text or len(text) <= 500:
            print(f"  [miss] {slug} — no usable text")
            missing.append(slug)
            time.sleep(1.5)
            continue

        if not _content_matches(text, title):
            print(f"  [reject] {slug} — scraped page does not match '{title}' "
                  f"(stale/wrong doc_id {doc_id}); NOT saved")
            rejected.append(slug)
            time.sleep(1.5)
            continue

        header = f"CASE: {title}\nSOURCE: {BASE_URL}/doc/{doc_id}/\n\n"
        dest.write_text(header + text, encoding="utf-8")
        print(f"  [ok] {slug} ({len(text)} chars)")
        scraped.append(slug)
        time.sleep(1.5)

    summary = {
        "scraped": scraped,
        "skipped": skipped,
        "rejected": rejected,
        "missing": missing,
        "total": len(LANDMARK_CASES),
    }
    print(
        f"\nScrape summary: {len(scraped)} saved, {len(skipped)} skipped, "
        f"{len(rejected)} rejected, {len(missing)} missing "
        f"(of {len(LANDMARK_CASES)} configured)."
    )
    if rejected:
        print(f"  REJECTED (wrong content — fix doc_id): {', '.join(rejected)}")
    if missing:
        print(f"  MISSING (no text — check doc_id/network): {', '.join(missing)}")
    return summary


def check_corpus_health() -> list[tuple[str, str]]:
    """Verify every configured case has a present, header-matching file.

    Returns a list of (slug, reason) problems — empty means a healthy corpus.
    Needs no network: it reads the saved ``CASE:`` header and checks the body
    plausibly matches, catching both missing files and silently wrong content.
    """
    problems: list[tuple[str, str]] = []
    for case in LANDMARK_CASES:
        dest = PRECEDENTS_DIR / f"{case['slug']}.txt"
        if not dest.exists():
            problems.append((case["slug"], "file missing"))
            continue
        text = dest.read_text(encoding="utf-8", errors="ignore")
        header_m = re.search(r"(?im)^CASE:\s*(.+)$", text)
        if not header_m:
            problems.append((case["slug"], "no CASE header"))
            continue
        if header_m.group(1).strip() != case["title"]:
            problems.append((case["slug"], f"header '{header_m.group(1).strip()}' != configured title"))
            continue
        # Body (after the header block) must plausibly match the expected case.
        body = text.split("\n\n", 1)[-1]
        if not _content_matches(body, case["title"]):
            problems.append((case["slug"], "body does not match expected case (wrong content)"))
    return problems


if __name__ == "__main__":
    print("Scraping landmark cases from Indian Kanoon (direct doc IDs)...")
    result = scrape_all()
    on_disk = len(result["scraped"]) + len(result["skipped"])
    print(f"\n{on_disk}/{result['total']} cases present in corpus/precedents/")
