"""Chapter-one titles and preservation checks for the title-only revision."""
import hashlib
import json
import unittest

from tools.validate_reetalk import ENGLISH, load
from tools.validate_image_prompts import ROOT, read_workbook

CATEGORY = ENGLISH / "01 - معرفی و آشنایی"
# Hashes capture the pre-rename TXT bytes and canonical JSON excluding title.
EXPECTED = {1: ('سلام و آشنایی',
     'Hello and Introductions',
     '06003365260bb7bd044dc41dc1318320bb5b1b1dd7831c2a6fab4255877ea1a8',
     '3ef11eeebf68a9e7270584dc66f1a51ed78c1d470cb9a661a68ebe94e37690f6'),
 2: ('اهل کجایی؟',
     'Where Are You From?',
     'a9e0c0ce32fdfad4229ed4855ee5ec81f35bfc93acce85ab6093d043f13cb9cf',
     '0fee7c1d3ca01ed47d321bcb818cc0f9549a3577bc5a259390bd40f76f3f072e'),
 3: ('معرفی در کلاس',
     'Class Introductions',
     '3c944b5f95fc740a6f27f3c189664e1ecc6c64253c1c1ed1530f8507ec8def30',
     '60d544e1876516418f423a68ca9224e94e9e5e82ef2ea7491bed22f2c40ab956'),
 4: ('شماره و ایمیل',
     'Phone Number and Email',
     '18ef44880617bf539d1f7a5c88ccc532a15a25f5c7b6772a424c2c646526ed97',
     '2235a7b61aae8d75be3f9fe0ade36d6bffb7231f31d3a9cbb38c8b0e6ec755a8'),
 5: ('همسایه جدید',
     'The New Neighbor',
     'd7621c6bfd5f2f37c3d07b2a572e518a357523ad514a7ea5ab66745d49d8e37a',
     '515343c32b362822155869c9c024722cd0c953b73041b45ff453570127754026'),
 6: ('معرفی یک دوست',
     'Introducing a Friend',
     '50a6fea1706ca140bcead392fe303a387e421d08481c1087293d1406039f7943',
     'f23d3ac6289903b2a1a153838d3f0a2eea3578d38a2a166e785886bc26739f2d'),
 7: ('آشنایی در مهمانی',
     'Meeting at a Party',
     '028e1ff5d5d27bece288a46c24ae6c6e17efa6dd133e45b9ce07b2ddc2ce5d5b',
     '96bc04f9f73262e07522f5281ff95420197eb186962cb7881276ec1c5750abcb'),
 8: ('شغل و سرگرمی',
     'Work and Hobbies',
     '7257db27ec52fb52afadd36fcc86c706d7b7ed026b91bf1072e271b2cd8dd31b',
     '43b84c9fda37cfdeb2826a9dd893239b7ed2ec317820dfd9ccca280677498372'),
 9: ('روز اول کار',
     'First Day at Work',
     'd416434436a43ff88c5fef7fc1321501155a64e1ac3ad6a35f4900bba9555a9d',
     '70b634c1e72292a456a59a297d2af187556a196713a22440a17d2ed086193159'),
 10: ('گفت\u200cوگو در قطار',
      'Chatting on the Train',
      'aa8df81d13a33edb110e6dc951b9091d32ec969593ee8bdd0907650c493de053',
      '469e38489ba497419305557ec0eab403cfabfe09f883f4c0965fa881d04039d6'),
 11: ('پیشنهاد همکاری',
      'Exploring Collaboration',
      '16bc6ead2ad7d4e1e4b889c9e14d6e9143d738fa41e3dd0d76a5b17407297596',
      'a7544e11bd690e009c83fca17c07671e6617b776e08cb53e4973aee55674bd9e'),
 12: ('سخنران همایش',
      'The Conference Speaker',
      'c3b92b9b4f3c2714a8785d21201c7fc6fcc4652be6fe42352e6c2f1b8ab56bdb',
      'a448100f61b0dcc2d0f9cfbc0ab0ee4a80e6f2a2024fbf5a984e52ee5143da9b')}


class FirstChapterTitlesTests(unittest.TestCase):
    def test_names_and_bilingual_titles_match(self):
        self.assertEqual(len(list(CATEGORY.glob("*.txt"))), 12)
        self.assertEqual(len(list(CATEGORY.glob("*.json"))), 12)
        for n, (fa, en, _, _) in EXPECTED.items():
            with self.subTest(lesson=n):
                path = CATEGORY / f"{n:02} - {fa}.txt"
                draft = load(path.with_suffix(".json"))
                self.assertTrue(path.is_file())
                self.assertEqual(draft["title"], {"fa": fa, "en": en})
                self.assertEqual(draft["dialogueId"], f"en-t01-s{n:02}")
                self.assertEqual(len(list(CATEGORY.glob(f"{n:02} - *.txt"))), 1)
                self.assertEqual(len(list(CATEGORY.glob(f"{n:02} - *.json"))), 1)

    def test_all_dialogue_bytes_are_unchanged(self):
        for n, (fa, _, source_hash, _) in EXPECTED.items():
            with self.subTest(lesson=n):
                path = CATEGORY / f"{n:02} - {fa}.txt"
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source_hash)

    def test_json_except_title_is_unchanged(self):
        for n, (fa, _, _, content_hash) in EXPECTED.items():
            with self.subTest(lesson=n):
                draft = load(CATEGORY / f"{n:02} - {fa}.json")
                draft.pop("title")
                canonical = json.dumps(draft, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
                self.assertEqual(hashlib.sha256(canonical).hexdigest(), content_hash)

    def test_workbook_titles_and_source_paths_match(self):
        sheets = read_workbook(ROOT / "scenarios.xlsx")
        for n, (fa, _, source_hash, _) in EXPECTED.items():
            with self.subTest(lesson=n):
                row = n + 1
                self.assertEqual(sheets["سناریوها"][f"F{row}"], fa)
                self.assertEqual(sheets["پرامپت سناریوها"][f"B{row}"], fa)
                self.assertEqual(sheets["تطبیق با متن انگلیسی"][f"B{row}"], fa)
                path = CATEGORY / f"{n:02} - {fa}.txt"
                self.assertEqual(sheets["تطبیق با متن انگلیسی"][f"C{row}"], path.relative_to(ROOT).as_posix())
                self.assertEqual(sheets["تطبیق با متن انگلیسی"][f"D{row}"], source_hash)


if __name__ == "__main__":
    unittest.main()
