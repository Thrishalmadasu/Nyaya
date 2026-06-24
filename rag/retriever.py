"""Chroma-based statute retrieval for the moot court RAG."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

_CHROMA_DIR = str(Path(__file__).parent.parent / "chroma_db")
_COLLECTION_NAME = "indian_law"

_client: chromadb.PersistentClient | None = None
_collection = None
_ef = None


def _get_collection():
    global _client, _collection, _ef
    if _collection is not None:
        return _collection

    _ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    _client = chromadb.PersistentClient(path=_CHROMA_DIR)
    _collection = _client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=_ef,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


@dataclass
class Chunk:
    text: str
    source_act: str
    section_id: str
    section_title: str
    code_regime: str
    year: str
    score: float = 0.0

    def format_for_llm(self) -> str:
        return (
            f"[{self.source_act} — {self.section_id}: {self.section_title}]\n"
            f"{self.text}\n"
        )


def retrieve(
    query: str,
    code_regime: str | None = None,
    top_k: int = 8,
    include_constitution: bool = False,
) -> list[Chunk]:
    """Query the Chroma collection and return the top-k relevant chunks.

    By default the filter is restricted to the active ``code_regime`` only.
    Constitutional articles are pulled in only when ``include_constitution`` is
    set — otherwise they compete in (and pollute) every ordinary-crime query,
    e.g. Article 20 surfacing for a murder case.
    """
    collection = _get_collection()

    where: dict | None = None
    if code_regime:
        regimes = [code_regime]
        if include_constitution and code_regime != "CONST":
            regimes.append("CONST")
        where = {"code_regime": {"$in": regimes}} if len(regimes) > 1 else {"code_regime": code_regime}

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, max(1, collection.count())),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[Chunk] = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, distances):
        chunks.append(
            Chunk(
                text=doc,
                source_act=meta.get("source_act", ""),
                section_id=meta.get("section_id", ""),
                section_title=meta.get("section_title", ""),
                code_regime=meta.get("code_regime", ""),
                year=str(meta.get("year", "")),
                score=1.0 - dist,
            )
        )

    return chunks


def retrieve_precedents(query: str, top_k: int = 3) -> list[Chunk]:
    """Query the Chroma collection for embedded precedent chunks.

    Mirrors ``retrieve()`` but filters strictly to ``code_regime="PRECEDENT"``
    so landmark-case paragraphs surface for advocate arguments without
    competing against statute sections. Returns an empty list if the corpus
    holds no precedents (callers can then fall back to internet search).
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, max(1, collection.count())),
        where={"code_regime": "PRECEDENT"},
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[Chunk] = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, distances):
        chunks.append(
            Chunk(
                text=doc,
                source_act=meta.get("source_act", "Precedent"),
                section_id=meta.get("section_id", ""),
                section_title=meta.get("section_title", ""),
                code_regime=meta.get("code_regime", "PRECEDENT"),
                year=str(meta.get("year", "")),
                score=1.0 - dist,
            )
        )

    return chunks


def section_exists(citation: str) -> bool:
    """Deterministically check if a citation exists in the corpus by metadata lookup.

    citation: e.g. "BNS Section 103" or "IPC Section 302"
    """
    collection = _get_collection()
    if collection.count() == 0:
        return False

    # Normalise the citation string to extract section_id
    import re

    match = re.search(r"[Ss]ection\s+(\d+[A-Za-z]*)", citation)
    if not match:
        # Try Article (for Constitution)
        match = re.search(r"[Aa]rticle\s+(\d+[A-Za-z]*)", citation)
        if not match:
            return False
        section_id = f"Article {match.group(1)}"
    else:
        section_id = f"Section {match.group(1)}"

    results = collection.get(
        where={"section_id": section_id},
        limit=1,
    )
    return len(results.get("ids", [])) > 0


# Generic words stripped from case titles before token matching, so a shared
# place/role word (e.g. "State", "Union of India") can never be one of the two
# tokens that make a precedent match.
_PRECEDENT_STOPWORDS = frozenset({
    "state", "of", "union", "india", "the", "and", "ors", "anr", "others",
    "public", "prosecutor", "cbi", "secretary", "home", "govt", "government",
    "versus", "vs",
})

# Distinctive name tokens for each PRECEDENT title in the corpus, cached on
# first use. The corpus stores short slug titles ("Kesavananda Bharati 1973");
# advocates cite full-form names ("Kesavananda Bharati v. State of Kerala
# (1973)"), so a metadata equality lookup like section_exists cannot work here.
_precedent_title_tokens: list[frozenset[str]] | None = None


def _precedent_name_tokens(text: str) -> frozenset[str]:
    """Lowercased name tokens of a case title — years, punctuation and generic
    words removed. Tokens shorter than 3 chars are dropped so initials like
    'A.K.' don't become noise (the distinctive surname carries the match)."""
    import re

    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return frozenset(
        tok
        for tok in cleaned.split()
        if len(tok) >= 3 and not tok.isdigit() and tok not in _PRECEDENT_STOPWORDS
    )


def precedent_exists(citation: str) -> bool:
    """True if a cited case plausibly matches a precedent in the local corpus.

    Match rule (deliberately high-precision): a citation matches a corpus case
    when either every name token of the corpus slug is present in the citation
    (covers single-surname slugs like 'Nanavati'), or the two share at least two
    name tokens (covers full-name slugs while making a chance collision on a
    common surname like 'Singh'/'Kumar' alone insufficient).

    Recall is intentionally traded for precision: real cases the local corpus
    doesn't hold (or names it as a slug the citation doesn't fully overlap) fall
    through to the Tavily web check in rag.precedent_search.verify_precedent_online.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return False

    global _precedent_title_tokens
    if _precedent_title_tokens is None:
        res = collection.get(where={"code_regime": "PRECEDENT"}, include=["metadatas"])
        titles = {m.get("section_title", "") for m in res.get("metadatas", [])}
        _precedent_title_tokens = [
            toks for toks in (_precedent_name_tokens(t) for t in titles) if toks
        ]

    cite_tokens = _precedent_name_tokens(citation)
    if not cite_tokens:
        return False

    for title_tokens in _precedent_title_tokens:
        if title_tokens <= cite_tokens or len(title_tokens & cite_tokens) >= 2:
            return True
    return False
