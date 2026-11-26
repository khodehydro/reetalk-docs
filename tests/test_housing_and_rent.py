"""Regression checks for source fidelity and reviewed housing distinctions.

These protect selected editorial decisions, not all linguistic accuracy.
"""
import json
import re
import unittest

from tools.validate_reetalk import ENGLISH, load, validate
from tools.validate_image_prompts import ROOT, read_workbook

CATEGORY = ENGLISH / "04 - خانه و اجاره"


class HousingAndRentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = sorted(CATEGORY.glob("*.txt"))
        cls.drafts = {int(p.name[:2]): load(p.with_suffix(".json")) for p in cls.paths}

    def answer(self, lesson, question):
        q = next(q for q in self.drafts[lesson]["learning"]["questions"] if q["id"] == question)
        return next(o["text"] for o in q["options"] if o["id"] == q["correctOptionId"]), q

    def grammar(self, lesson, grammar):
        return next(g for g in self.drafts[lesson]["learning"]["grammar"] if g["id"] == grammar)

    def test_twelve_complete_at_workbook_levels(self):
        self.assertEqual(len(self.paths), 12)
        self.assertEqual(len(list(CATEGORY.glob("*.json"))), 12)
        cells = read_workbook(ROOT / "scenarios.xlsx")["سناریوها"]
        levels = {cells[f"A{r}"]: cells[f"H{r}"] for r in range(2, 362)}
        for n, path in enumerate(self.paths, 1):
            d = self.drafts[n]
            with self.subTest(lesson=n):
                self.assertEqual(d["dialogueId"], f"en-t04-s{n:02}")
                self.assertEqual(d["categoryId"], "housing-and-rent")
                self.assertEqual(d["level"], levels[f"T04-S{n:02}"])
                validate(d, path.read_text(encoding="utf-8"), studio=n >= 3)

    def test_table_first_column_is_a_real_excerpt(self):
        for n, d in self.drafts.items():
            texts = [t["text"].lower() for t in d["turns"]]
            for g in d["learning"]["grammar"]:
                for table in g["tables"]:
                    for row in table["rows"]:
                        with self.subTest(lesson=n, grammar=g["id"], excerpt=row[0]):
                            self.assertTrue(any(row[0]["text"].lower() in t for t in texts))

    def test_word_cards_are_unique_by_surface_and_sense(self):
        for n, d in self.drafts.items():
            senses = [(w["text"].lower(), w["meaning"]["fa"], w["meaning"]["en"])
                      for w in d["learning"]["words"]]
            with self.subTest(lesson=n):
                self.assertEqual(len(senses), len(set(senses)))

    def test_a1_explanations_and_popups_are_simple(self):
        jargon = re.compile(r"فاعل صوری|متمم|وجه التزامی|present participle|auxiliary|intransitive|subjunctive", re.I)
        for n in (1, 2):
            d = self.drafts[n]
            material = [t["gloss"] for turn in d["turns"] for t in turn["tokens"]]
            material += [w["meaning"] for w in d["learning"]["words"]]
            material += [g["explanation"] for g in d["learning"]["grammar"]]
            self.assertIsNone(jargon.search(json.dumps(material, ensure_ascii=False)))

    def test_address_floor_and_duration_are_distinct(self):
        answer, _ = self.answer(2, "number-floor")
        self.assertEqual(answer["en"], "Number twelve, second floor")
        answer, q = self.answer(2, "duration")
        self.assertEqual(answer["en"], "Two minutes")
        self.assertEqual(q["evidenceTurnIds"], ["t04", "t05"])

    def test_utilities_are_excluded_and_rental_is_only_intended(self):
        answer, _ = self.answer(3, "utilities")
        self.assertEqual(answer["en"], "Separately from rent")
        answer, _ = self.answer(3, "decision")
        self.assertIn("no signing is reported", answer["en"])
        words = self.drafts[3]["learning"]["words"]
        quiet = next(w for w in words if w["text"].lower() == "quiet")
        quite = next(w for w in words if w["text"].lower() == "quite")
        self.assertNotEqual(quiet["meaning"], quite["meaning"])

    def test_fixed_repair_is_not_fixed_price(self):
        words = [w for w in self.drafts[7]["learning"]["words"] if w["text"].lower() == "fixed"]
        self.assertEqual(len(words), 2)
        self.assertTrue(any("price" in w["meaning"]["en"] for w in words))
        self.assertTrue(any("repaired" in w["meaning"]["en"] for w in words))
        repaired = next(w for w in words if "repaired" in w["meaning"]["en"])
        self.assertIn("everything is fixed", repaired["example"]["text"])

    def test_rent_acceptance_is_conditional_and_increase_is_by(self):
        answer, q = self.answer(6, "gist")
        self.assertIn("in exchange for a two-year contract", answer["en"])
        self.assertEqual(q["evidenceTurnIds"], ["t08", "t09", "t10"])
        g = self.grammar(6, "amount-of-increase")
        self.assertIn("No base rent is given", g["explanation"]["en"])
        self.assertIn("By five percent", g["explanation"]["en"])

    def test_noise_note_final_location_and_conditional_escalation(self):
        answer, _ = self.answer(8, "final-delivery")
        self.assertEqual(answer["en"], "Under the door")
        answer, _ = self.answer(8, "manager-condition")
        self.assertEqual(answer["en"], "If the noise does not stop")

    def test_notice_is_not_visit_duration_and_source_is_preserved(self):
        d = self.drafts[9]
        self.assertIn("twenty-four hours notice", d["turns"][2]["text"])
        g = self.grammar(9, "advance-notice-form")
        self.assertIn("twenty-four hours’ notice", g["explanation"]["en"])
        self.assertIn("not the visit’s duration", g["explanation"]["en"])
        answer, _ = self.answer(9, "entry-alternatives")
        self.assertIn("or the tenant’s prior written permission", answer["en"])

    def test_legal_claims_and_contract_period_are_not_universalized(self):
        answer, _ = self.answer(9, "legal-scope")
        self.assertIn("no jurisdiction is identified", answer["en"])
        g = self.grammar(10, "elapsed-deadline-and-options")
        self.assertIn("this contract, not universal law", g["explanation"]["en"])
        answer, _ = self.answer(10, "mail-purpose")
        self.assertEqual(answer["en"], "To have a record of the letter’s delivery")

    def test_moving_process_is_not_completion(self):
        answer, _ = self.answer(11, "completion")
        self.assertEqual(answer["en"], "All packing is complete")
        self.assertIn("not establish", next(q for q in self.drafts[11]["learning"]["questions"]
                                           if q["id"] == "completion")["prompt"]["en"])
        answer, _ = self.answer(11, "van")
        self.assertEqual(answer["en"], "Saturday morning with two helpers")

    def test_c1_qualified_figures_and_preapproval(self):
        answer, _ = self.answer(12, "figures")
        self.assertTrue(answer["en"].startswith("Usually ten to twenty percent"))
        g = self.grammar(12, "qualified-figures-and-passive")
        self.assertIn("not guaranteed bank terms", g["explanation"]["en"])
        answer, _ = self.answer(12, "preapproval")
        self.assertIn("preliminary stage", answer["en"])
        g = self.grammar(12, "rates-and-partitive-reference")
        self.assertIn("other loans, not other people", g["explanation"]["en"])

    def test_c1_does_not_expand_spending_reply_into_a_stronger_promise(self):
        answer, q = self.answer(12, "scope-of-promise")
        self.assertIn("will not change his spending habits", answer["en"])
        self.assertEqual(q["evidenceTurnIds"], ["t12", "t13"])
        g = self.grammar(12, "until-approval-and-source-limit")
        self.assertIn("does not explicitly promise", g["explanation"]["en"])


if __name__ == "__main__":
    unittest.main()
