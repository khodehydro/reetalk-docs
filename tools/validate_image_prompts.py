#!/usr/bin/env python3
"""Check workbook image-prompt provenance and all duplicated prompt columns.

Uses only Python's standard library. Semantic scene review remains an editorial
responsibility; source hashes detect later transcript changes, not bad readings.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
STYLE = (
    "Stylized 2D character illustration with angular, geometric shapes, sharp-edged gouache and cel-shading, "
    "and dry-brush texture. Bold ink linework with varied thickness, expressive large angular eyes, distinct "
    "blushed cheeks and nose, and sharp facial planes. High-contrast color palette adapted to the scene's mood, "
    "simplified graphic background with flat shapes, no 3D render, no soft airbrushing, no text. Scene:"
)
TOPIC_SUFFIX = (
    " Category-cover framing: use a slightly wider balanced composition of this same source-grounded interaction. "
    "Do not add other scenarios or written category titles."
)


class InvalidPrompts(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise InvalidPrompts(message)


def read_workbook(path):
    """Read cell values by sheet name, handling inline and shared strings."""
    with ZipFile(path) as z:
        need(z.testzip() is None, "Corrupt XLSX archive")
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            shared = ["".join(si.itertext()) for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        sheets = {}
        for sheet in workbook.find("s:sheets", NS):
            target = targets[sheet.attrib[f"{{{NS['r']}}}id"]]
            target = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
            root = ET.fromstring(z.read(target))
            cells = {}
            for c in root.findall("s:sheetData/s:row/s:c", NS):
                kind = c.attrib.get("t")
                value = c.find("s:v", NS)
                if kind == "inlineStr":
                    cells[c.attrib["r"]] = "".join(t.text or "" for t in c.findall("s:is//s:t", NS))
                elif value is not None:
                    cells[c.attrib["r"]] = shared[int(value.text)] if kind == "s" else value.text
            sheets[sheet.attrib["name"]] = cells
        return sheets


def validate(sheets, root=ROOT):
    for name in ("سناریوها", "خلاصه سطح‌ها", "پرامپت سناریوها", "پرامپت موضوعات", "تطبیق با متن انگلیسی", "راهنمای پرامپت‌ها"):
        need(name in sheets, f"Missing sheet: {name}")
    base = sheets["سناریوها"]
    scenarios = sheets["پرامپت سناریوها"]
    topics = sheets["پرامپت موضوعات"]
    summary = sheets["خلاصه سطح‌ها"]
    audit = sheets["تطبیق با متن انگلیسی"]
    source_files = {
        f"T{p.parent.name[:2]}-S{p.name[:2]}": p
        for p in (root / "سناریو" / "انگلیسی").rglob("*.txt")
    }
    need(len(source_files) == 360, "Expected 360 English source dialogues")
    codes = [base.get(f"A{r}") for r in range(2, 362)]
    need(len(set(codes)) == 360 and set(codes) == set(source_files), "Missing or duplicate scenario code")
    prompts = set()
    by_code = {}
    for r in range(2, 362):
        code = base[f"A{r}"]
        prefix = f"{code}: "
        source = source_files[code]
        raw = source.read_bytes()
        text = raw.decode("utf-8")
        names = list(dict.fromkeys(line.split(":", 1)[0] for line in text.strip().splitlines()))
        need(len(names) == 2, prefix + "Expected two source speakers")
        need(scenarios.get(f"A{r}") == audit.get(f"A{r}") == code, prefix + "Row/code mismatch")
        need(base.get(f"F{r}") == scenarios.get(f"B{r}") == source.stem[5:] == audit.get(f"B{r}"), prefix + "Title/source mismatch")
        need(audit.get(f"C{r}") == source.relative_to(root).as_posix(), prefix + "Incorrect source path")
        need(audit.get(f"D{r}") == hashlib.sha256(raw).hexdigest(), prefix + "Source changed: hash mismatch")
        need(audit.get(f"I{r}") == text, prefix + "Source transcript mismatch")
        need(audit.get(f"E{r}") == " / ".join(names), prefix + "Source speaker mismatch")
        prompt = scenarios.get(f"C{r}")
        need(isinstance(prompt, str) and prompt.startswith(STYLE + " "), prefix + "Missing exact style prefix")
        need(prompt == base.get(f"K{r}"), prefix + "Duplicated scenario prompts differ")
        need(prompt.count("Scene:") == 1, prefix + "Expected one Scene section")
        need(prompt not in prompts, prefix + "Duplicate scenario prompt")
        prompts.add(prompt)
        by_code[code] = prompt
        scene = audit.get(f"J{r}")
        need(isinstance(scene, str) and len(scene) > 40 and prompt.startswith(STYLE + " " + scene), prefix + "Audit scene does not match prompt")
        need(" Cast continuity: " in prompt, prefix + "Missing explicit casting")
        cast = prompt.split(" Cast continuity: ", 1)[1]
        for name in names:
            display = name.replace(", ", " ")
            need(display + " (adult" in cast, prefix + f"Missing cast role: {name}")
        for col in ("F", "G", "H"):
            need(bool(audit.get(f"{col}{r}")), prefix + "Missing casting, setting, or editorial explanation")
        need("One cohesive landscape 5:3" in prompt, prefix + "Missing cover composition")
        need("No collage, speech bubbles, lettering, numerals" in prompt, prefix + "Missing no-text safeguards")
    for r in range(2, 32):
        topic = int(summary[f"A{r}"])
        code = f"T{topic:02}-S01"
        expected = by_code[code] + TOPIC_SUFFIX
        need(topics.get(f"D{r}") == code, f"Topic {topic}: incorrect representative dialogue")
        need(topics.get(f"C{r}") == summary.get(f"J{r}") == expected, f"Topic {topic}: prompt not grounded in representative source")
        for br in range(2, 362):
            if int(base[f"B{br}"]) == topic:
                need(base.get(f"J{br}") == expected, f"Topic {topic}: duplicated topic prompt differs")
    for sheet_name, last in (("پرامپت سناریوها", 361), ("تطبیق با متن انگلیسی", 361), ("پرامپت موضوعات", 31)):
        code_rows = [int(re.search(r"\d+", cell)[0]) for cell in sheets[sheet_name] if re.fullmatch(r"A\d+", cell)]
        need(max(code_rows) == last, f"{sheet_name}: unexpected extra/missing rows")


def main():
    try:
        validate(read_workbook(ROOT / "scenarios.xlsx"))
    except (ValueError, KeyError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("PASS: 360 English source references, hashes, full transcripts, speaker lists, casts, unique prompts, and workbook copies.")
    print("PASS: 30 topic prompts match their stated representative dialogues.")
    print("NOTE: These checks establish provenance and consistency, not a proof of semantic accuracy or generated-image compliance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
