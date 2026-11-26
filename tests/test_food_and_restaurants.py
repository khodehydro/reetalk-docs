"""Source and editorial regression checks for English topic five.

Automated checks protect selected distinctions, not all bilingual accuracy.
"""
import json
import re
import unittest

from tools.validate_reetalk import ENGLISH, load, validate
from tools.validate_image_prompts import ROOT, read_workbook

CATEGORY = ENGLISH / "05 - غذا و رستوران"


class FoodAndRestaurantsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = sorted(CATEGORY.glob("*.txt"))
        cls.drafts = {int(p.name[:2]): load(p.with_suffix(".json")) for p in cls.paths}

    def answer(self, lesson, question):
        q = next(q for q in self.drafts[lesson]["learning"]["questions"] if q["id"] == question)
        return next(o["text"] for o in q["options"] if o["id"] == q["correctOptionId"]), q

    def grammar(self, lesson, grammar):
        return next(g for g in self.drafts[lesson]["learning"]["grammar"] if g["id"] == grammar)

    def words(self, lesson, surface):
        return [w for w in self.drafts[lesson]["learning"]["words"] if w["text"].lower() == surface]

    def test_all_twelve_complete_at_workbook_levels(self):
        self.assertEqual(len(self.paths), 12)
        self.assertEqual(len(list(CATEGORY.glob("*.json"))), 12)
        cells = read_workbook(ROOT / "scenarios.xlsx")["سناریوها"]
        levels = {cells[f"A{r}"]: cells[f"H{r}"] for r in range(2, 362)}
        for n, path in enumerate(self.paths, 1):
            d = self.drafts[n]
            with self.subTest(lesson=n):
                self.assertEqual(d["dialogueId"], f"en-t05-s{n:02}")
                self.assertEqual(d["categoryId"], "food-and-restaurants")
                self.assertEqual(d["level"], levels[f"T05-S{n:02}"])
                validate(d, path.read_text(encoding="utf-8"), studio=n >= 4)

    def test_grammar_table_excerpts_are_real(self):
        for n, d in self.drafts.items():
            texts = [t["text"].lower() for t in d["turns"]]
            for g in d["learning"]["grammar"]:
                for table in g["tables"]:
                    for row in table["rows"]:
                        with self.subTest(lesson=n, grammar=g["id"], excerpt=row[0]):
                            self.assertTrue(any(row[0]["text"].lower() in t for t in texts))

    def test_word_cards_are_unique_by_surface_and_meaning(self):
        for n, d in self.drafts.items():
            senses = [(w["text"].lower(), w["meaning"]["fa"], w["meaning"]["en"])
                      for w in d["learning"]["words"]]
            with self.subTest(lesson=n):
                self.assertEqual(len(senses), len(set(senses)))

    def test_a1_popups_and_explanations_avoid_advanced_jargon(self):
        jargon = re.compile(r"متمم|فاعل صوری|وجه التزامی|intransitive|subjunctive|auxiliary|past participle", re.I)
        for n in (1, 2, 3):
            d = self.drafts[n]
            material = [t["gloss"] for turn in d["turns"] for t in turn["tokens"]]
            material += [w["meaning"] for w in d["learning"]["words"]]
            material += [g["explanation"] for g in d["learning"]["grammar"]]
            self.assertIsNone(jargon.search(json.dumps(material, ensure_ascii=False)))

    def test_coffee_preferences_and_joint_delivery(self):
        answer, _ = self.answer(1, "milk")
        self.assertEqual(answer["en"], "Hot milk")
        answer, _ = self.answer(1, "sugar")
        self.assertEqual(answer["en"], "No sugar")
        answer, _ = self.answer(1, "bill-time")
        self.assertEqual(answer["en"], "With the coffee")

    def test_water_with_lemon_is_not_pure_lemon_juice(self):
        answer, _ = self.answer(2, "drink")
        self.assertEqual(answer["en"], "A glass of water with lemon")
        self.assertIn("آب با لیمو", self.drafts[2]["turns"][6]["translation"]["fa"])
        g = self.grammar(2, "ordering-have")
        self.assertIn("not pure lemon juice", g["explanation"]["en"])

    def test_nine_turn_bill_source_and_receipt_speaker_are_preserved(self):
        d = self.drafts[3]
        self.assertEqual(len(d["turns"]), 9)
        self.assertEqual(d["turns"][8]["speakerId"], "customer")
        self.assertIn("here is the receipt", d["turns"][8]["text"])
        g = self.grammar(3, "payment-instructions-and-receipt")
        self.assertIn("retain that speaker", g["explanation"]["en"])
        g = self.grammar(3, "each-and-unit-price")
        self.assertIn("no total is invented", g["explanation"]["en"])

    def test_card_and_dishes_keep_food_context(self):
        self.assertEqual(self.words(3, "card")[0]["meaning"]["en"], "card; a bank payment card")
        for n in (5, 7, 8, 10, 11, 12):
            for word in self.words(n, "dishes"):
                self.assertIn("prepared foods", word["meaning"]["en"])

    def test_takeaway_price_and_wait_are_not_confused(self):
        answer, _ = self.answer(6, "total")
        self.assertEqual(answer["en"], "Fifteen")
        g = self.grammar(6, "duration-versus-ready")
        self.assertIn("Twenty minutes is not the price", g["explanation"]["en"])
        answer, _ = self.answer(6, "collect")
        self.assertEqual(answer["en"], "He will come back to collect it")

    def test_allergy_scope_process_and_reassurance_are_distinct(self):
        answer, _ = self.answer(7, "scope")
        self.assertIn("A nut allergy", answer["en"])
        answer, _ = self.answer(7, "process")
        self.assertIn("oil is shared", answer["en"])
        answer, _ = self.answer(7, "safety-scope")
        self.assertIn("no independent medical guarantee", answer["en"])
        used = self.words(7, "used")
        self.assertEqual(len(used), 1)
        self.assertEqual(used[0]["pronunciation"]["ipa"], "/juzd/")

    def test_compensation_is_only_for_wrong_dish(self):
        answer, q = self.answer(8, "waiver")
        self.assertEqual(answer["en"], "The cost of the wrong dish")
        self.assertEqual(q["evidenceTurnIds"], ["t10"])
        g = self.grammar(8, "compensation-scope")
        self.assertIn("does not make all dishes", g["explanation"]["en"])
        self.assertEqual(len(self.drafts[8]["turns"]), 13)

    def test_dinner_times_and_fallback_are_not_expanded(self):
        answer, _ = self.answer(9, "times")
        self.assertEqual(answer["en"], "Proposed booking at seven, readiness at six thirty, ten-minute drive")
        answer, _ = self.answer(9, "fallback")
        self.assertIn("next time", answer["en"])
        g = self.grammar(9, "plan-and-clock-times")
        self.assertIn("No exact departure time is stated", g["explanation"]["en"])

    def test_echoes_recover_the_right_predicate(self):
        g = self.grammar(9, "shared-anticipation-and-comparison")
        self.assertIn("looking forward to it", g["explanation"]["en"])
        answer, _ = self.answer(10, "echo")
        self.assertEqual(answer["en"], "Arman also remembers the steak’s taste")
        g = self.grammar(10, "relative-and-echo")
        self.assertIn("I agree", g["explanation"]["en"])

    def test_party_number_diets_and_restricted_drinks(self):
        answer, _ = self.answer(11, "number")
        self.assertEqual(answer["en"], "About fifty")
        answer, _ = self.answer(11, "ones")
        self.assertEqual(answer["en"], "The dishes")
        answer, _ = self.answer(11, "alcohol-scope")
        self.assertIn("ages are unspecified", answer["en"])
        g = self.grammar(11, "must-should-and-embedded-which")
        self.assertIn("Vegetarian is not equated with vegan", g["explanation"]["en"])

    def test_chef_source_role_and_separate_preparation_times(self):
        d = self.drafts[12]
        self.assertEqual(d["speakers"][0]["name"], "Dr. Ahmadi")
        self.assertIn("head chef", d["turns"][0]["text"])
        answer, _ = self.answer(12, "routines")
        self.assertIn("morning from the harbor", answer["en"])
        self.assertIn("each evening", answer["en"])
        g = self.grammar(12, "recipe-and-reduced-passive")
        self.assertIn("recipe differs from receipt", g["explanation"]["en"])

    def test_c1_inference_collective_credit_and_nonranking_most(self):
        answer, _ = self.answer(12, "could-tell")
        self.assertIn("recognize", answer["en"])
        answer, _ = self.answer(12, "team-credit")
        self.assertEqual(answer["en"], "Shares the recognition with the team")
        answer, _ = self.answer(12, "most-welcome")
        self.assertIn("intensifies", answer["en"])
        g = self.grammar(12, "could-tell-and-experiential-perfect")
        self.assertIn("not silently changed to had had", g["explanation"]["en"])


if __name__ == "__main__":
    unittest.main()
