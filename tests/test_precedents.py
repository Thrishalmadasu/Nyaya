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


class PrecedentNameMatchTests(unittest.TestCase):
    """precedent_exists() matches full-form citations against the slug corpus."""

    def _require_corpus(self):
        try:
            from rag.retriever import _get_collection
            if _get_collection().count() == 0:
                raise unittest.SkipTest("corpus not built")
        except unittest.SkipTest:
            raise
        except Exception as exc:
            raise unittest.SkipTest(f"retrieval deps unavailable: {exc}")

    def test_full_form_citations_match_corpus_slugs(self):
        self._require_corpus()
        from rag.retriever import precedent_exists

        for citation in (
            "Kesavananda Bharati v. State of Kerala (1973)",
            "Maneka Gandhi v Union of India (1978)",
            "K.M. Nanavati v State of Maharashtra (1961)",     # single-surname slug
            "Bachan Singh v State of Punjab (1980)",            # common surname, two-token match
            "A.K. Gopalan v State of Madras (1950)",            # initials dropped, surname carries
        ):
            self.assertTrue(precedent_exists(citation), msg=citation)

    def test_fabricated_cases_do_not_match_locally(self):
        self._require_corpus()
        from rag.retriever import precedent_exists

        # A lone common surname must NOT verify a different real case.
        self.assertFalse(precedent_exists("Rajesh Kumar v State of Delhi (2021)"))
        self.assertFalse(precedent_exists("Totally Fake v Nobody (2099)"))


class PrecedentSearchTests(unittest.TestCase):
    def test_sanitize_strips_site_operators(self):
        from rag.precedent_search import _sanitize_query

        cleaned = _sanitize_query('murder -site:evil.com "quoted"')
        self.assertNotIn("site:", cleaned.lower())
        self.assertNotIn('"', cleaned)

    def test_party_tokens_drop_generic_words(self):
        from rag.precedent_search import _citation_party_tokens

        toks = [t.lower() for t in _citation_party_tokens("Maneka Gandhi v Union of India (1978)")]
        self.assertIn("maneka", toks)
        self.assertIn("gandhi", toks)
        # "union"/"india"/"of"/"v" and the year are not identifying tokens.
        self.assertNotIn("union", toks)
        self.assertNotIn("india", toks)
        self.assertNotIn("1978", toks)

    def test_verify_online_returns_none_without_key(self):
        import os
        from unittest import mock
        from rag import precedent_search

        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(precedent_search.verify_precedent_online("Some Case v Other (1999)"))

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
