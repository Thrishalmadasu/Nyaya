"""Tests for statute chunking: windowing, sub-chunk metadata, keyword tagging."""
import unittest

from ingestion.chunker import _window_text, _chunk_statute


class WindowTextTests(unittest.TestCase):
    def test_short_text_is_single_window(self):
        self.assertEqual(_window_text("a short body", 1500, 200), ["a short body"])

    def test_long_text_splits_with_overlap(self):
        body = "x" * 4000
        windows = _window_text(body, 1500, 200)
        self.assertGreater(len(windows), 1)
        self.assertTrue(all(len(w) <= 1500 for w in windows))
        # Consecutive windows overlap by the configured amount.
        self.assertEqual(windows[0][-200:], windows[1][:200])


def _synthetic_statute() -> str:
    # >=10 sections so the <10-section blind-window fallback does not fire.
    parts = ["1. Short title.\nThis Act may be called the Test Act."]
    parts.append("2. Murder.\n" + ("Whoever causes the death of another shall be guilty. " * 40))
    for n in range(3, 13):
        parts.append(f"{n}. Provision {n}.\nBody of provision number {n}.")
    return "\n".join(parts)


class ChunkStatuteTests(unittest.TestCase):
    def setUp(self):
        self.chunks = _chunk_statute(_synthetic_statute(), "TEST", "BNS", 2023)

    def test_no_fallback_para_chunks(self):
        self.assertFalse(any(c.metadata["section_id"].startswith("Para") for c in self.chunks))

    def test_long_section_splits_into_parts_sharing_section_id(self):
        s2 = [c for c in self.chunks if c.metadata["section_id"] == "Section 2"]
        self.assertGreater(len(s2), 1)
        # All parts keep the same section_id and title; parts are numbered.
        self.assertEqual({c.metadata["section_title"] for c in s2}, {"Murder."})
        self.assertEqual(sorted(c.metadata["part"] for c in s2), [str(i + 1) for i in range(len(s2))])

    def test_keywords_attached_for_known_offence(self):
        s2 = next(c for c in self.chunks if c.metadata["section_id"] == "Section 2")
        self.assertIn("killing", s2.metadata["keywords"])
        self.assertTrue(s2.text.startswith("Section 2. Murder."))

    def test_every_chunk_has_core_metadata(self):
        for c in self.chunks:
            for key in ("source_act", "section_id", "section_title", "code_regime", "year", "part"):
                self.assertIn(key, c.metadata)


if __name__ == "__main__":
    unittest.main()
