"""Source fidelity and editorial regressions for the completed second category.

These checks protect reviewed distinctions; they do not prove linguistic quality.
"""
import json
import re
import unittest

from tools.validate_reetalk import ENGLISH, load, validate
from tools.validate_image_prompts import ROOT, read_workbook

CATEGORY = ENGLISH / "02 - خانواده و دوستان"


class FamilyAndFriendsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = sorted(CATEGORY.glob("*.txt"))
        cls.drafts = {int(p.name[:2]): load(p.with_suffix(".json")) for p in cls.paths}

    def test_all_twelve_complete_at_workbook_levels(self):
        self.assertEqual(len(self.paths), 12)
        self.assertEqual(len(list(CATEGORY.glob("*.json"))), 12)
        cells = read_workbook(ROOT / "scenarios.xlsx")["سناریوها"]
        levels = {cells[f"A{row}"]: cells[f"H{row}"] for row in range(2, 362)}
        for number, path in enumerate(self.paths, 1):
            d = self.drafts[number]
            with self.subTest(path=path.name):
                self.assertEqual(d["dialogueId"], f"en-t02-s{number:02}")
                self.assertEqual(d["categoryId"], "family-and-friends")
                self.assertEqual(d["level"], levels[f"T02-S{number:02}"])
                validate(d, path.read_text(encoding="utf-8"), studio=number >= 4)

    def test_table_source_column_contains_real_excerpts(self):
        for number, draft in self.drafts.items():
            texts = [t["text"].lower() for t in draft["turns"]]
            for grammar in draft["learning"]["grammar"]:
                for table in grammar["tables"]:
                    for row in table["rows"]:
                        excerpt = row[0]["text"].lower()
                        with self.subTest(lesson=number, grammar=grammar["id"], excerpt=excerpt):
                            self.assertTrue(any(excerpt in text for text in texts))

    def test_word_senses_are_not_duplicate_cards(self):
        for number, draft in self.drafts.items():
            senses = [(w["text"].lower(), w["meaning"]["fa"], w["meaning"]["en"])
                      for w in draft["learning"]["words"]]
            with self.subTest(lesson=number):
                self.assertEqual(len(senses), len(set(senses)))

    def test_beginner_popups_do_not_use_advanced_grammar_labels(self):
        jargon = re.compile(r"فاعل صوری|شبه‌شکاف|متمم|past participle|auxiliary|fused relative|pseudocleft", re.I)
        for number in (1, 2, 3):
            d = self.drafts[number]
            popups = [token["gloss"] for turn in d["turns"] for token in turn["tokens"]]
            popups += [w["meaning"] for w in d["learning"]["words"]]
            with self.subTest(lesson=number):
                self.assertIsNone(jargon.search(json.dumps(popups, ensure_ascii=False)))

    def test_age_and_personality_are_not_old_or_kind_literal_mismatches(self):
        d = self.drafts[2]
        old = next(x for x in d["turns"][2]["tokens"] if x["surface"].lower().strip('.,!?') == "old")
        self.assertIn("ساله", old["gloss"]["fa"])
        d = self.drafts[11]
        kind = next(x for x in d["turns"][1]["tokens"] if x["surface"].lower() == "kind")
        self.assertIn("نوع", kind["gloss"]["fa"])

    def test_final_meeting_time_is_not_initial_suggestion(self):
        d = self.drafts[5]
        q = next(q for q in d["learning"]["questions"] if q["id"] == "final-time")
        answer = next(o for o in q["options"] if o["id"] == q["correctOptionId"])
        self.assertEqual(answer["text"]["en"], "Six thirty")
        self.assertTrue({"t09", "t10"}.issubset(q["evidenceTurnIds"]))

    def test_school_children_follow_actual_speakers_not_title(self):
        d = self.drafts[7]
        self.assertEqual(d["turns"][1]["speakerId"], "mina")
        self.assertEqual(d["turns"][4]["speakerId"], "roya")
        self.assertIn("Mina’s son", d["objective"]["en"])
        self.assertIn("Roya’s daughter", d["objective"]["en"])

    def test_source_name_mismatches_are_preserved(self):
        self.assertEqual(self.drafts[9]["speakers"][0]["name"], "Amiri")
        self.assertEqual(self.drafts[10]["speakers"][1]["name"], "Parisa")

    def test_nonstandard_future_source_is_retained_but_explained(self):
        d = self.drafts[6]
        self.assertIn("and I bring a small gift", d["turns"][8]["text"])
        grammar = next(g for g in d["learning"]["grammar"] if g["id"] == "future-visit")
        self.assertIn("I will bring", grammar["explanation"]["en"])
        self.assertIn("source", grammar["explanation"]["en"].lower())

    def test_c1_teaches_scope_stance_and_focus_not_only_simple_tenses(self):
        d = self.drafts[12]
        ids = {g["id"] for g in d["learning"]["grammar"]}
        self.assertTrue({"historical-aspect", "qualification-and-concession", "what-focus",
                         "quantification-and-reference", "concession-and-condition"}.issubset(ids))
        q = next(q for q in d["learning"]["questions"] if q["id"] == "limited-claim")
        answer = next(o for o in q["options"] if o["id"] == q["correctOptionId"])
        self.assertIn("not universal", answer["text"]["en"])
        self.assertEqual(q["evidenceTurnIds"], ["t16"])


if __name__ == "__main__":
    unittest.main()
