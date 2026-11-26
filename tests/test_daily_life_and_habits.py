"""Protect source fidelity and reviewed distinctions in the third category."""
import json
import re
import unittest

from tools.validate_reetalk import ENGLISH, load, validate
from tools.validate_image_prompts import ROOT, read_workbook

CATEGORY = ENGLISH / "03 - زندگی روزمره و عادت‌ها"


class DailyLifeAndHabitsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = sorted(CATEGORY.glob("*.txt"))
        cls.drafts = {int(p.name[:2]): load(p.with_suffix(".json")) for p in cls.paths}

    def test_all_twelve_complete_at_workbook_levels(self):
        self.assertEqual(len(self.paths), 12)
        self.assertEqual(len(list(CATEGORY.glob("*.json"))), 12)
        cells = read_workbook(ROOT / "scenarios.xlsx")["سناریوها"]
        levels = {cells[f"A{r}"]: cells[f"H{r}"] for r in range(2, 362)}
        for number, path in enumerate(self.paths, 1):
            d = self.drafts[number]
            with self.subTest(path=path.name):
                self.assertEqual(d["dialogueId"], f"en-t03-s{number:02}")
                self.assertEqual(d["categoryId"], "daily-life-and-habits")
                self.assertEqual(d["level"], levels[f"T03-S{number:02}"])
                validate(d, path.read_text(encoding="utf-8"), studio=number >= 5)

    def test_table_source_column_has_real_excerpts(self):
        for number, draft in self.drafts.items():
            texts = [t["text"].lower() for t in draft["turns"]]
            for grammar in draft["learning"]["grammar"]:
                for table in grammar["tables"]:
                    for row in table["rows"]:
                        with self.subTest(lesson=number, grammar=grammar["id"], excerpt=row[0]):
                            self.assertTrue(any(row[0]["text"].lower() in text for text in texts))

    def test_word_senses_are_not_exact_duplicate_cards(self):
        for number, draft in self.drafts.items():
            senses = [(w["text"].lower(), w["meaning"]["fa"], w["meaning"]["en"])
                      for w in draft["learning"]["words"]]
            with self.subTest(lesson=number):
                self.assertEqual(len(senses), len(set(senses)))

    def test_a1_popups_avoid_advanced_labels(self):
        jargon = re.compile(r"فاعل صوری|شبه‌شکاف|متمم|auxiliary|past participle|pseudocleft|fused relative", re.I)
        for number in range(1, 5):
            d = self.drafts[number]
            popups = [t["gloss"] for turn in d["turns"] for t in turn["tokens"]]
            popups += [w["meaning"] for w in d["learning"]["words"]]
            with self.subTest(lesson=number):
                self.assertIsNone(jargon.search(json.dumps(popups, ensure_ascii=False)))

    def test_watch_means_a_clock_in_two_but_a_verb_in_four(self):
        for number, expected in ((2, "ساعت مچی"), (4, "تماشا")):
            words = [w for w in self.drafts[number]["learning"]["words"] if w["text"].lower() == "watch"]
            self.assertEqual(len(words), 1)
            self.assertIn(expected, words[0]["meaning"]["fa"])

    def test_source_week_is_not_replaced_by_title_calendar(self):
        d = self.drafts[5]
        self.assertIn("from Monday to Friday", d["turns"][0]["text"])
        q = next(q for q in d["learning"]["questions"] if q["id"] == "workdays")
        answer = next(o for o in q["options"] if o["id"] == q["correctOptionId"])
        self.assertEqual(answer["text"]["en"], "Monday to Friday")

    def test_report_deadline_is_not_an_exclusive_event_day(self):
        d = self.drafts[8]
        q = next(q for q in d["learning"]["questions"] if q["id"] == "report")
        answer = next(o for o in q["options"] if o["id"] == q["correctOptionId"])
        self.assertEqual(answer["text"]["en"], "No later than Wednesday")
        self.assertEqual(q["evidenceTurnIds"], ["t03"])

    def test_smoking_duration_is_not_abstinence_duration(self):
        d = self.drafts[9]
        q = next(q for q in d["learning"]["questions"] if q["id"] == "duration")
        self.assertIn("before quitting", q["prompt"]["en"])
        self.assertIn("not the time since quitting", q["explanation"]["en"])
        self.assertEqual(q["evidenceTurnIds"], ["t02", "t03"])

    def test_unusual_third_person_elham_is_preserved_and_not_invented_away(self):
        d = self.drafts[10]
        self.assertEqual(d["speakers"][0]["name"], "Elham")
        self.assertEqual(d["turns"][0]["speakerId"], "elham")
        self.assertTrue(d["turns"][0]["text"].startswith("Elham is always"))
        grammar = next(g for g in d["learning"]["grammar"] if g["id"] == "reference-and-odd-source")
        self.assertIn("no extra identity is invented", grammar["explanation"]["en"])

    def test_c1_distinguishes_variable_position_from_required_boundary(self):
        d = self.drafts[12]
        ids = {g["id"] for g in d["learning"]["grammar"]}
        self.assertTrue({"mirrored-alternatives", "modality-and-personal-boundary",
                         "metaphorical-domination", "passive-and-relative"}.issubset(ids))
        q = next(q for q in d["learning"]["questions"] if q["id"] == "boundary")
        answer = next(o for o in q["options"] if o["id"] == q["correctOptionId"])
        self.assertIn("vary by person", answer["text"]["en"])
        self.assertIn("necessary", answer["text"]["en"])
        self.assertEqual(q["evidenceTurnIds"], ["t16"])


if __name__ == "__main__":
    unittest.main()
