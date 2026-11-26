#!/usr/bin/env python3
"""Validate authored ReeTalk drafts, without third-party dependencies.

Default: preserve the repository's source dialogue (4+ turns per speaker).
--studio: additionally enforce the proposed Studio minimum (5+ per speaker).
--require-complete: fail if any source text has no matching draft.
Structural validation is not a substitute for bilingual editorial review.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ENGLISH = ROOT / "سناریو" / "انگلیسی"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
# Only names actually spoken in authored lessons; ordinary words still need cards.
PROPER_NAMES = {
    "sara", "amir", "leila", "omid", "shiraz", "isfahan", "maryam", "tabriz", "nima.rezaei",
    "nadia", "hamid", "sam", "laila", "nigar", "arman", "poya", "mina", "arash", "milad",
    "tehran", "elham", "dr", "kamrani", "behnam", "reza", "nima", "mona",
}


class InvalidDraft(ValueError):
    """A failed content-contract check."""


def need(condition, message):
    if not condition:
        raise InvalidDraft(message)


def keys(value, expected, at):
    need(isinstance(value, dict), f"{at}: expected object")
    need(set(value) == set(expected.split()), f"{at}: unexpected or missing keys: {set(value) ^ set(expected.split())}")


def strings(value, at="root"):
    need(value is not None, f"{at}: null is not permitted")
    if isinstance(value, str):
        need(bool(value.strip()), f"{at}: empty string")
    elif isinstance(value, dict):
        for key, child in value.items():
            strings(child, f"{at}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            strings(child, f"{at}[{i}]")


def bilingual(value, at):
    keys(value, "fa en", at)
    need(all(isinstance(v, str) and v.strip() for v in value.values()), f"{at}: missing translation")


def nonempty_array(value, at):
    need(isinstance(value, list) and len(value) > 0, f"{at}: expected nonempty array")


def unique_ids(items, at):
    nonempty_array(items, at)
    ids = [item.get("id") for item in items]
    need(all(isinstance(i, str) and len(i) <= 64 and SLUG.fullmatch(i) for i in ids), f"{at}: invalid ID")
    need(len(ids) == len(set(ids)), f"{at}: duplicate IDs")
    return set(ids)


def example(value, at):
    keys(value, "text translation", at)
    need(isinstance(value["text"], str), f"{at}.text: expected string")
    bilingual(value["translation"], f"{at}.translation")
    # For English-target drafts English translations retain the English original.
    need(value["translation"]["en"] == value["text"], f"{at}: English text/translation mismatch")


def pronunciation(value, at):
    keys(value, "faReading ipa", at)
    need(all(isinstance(v, str) for v in value.values()), f"{at}: expected strings")
    need(value["ipa"].startswith("/") and value["ipa"].endswith("/"), f"{at}: IPA must be slash-delimited")
    need(bool(re.search(r"[\u0600-\u06ff]", value["faReading"])), f"{at}: expected Persian reading")


def validate(draft, source=None, studio=False):
    """Raise InvalidDraft for a structural or source-fidelity violation."""
    keys(draft, "draftSchemaVersion contentType dialogueId categoryId targetLanguage locale level title objective speakers turns learning", "root")
    strings(draft)
    need(type(draft["draftSchemaVersion"]) is int and draft["draftSchemaVersion"] == 1, "unsupported draft version")
    need(draft["contentType"] == "reetalk", "invalid contentType")
    for key in ("dialogueId", "categoryId"):
        need(isinstance(draft[key], str) and len(draft[key]) <= 64 and SLUG.fullmatch(draft[key]), f"invalid {key}")
    need(draft["targetLanguage"] == "en" and draft["locale"] == "en-US", "expected en / en-US")
    need(draft["level"] in {"A1", "A2", "B1", "B2", "C1", "C2"}, "invalid level")
    for key in ("title", "objective"):
        bilingual(draft[key], key)
    speakers = unique_ids(draft["speakers"], "speakers")
    need(len(speakers) == 2, "exactly two speakers required")
    for s in draft["speakers"]:
        keys(s, "id name gender", "speaker")
        need(s["gender"] in {"woman", "man"}, "invalid gender")
    turns = unique_ids(draft["turns"], "turns")
    need((10 if studio else 8) <= len(turns) <= 120, "turn count outside accepted range")
    counts = Counter()
    source_lines = []
    surface_words = set()
    names = {s["id"]: s["name"] for s in draft["speakers"]}
    for t in draft["turns"]:
        keys(t, "id speakerId text translation tokens", "turn")
        need(t["speakerId"] in speakers, "unknown speakerId")
        need(isinstance(t["text"], str), "turn text must be a string")
        counts[t["speakerId"]] += 1
        bilingual(t["translation"], "turn.translation")
        need(t["translation"]["en"] == t["text"], "English turn translation must retain source")
        nonempty_array(t["tokens"], "tokens")
        for token in t["tokens"]:
            keys(token, "surface gloss", "token")
            need(isinstance(token["surface"], str) and not re.search(r"\s", token["surface"]), "token contains whitespace")
            bilingual(token["gloss"], "token.gloss")
            surface_words.add(token["surface"].strip(".,!?").lower())
        need(" ".join(tk["surface"] for tk in t["tokens"]) == t["text"], f"token reconstruction failed: {t['id']}")
        source_lines.append(f"{names[t['speakerId']]}: {t['text']}")
    need(all(counts[s] >= (5 if studio else 4) for s in speakers), "insufficient turns per speaker")
    if source is not None:
        need(source_lines == source.strip().splitlines(), "dialogue differs from source TXT")
    keys(draft["learning"], "words grammar phrases questions", "learning")
    learn = draft["learning"]
    for key, values in learn.items():
        unique_ids(values, f"learning.{key}")
    for w in learn["words"]:
        keys(w, "id text pronunciation meaning example", "word")
        pronunciation(w["pronunciation"], "word.pronunciation")
        bilingual(w["meaning"], "word.meaning")
        example(w["example"], "word.example")
        need(w["text"].lower() in surface_words, f"unrelated word: {w['text']}")
        need(w["example"]["text"] in {t["text"] for t in draft["turns"]}, "word example absent from dialogue")
        example_words = {s.strip(".,!?").lower() for s in w["example"]["text"].split()}
        need(w["text"].lower() in example_words, "word absent from its example")
    covered = {w["text"].lower() for w in learn["words"]}
    need(not (surface_words - covered - PROPER_NAMES), f"uncovered words: {sorted(surface_words - covered - PROPER_NAMES)}")
    for g in learn["grammar"]:
        keys(g, "id title explanation example takeaway tables", "grammar")
        for key in ("title", "explanation", "takeaway"):
            bilingual(g[key], f"grammar.{key}")
        example(g["example"], "grammar.example")
        need(g["example"]["text"] in {t["text"] for t in draft["turns"]}, "grammar example absent from dialogue")
        nonempty_array(g["tables"], "grammar.tables")
        for table in g["tables"]:
            keys(table, "title columns rows", "table")
            bilingual(table["title"], "table.title")
            nonempty_array(table["columns"], "table.columns")
            for col in table["columns"]:
                bilingual(col, "column")
            nonempty_array(table["rows"], "table.rows")
            for row in table["rows"]:
                need(isinstance(row, list) and len(row) == len(table["columns"]), "ragged table row")
                for cell in row:
                    if isinstance(cell, dict) and set(cell) == {"text"}:
                        need(isinstance(cell["text"], str), "table text must be string")
                    else:
                        bilingual(cell, "table.cell")
    for p in learn["phrases"]:
        keys(p, "id text pronunciation meaning context example", "phrase")
        pronunciation(p["pronunciation"], "phrase.pronunciation")
        for key in ("meaning", "context"):
            bilingual(p[key], f"phrase.{key}")
        example(p["example"], "phrase.example")
        need(any(p["text"] in t["text"] for t in draft["turns"]), f"phrase absent from dialogue: {p['id']}")
        need(p["example"]["text"] in {t["text"] for t in draft["turns"]}, "phrase example absent from dialogue")
        need(p["text"] in p["example"]["text"], "phrase absent from its example")
    stages = set()
    for q in learn["questions"]:
        keys(q, "id stage type prompt options correctOptionId explanation evidenceTurnIds", "question")
        need(q["stage"] in {"gist", "detail", "review"}, "invalid question stage")
        stages.add(q["stage"])
        need(q["type"] == "multiple_choice", "unsupported question type")
        for key in ("prompt", "explanation"):
            bilingual(q[key], f"question.{key}")
        options = unique_ids(q["options"], "options")
        need(2 <= len(options) <= 6, "expected 2–6 options")
        need(q["correctOptionId"] in options, "unknown correct option")
        for o in q["options"]:
            keys(o, "id text", "option")
            bilingual(o["text"], "option.text")
        for language in ("fa", "en"):
            texts = [o["text"][language] for o in q["options"]]
            need(len(texts) == len(set(texts)), "duplicate option text")
        nonempty_array(q["evidenceTurnIds"], "evidenceTurnIds")
        need(all(t in turns for t in q["evidenceTurnIds"]), "unknown evidence turn")
        need(len(q["evidenceTurnIds"]) == len(set(q["evidenceTurnIds"])), "duplicate evidence turn")
    need({"gist", "detail"} <= stages, "gist and detail questions required")


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path):
    raw = path.read_bytes()
    need(not raw.startswith(b"\xef\xbb\xbf"), "UTF-8 BOM is forbidden")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicate_keys,
                      parse_constant=lambda s: (_ for _ in ()).throw(InvalidDraft(f"invalid constant: {s}")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    sources = sorted(ENGLISH.rglob("*.txt"))
    drafts = sorted(ENGLISH.rglob("*.json"))
    errors = []
    ids = set()
    for path in drafts:
        try:
            source = path.with_suffix(".txt")
            need(source.is_file(), "matching source TXT is missing")
            d = load(path)
            validate(d, source.read_text(encoding="utf-8"), args.studio)
            need(d["dialogueId"] not in ids, "dialogueId reused by another file")
            ids.add(d["dialogueId"])
        except (ValueError, TypeError, KeyError, OSError) as error:
            errors.append(f"{path.relative_to(ROOT)}: {error}")
    missing = [p for p in sources if not p.with_suffix(".json").is_file()]
    if args.require_complete and missing:
        errors.append(f"{len(missing)} source dialogues still have no JSON")
    print(f"English: {len(drafts)}/{len(sources)} drafts; {len(missing)} remaining; {len(errors)} errors.")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if drafts and not args.studio:
        short = sum(len(p.read_text(encoding="utf-8").strip().splitlines()) < 10 for p in sources if p.with_suffix(".json").is_file())
        if short:
            print(f"NOTE: {short} source-preserving drafts have fewer than Studio's proposed 10 turns. Run --studio to enforce that contract.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
