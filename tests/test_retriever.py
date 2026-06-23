"""Integration tests for retrieval scoping.

These need a built corpus (chroma_db) and load the embedding model. The check
and model load happen in setUpClass (not at import time) so test discovery
stays cheap and the class skips cleanly when the corpus or model is
unavailable (e.g. a fresh checkout in CI).
"""
import unittest


class RetrievalScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from rag.retriever import _get_collection
            if _get_collection().count() == 0:
                raise unittest.SkipTest("corpus not built; run python -m ingestion.build_corpus")
        except unittest.SkipTest:
            raise
        except Exception as exc:  # embedding model / chroma not available
            raise unittest.SkipTest(f"retrieval dependencies unavailable: {exc}")

    def test_regime_only_by_default_excludes_constitution(self):
        from rag.retriever import retrieve
        hits = retrieve("murder", code_regime="BNS", top_k=5)
        self.assertTrue(hits)
        self.assertTrue(all(h.source_act != "Constitution of India" for h in hits))

    def test_bns_murder_returns_a_real_murder_section(self):
        from rag.retriever import retrieve
        ids = {h.section_id for h in retrieve("punishment for murder", code_regime="BNS", top_k=5)}
        self.assertTrue({"Section 101", "Section 103"} & ids)

    def test_include_constitution_can_surface_articles(self):
        from rag.retriever import retrieve
        hits = retrieve(
            "right to life and personal liberty",
            code_regime="BNS",
            top_k=5,
            include_constitution=True,
        )
        self.assertTrue(any(h.source_act == "Constitution of India" for h in hits))

    def test_section_exists_basic(self):
        from rag.retriever import section_exists
        self.assertTrue(section_exists("BNS Section 103"))
        self.assertFalse(section_exists("BNS Section 99999"))


if __name__ == "__main__":
    unittest.main()
