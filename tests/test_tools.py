"""Tests for the LangChain @tool wrappers and their wiring into the auditor.

The citation validator is now the live mechanism the auditor uses to check
statute citations (routed through tool.invoke), so these tests pin both the
tool's act-aware contract and the auditor's string→bool parsing of its result.

Like test_retriever.py, these need a built corpus (chroma_db) and load the
embedding model; the guard runs in setUpClass so discovery stays cheap and the
class skips cleanly on a fresh checkout.
"""
import unittest


class CitationValidatorToolTests(unittest.TestCase):
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

    def _check(self, citation, expected_regime=None):
        from tools.citation_validator import citation_validator_tool
        return citation_validator_tool.invoke(
            {"citation": citation, "expected_regime": expected_regime}
        )

    def test_invoke_contract_found_and_not_found(self):
        self.assertTrue(self._check("BNS Section 103").startswith("FOUND"))
        self.assertTrue(self._check("BNS Section 99999").startswith("NOT FOUND"))

    def test_tool_is_act_aware(self):
        # Same regression as test_retriever, but routed through the tool: the
        # act-aware check must survive the @tool boundary.
        self.assertTrue(self._check("IPC Section 378", "IPC").startswith("FOUND"))
        self.assertTrue(self._check("BNS Section 378", "BNS").startswith("NOT FOUND"))
        self.assertTrue(self._check("BNS Section 303", "BNS").startswith("FOUND"))

    def test_bare_citation_uses_expected_regime(self):
        self.assertTrue(self._check("Section 378", "BNS").startswith("NOT FOUND"))
        self.assertTrue(self._check("Section 378", "IPC").startswith("FOUND"))


class AuditorRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from rag.retriever import _get_collection
            if _get_collection().count() == 0:
                raise unittest.SkipTest("corpus not built; run python -m ingestion.build_corpus")
        except unittest.SkipTest:
            raise
        except Exception as exc:
            raise unittest.SkipTest(f"retrieval dependencies unavailable: {exc}")

    def test_auditor_flags_wrong_regime_section_via_tool(self):
        # One good and one act-wrong citation; no precedents (keeps it offline).
        # The auditor now validates statutes through citation_validator_tool, so
        # this pins the node's FOUND/NOT FOUND parsing as well as the tool.
        from agents.auditor import auditor_node

        state = {
            "case_file": {"code_regime": "BNS"},
            "round_transcript": [
                {
                    "side": "prosecution",
                    "round_number": 1,
                    "statutes_cited": ["BNS Section 103", "BNS Section 378"],
                    "precedents_cited": [],
                }
            ],
        }
        out = auditor_node(state)
        audit = out["audit_result"]
        self.assertIn("BNS Section 103", audit["verified_citations"])
        self.assertIn("BNS Section 378", audit["hallucinated_citations"])
        self.assertFalse(out["audit_passed"])  # a hallucinated statute fails the audit


if __name__ == "__main__":
    unittest.main()
