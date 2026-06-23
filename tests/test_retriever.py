"""Integration tests for retrieval scoping.

These need a built corpus (chroma_db) and load the embedding model, so they
skip automatically when the corpus is empty (e.g. a fresh checkout in CI).
"""
import unittest

from rag.retriever import _get_collection, retrieve, section_exists

_CORPUS_EMPTY = _get_collection().count() == 0


@unittest.skipIf(_CORPUS_EMPTY, "corpus not built; run python -m ingestion.build_corpus")
class RetrievalScopeTests(unittest.TestCase):
    def test_regime_only_by_default_excludes_constitution(self):
        hits = retrieve("murder", code_regime="BNS", top_k=5)
        self.assertTrue(hits)
        self.assertTrue(all(h.source_act != "Constitution of India" for h in hits))

    def test_bns_murder_returns_a_real_murder_section(self):
        ids = {h.section_id for h in retrieve("punishment for murder", code_regime="BNS", top_k=5)}
        self.assertTrue({"Section 101", "Section 103"} & ids)

    def test_include_constitution_can_surface_articles(self):
        hits = retrieve(
            "right to life and personal liberty",
            code_regime="BNS",
            top_k=5,
            include_constitution=True,
        )
        self.assertTrue(any(h.source_act == "Constitution of India" for h in hits))

    def test_section_exists_basic(self):
        self.assertTrue(section_exists("BNS Section 103"))
        self.assertFalse(section_exists("BNS Section 99999"))


if __name__ == "__main__":
    unittest.main()
