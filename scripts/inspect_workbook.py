from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def shared_strings(book: zipfile.ZipFile) -> list[str]:
    try:
        stream = book.open("xl/sharedStrings.xml")
    except KeyError:
        return []
    values: list[str] = []
    for event, elem in ET.iterparse(stream, events=("end",)):
        if elem.tag.endswith("}si"):
            values.append("".join(node.text or "" for node in elem.iter() if node.tag.endswith("}t")))
            elem.clear()
    return values


def cell_value(cell: ET.Element, strings: list[str]) -> str:
    kind = cell.attrib.get("t")
    value = cell.find("m:v", NS)
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
    raw = "" if value is None or value.text is None else value.text
    if kind == "s" and raw:
        return strings[int(raw)]
    return raw


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else next(Path.cwd().glob("*.xlsx"))
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    report = {"file": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest(), "sheets": []}
    with zipfile.ZipFile(path) as book:
        strings = shared_strings(book)
        wb = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall(f"{{{REL_NS}}}Relationship")}
        for sheet in wb.find("m:sheets", NS) or []:
            name = sheet.attrib["name"]
            rid = sheet.attrib[f"{{{NS['r']}}}id"]
            target = targets[rid].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            rows = cols = nonempty = formulas = errors = 0
            sample: list[list[str]] = []
            with book.open(target) as stream:
                for _, elem in ET.iterparse(stream, events=("end",)):
                    if elem.tag.endswith("}row"):
                        rows = max(rows, int(elem.attrib.get("r", rows + 1)))
                        values: dict[int, str] = {}
                        for cell in elem.findall("m:c", NS):
                            ref = cell.attrib.get("r", "A1")
                            letters = re.match(r"[A-Z]+", ref).group(0)
                            col = 0
                            for letter in letters:
                                col = col * 26 + ord(letter) - 64
                            cols = max(cols, col)
                            text = cell_value(cell, strings)
                            if text != "":
                                nonempty += 1
                                if rows <= 5 and col <= 20:
                                    values[col] = text[:160]
                            if cell.find("m:f", NS) is not None:
                                formulas += 1
                            if text in {"#ERROR!", "#NAME?", "#REF!", "#VALUE!"}:
                                errors += 1
                        if rows <= 5:
                            sample.append([values.get(i, "") for i in range(1, min(cols, 20) + 1)])
                        elem.clear()
            report["sheets"].append({"name": name, "rows": rows, "cols": cols, "nonempty": nonempty, "formulas": formulas, "error_cells": errors, "sample": sample})
    if "--compact" in sys.argv:
        compact = dict(report)
        compact["sheets"] = [{key: value for key, value in sheet.items() if key != "sample"} for sheet in report["sheets"]]
        print(json.dumps(compact, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
