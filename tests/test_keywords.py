"""Tests for the offence -> synonym keyword map."""
import unittest

from ingestion.keywords import keywords_for


class KeywordMapTests(unittest.TestCase):
    def test_murder_synonyms(self):
        kws = keywords_for("Punishment for murder")
        self.assertIn("killing", kws)
        self.assertIn("caused death", kws)

    def test_theft_synonyms(self):
        kws = keywords_for("Theft")
        self.assertIn("stealing", kws)
        self.assertIn("taking property", kws)

    def test_generic_title_has_no_keywords(self):
        self.assertEqual(keywords_for("Short title, extent and commencement"), [])

    def test_no_duplicates_and_order_preserved(self):
        kws = keywords_for("Cheating")
        self.assertEqual(len(kws), len(set(kws)))
        self.assertEqual(kws[0], "fraud")

    def test_body_is_scanned_when_title_is_generic(self):
        # Title gives nothing, but the body mentions the offence.
        kws = keywords_for("Of offences", "Whoever commits theft shall be punished")
        self.assertIn("stealing", kws)


if __name__ == "__main__":
    unittest.main()
