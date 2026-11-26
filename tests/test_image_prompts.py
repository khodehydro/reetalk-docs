"""Workbook provenance checks and regressions for previously incorrect scenes."""
from copy import deepcopy
import unittest

from tools.validate_image_prompts import (
    ROOT, InvalidPrompts, STYLE, read_workbook, validate,
)


class ImagePromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sheets = read_workbook(ROOT / "scenarios.xlsx")
        cls.prompts = {
            cls.sheets["پرامپت سناریوها"][f"A{r}"]: cls.sheets["پرامپت سناریوها"][f"C{r}"]
            for r in range(2, 362)
        }

    def scene(self, code):
        return self.prompts[code][len(STYLE) + 1:].split(" Cast continuity: ", 1)[0]

    def test_all_source_references_and_prompt_copies(self):
        validate(self.sheets)

    def test_source_transcript_change_is_detected(self):
        sheets = deepcopy(self.sheets)
        sheets["تطبیق با متن انگلیسی"]["I2"] = "Different source dialogue"
        with self.assertRaisesRegex(InvalidPrompts, "transcript mismatch"):
            validate(sheets)

    def test_source_hash_change_is_detected(self):
        sheets = deepcopy(self.sheets)
        sheets["تطبیق با متن انگلیسی"]["D2"] = "0" * 64
        with self.assertRaisesRegex(InvalidPrompts, "hash mismatch"):
            validate(sheets)

    def test_original_column_cannot_remain_stale(self):
        sheets = deepcopy(self.sheets)
        sheets["سناریوها"]["K2"] = "Old scene"
        with self.assertRaisesRegex(InvalidPrompts, "prompts differ"):
            validate(sheets)

    def test_speaker_mismatch_is_detected(self):
        sheets = deepcopy(self.sheets)
        sheets["تطبیق با متن انگلیسی"]["E2"] = "Wrong / Characters"
        with self.assertRaisesRegex(InvalidPrompts, "speaker mismatch"):
            validate(sheets)

    def test_topic_cannot_reference_invented_scene(self):
        sheets = deepcopy(self.sheets)
        sheets["پرامپت موضوعات"]["C2"] = "Invented cafe scene"
        with self.assertRaisesRegex(InvalidPrompts, "representative source"):
            validate(sheets)

    def test_airport_cafe_is_not_airplane_service(self):
        scene = self.scene("T10-S05")
        self.assertIn("Arman and Sara share tea and a sandwich at a small airport cafe before boarding", scene)
        self.assertIn("Both are travelers", scene)

    def test_person_discussed_is_not_the_speaker(self):
        self.assertIn("Niloufar and Arash discussing him", self.scene("T13-S03"))
        self.assertIn("Leila and Friend discussing a phone", self.scene("T24-S05"))
        self.assertIn("Nima and Friend only", self.scene("T26-S12"))
        self.assertIn("Sara and Arash as the actual speakers", self.scene("T29-S11"))

    def test_locked_keys_are_in_car_not_house(self):
        scene = self.scene("T30-S08")
        self.assertIn("keys are locked inside her car in a supermarket parking lot", scene)
        self.assertIn("not an apartment door", scene)

    def test_station_directions_are_not_emergency_call(self):
        scene = self.scene("T30-S02")
        self.assertIn("Tourist asks Local for walking directions to the train station", scene)
        self.assertIn("not an emergency-address phone call", scene)

    def test_refund_and_charge_plot_mismatches(self):
        self.assertIn("cash kept in her room safe", self.scene("T11-S10"))
        self.assertIn("color faded after washing", self.scene("T07-S11"))
        self.assertIn("reprints it after checking his passport", self.scene("T09-S10"))
        self.assertIn("Both are shoppers", self.scene("T06-S09"))

    def test_specific_named_speaker_corrections(self):
        for code, actual in (
            ("T01-S02", "Leila"), ("T08-S11", "Farzad"),
            ("T09-S09", "Reza"), ("T13-S04", "Farhad"),
            ("T14-S10", "Mona"), ("T16-S05", "Maryam"),
            ("T19-S05", "Niloufar"), ("T21-S09", "Arash"),
            ("T22-S05", "Farhad"), ("T25-S03", "Mina"),
        ):
            with self.subTest(code=code):
                self.assertIn(actual, self.scene(code))

    def test_roles_not_swapped(self):
        self.assertIn("Leila is the supportive speaker", self.scene("T26-S02"))
        self.assertIn("a chef speaking with a diner", self.scene("T05-S12"))
        self.assertIn("porter and traveler moving luggage", self.scene("T10-S03"))

    def test_gender_casts_follow_existing_draft_profiles(self):
        self.assertIn("Sara (adult woman)", self.prompts["T01-S01"])
        self.assertIn("Amir (adult man)", self.prompts["T01-S01"])
        self.assertIn("Teacher (adult woman)", self.prompts["T01-S03"])
        self.assertIn("Mother (adult woman)", self.prompts["T30-S03"])
        self.assertIn("Husband (adult man)", self.prompts["T26-S08"])

    def test_uncertain_venue_not_arbitrarily_cafe_or_school(self):
        self.assertIn("current venue and contact channel are not established", self.scene("T01-S01"))
        self.assertIn("neutral abstract background", self.scene("T01-S04"))


if __name__ == "__main__":
    unittest.main()
