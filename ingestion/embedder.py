"""Embed text chunks and upsert into Chroma."""
from __future__ import annotations

import hashlib
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from ingestion.chunker import TextChunk

_CHROMA_DIR = str(Path(__file__).parent.parent / "chroma_db")
_COLLECTION_NAME = "indian_law"

_BATCH_SIZE = 100


def _chunk_id(chunk: TextChunk) -> str:
    """Deterministic ID so re-runs don't duplicate entries.

    Includes the sub-chunk `part`: long sections are split into parts that all
    lead with the same "Section N. <title>. Keywords: ..." prefix, so a key
    based only on text[:80] would collide and the dedup step would silently drop
    every part after the first — undoing the long-section split.
    """
    meta = chunk.metadata
    key = f"{meta.get('source_act')}|{meta.get('section_id')}|{meta.get('part', '')}|{chunk.text[:80]}"
    return hashlib.md5(key.encode()).hexdigest()


def _get_collection():
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    client = chromadb.PersistentClient(path=_CHROMA_DIR)
    return client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def delete_acts(acts: list[str], verbose: bool = True) -> int:
    """Delete all existing chunks for the given source_act values.

    Chunk IDs are derived from (source_act, section_id, text), so re-ingesting
    an act with different/cleaner section splits would ADD new chunks alongside
    the stale ones rather than replace them. Deleting by source_act first makes
    a rebuild a true replacement — e.g. it purges the old mis-parsed 'BNS 2023'
    Para-junk before the clean 358-section version is upserted.
    """
    collection = _get_collection()
    removed = 0
    for act in acts:
        before = collection.count()
        collection.delete(where={"source_act": act})
        freed = before - collection.count()
        removed += freed
        if verbose:
            print(f"    cleared {freed} existing chunks for {act!r}")
    return removed


def upsert_chunks(chunks: list[TextChunk], verbose: bool = True) -> int:
    """Embed and upsert chunks into Chroma. Returns count upserted."""
    if not chunks:
        return 0

    # Deduplicate by ID globally — Chroma upsert requires unique IDs per batch
    seen: dict[str, TextChunk] = {}
    for c in chunks:
        cid = _chunk_id(c)
        if cid not in seen:
            seen[cid] = c
    unique_chunks = list(seen.values())

    if verbose and len(unique_chunks) < len(chunks):
        print(f"    deduplicated: {len(chunks)} → {len(unique_chunks)} unique chunks")

    collection = _get_collection()

    total = 0
    for i in range(0, len(unique_chunks), _BATCH_SIZE):
        batch = unique_chunks[i : i + _BATCH_SIZE]
        ids = [_chunk_id(c) for c in batch]
        documents = [c.text for c in batch]
        metadatas = [
            {k: str(v) for k, v in c.metadata.items()} for c in batch
        ]

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        total += len(batch)

        if verbose:
            print(f"    upserted {total}/{len(unique_chunks)} chunks...")

    return total
