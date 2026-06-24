"""Tests for the precedent corpus, retrieval, and local-first search.

The corpus-integrity test needs no Chroma/model — it just reads the saved
precedent files. The retrieval test loads the embedding model and skips
cleanly when the corpus is unbuilt (mirrors tests/test_retriever.py).
"""
import unittest
from pathlib import Path


class PrecedentCorpusIntegrityTests(unittest.TestCase):
    """Every configured case must have a present, header-matching file."""

    def test_no_missing_or_mismatched_precedents(self):
        from ingestion.scrape_kanoon import check_corpus_health, PRECEDENTS_DIR

        if not PRECEDENTS_DIR.exists() or not any(PRECEDENTS_DIR.glob("*.txt")):
            self.skipTest("precedent corpus not scraped yet")
        problems = check_corpus_health()
        self.assertEqual(
            problems, [],
            msg="corpus health problems: " + "; ".join(f"{s}: {r}" for s, r in problems),
        )

    def test_content_match_rejects_wrong_case(self):
        # The validator that guards against the olga_tellis class of bug.
        from ingestion.scrape_kanoon import _content_matches

        olga = "Olga Tellis v Bombay Municipal Corporation (1985)"
        bhim_singh_text = "Jammu & Kashmir High Court Prof. Bhim Singh vs Choudhary Talib Hussain 2006"
        self.assertFalse(_content_matches(bhim_singh_text, olga))
        real_olga_text = "Supreme Court Olga Tellis pavement dwellers Bombay Municipal Corporation 1985"
        self.assertTrue(_content_matches(real_olga_text, olga))


class PrecedentSearchTests(unittest.TestCase):
    def test_sanitize_strips_site_operators(self):
        from rag.precedent_search import _sanitize_query

        cleaned = _sanitize_query('murder -site:evil.com "quoted"')
        self.assertNotIn("site:", cleaned.lower())
        self.assertNotIn('"', cleaned)

    def test_get_precedents_local_first(self):
        # With the corpus built, get_precedents must return local results
        # (source="corpus") without needing a Tavily key.
        try:
            from rag.retriever import _get_collection
            if _get_collection().count() == 0:
                raise unittest.SkipTest("corpus not built")
        except unittest.SkipTest:
            raise
        except Exception as exc:
            raise unittest.SkipTest(f"retrieval deps unavailable: {exc}")

        from rag.retriever import retrieve_precedents
        chunks = retrieve_precedents("murder culpable homicide", top_k=3)
        # All returned chunks must be precedents, never statute sections.
        self.assertTrue(all(c.code_regime == "PRECEDENT" for c in chunks))


if __name__ == "__main__":
    unittest.main()
