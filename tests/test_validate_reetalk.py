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

    def test_first_category_is_complete_at_source_levels(self):
        paths = sorted((ENGLISH / "01 - معرفی و آشنایی").glob("*.txt"))
        self.assertEqual(len(paths), 12)
        levels = ["A1"] * 4 + ["A2"] * 4 + ["B1"] * 2 + ["B2", "C1"]
        for index, (path, level) in enumerate(zip(paths, levels), 1):
            with self.subTest(path=path.name):
                d = load(path.with_suffix(".json"))
                self.assertEqual(d["level"], level)
                self.assertEqual(d["dialogueId"], f"en-t01-s{index:02}")
                validate(d, path.read_text(encoding="utf-8"), studio=index > 4)

    def test_new_neighbor_is_hamid_in_source_and_draft(self):
        path = ENGLISH / "01 - معرفی و آشنایی" / "05 - همسایه تازه‌وارد طبقه سوم.txt"
        source = path.read_text(encoding="utf-8")
        draft = load(path.with_suffix(".json"))
        self.assertIn("Hamid: Yes, I moved in yesterday, my name is Hamid.", source)
        self.assertEqual(draft["speakers"][1], {"id": "hamid", "name": "Hamid", "gender": "man"})
        for text in (source, json.dumps(draft, ensure_ascii=False)):
            self.assertNotIn("farhad", text.lower())
            self.assertNotIn("فرهاد", text)
        validate(draft, source)

    def test_word_example_must_be_a_real_turn(self):
        d = self.draft()
        d["learning"]["words"][0]["example"]["text"] = "A made-up example."
        d["learning"]["words"][0]["example"]["translation"]["en"] = "A made-up example."
        with self.assertRaisesRegex(InvalidDraft, "word example absent"):
            validate(d)

    def test_word_must_occur_in_its_own_example(self):
        d = self.draft()
        d["learning"]["words"][0]["example"] = {
            "text": d["turns"][-1]["text"],
            "translation": d["turns"][-1]["translation"].copy(),
        }
        with self.assertRaisesRegex(InvalidDraft, "word absent from its example"):
            validate(d)

    def test_phrase_must_occur_in_its_own_example(self):
        d = self.draft()
        d["learning"]["phrases"][0]["example"] = {
            "text": d["turns"][-1]["text"],
            "translation": d["turns"][-1]["translation"].copy(),
        }
        with self.assertRaisesRegex(InvalidDraft, "phrase absent from its example"):
            validate(d)

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
