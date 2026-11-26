"""Regression checks for source-preserving drafts and validator failure modes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.validate_reetalk import ENGLISH, InvalidDraft, load, validate


class DraftValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = sorted(ENGLISH.rglob("*.json"))
        assert cls.paths, "Expected at least one authored draft"
        cls.original = load(cls.paths[0])

    def draft(self):
        return copy.deepcopy(self.original)

    def test_all_authored_drafts_match_sources(self):
        for path in self.paths:
            with self.subTest(path=path.name):
                validate(load(path), path.with_suffix(".txt").read_text(encoding="utf-8"))

    def test_studio_minimum_is_not_silently_relaxed(self):
        with self.assertRaises(InvalidDraft):
            validate(self.draft(), studio=True)

    def test_unknown_speaker(self):
        d = self.draft()
        d["turns"][0]["speakerId"] = "missing"
        with self.assertRaisesRegex(InvalidDraft, "unknown speaker"):
            validate(d)

    def test_mismatching_tokens(self):
        d = self.draft()
        d["turns"][0]["tokens"][0]["surface"] = "Hi!"
        with self.assertRaisesRegex(InvalidDraft, "token reconstruction"):
            validate(d)

    def test_incomplete_translation(self):
        d = self.draft()
        del d["turns"][0]["translation"]["fa"]
        with self.assertRaises(InvalidDraft):
            validate(d)

    def test_duplicate_turn_ids(self):
        d = self.draft()
        d["turns"][1]["id"] = d["turns"][0]["id"]
        with self.assertRaisesRegex(InvalidDraft, "duplicate IDs"):
            validate(d)

    def test_ragged_table(self):
        d = self.draft()
        d["learning"]["grammar"][0]["tables"][0]["rows"][0].pop()
        with self.assertRaisesRegex(InvalidDraft, "ragged"):
            validate(d)

    def test_invalid_table_cell(self):
        d = self.draft()
        d["learning"]["grammar"][0]["tables"][0]["rows"][0][0] = {"text": "I", "fa": "من"}
        with self.assertRaises(InvalidDraft):
            validate(d)

    def test_wrong_option_reference(self):
        d = self.draft()
        d["learning"]["questions"][0]["correctOptionId"] = "missing"
        with self.assertRaisesRegex(InvalidDraft, "unknown correct option"):
            validate(d)

    def test_wrong_evidence_reference(self):
        d = self.draft()
        d["learning"]["questions"][0]["evidenceTurnIds"] = ["t99"]
        with self.assertRaisesRegex(InvalidDraft, "unknown evidence"):
            validate(d)

    def test_duplicate_options(self):
        d = self.draft()
        q = d["learning"]["questions"][0]
        q["options"][1]["text"] = q["options"][0]["text"].copy()
        with self.assertRaisesRegex(InvalidDraft, "duplicate option"):
            validate(d)

    def test_extra_publishing_metadata(self):
        d = self.draft()
        d["media"] = {"audio": "audio.mp3"}
        with self.assertRaises(InvalidDraft):
            validate(d)

    def test_source_text_cannot_be_replaced(self):
        with self.assertRaisesRegex(InvalidDraft, "differs from source"):
            validate(self.draft(), "Sara: Another conversation.")

    def test_missing_word_card(self):
        d = self.draft()
        d["learning"]["words"].pop(0)
        with self.assertRaisesRegex(InvalidDraft, "uncovered words"):
            validate(d)

    def test_null_and_blank_are_rejected(self):
        for value in (None, "", " "):
            d = self.draft()
            d["title"]["fa"] = value
            with self.subTest(value=value), self.assertRaises(InvalidDraft):
                validate(d)

    def test_unrelated_phrase(self):
        d = self.draft()
        d["learning"]["phrases"][0]["text"] = "Goodbye forever"
        with self.assertRaisesRegex(InvalidDraft, "phrase absent"):
            validate(d)

    def test_duplicate_keys_and_bom(self):
        for data in (b'{"x":1,"x":2}', b'\xef\xbb\xbf{}', b'{"x":NaN}'):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "bad.json"
                path.write_bytes(data)
                with self.subTest(data=data), self.assertRaises(InvalidDraft):
                    load(path)

    def test_incorrect_json_syntax(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_text('{"x":1,}', encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                load(path)


if __name__ == "__main__":
    unittest.main()
