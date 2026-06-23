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
