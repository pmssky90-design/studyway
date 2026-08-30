from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

from apply_school_homepage_links import CSS_END, CSS_START, END, START, load_records, page_path, school_family


def marked_block(source: str) -> str:
    start = source.find(START)
    end = source.find(END, start)
    return "" if start < 0 or end < 0 else source[start : end + len(END)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit StudyWay official-school-homepage links.")
    parser.add_argument("public", type=Path)
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "studyway_school_homepages.json")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    public = args.public.resolve()
    records = load_records(args.data.resolve())
    errors: list[dict[str, str]] = []
    roots_external = details_internal = excluded_roots = family_pages = 0

    for record in records:
        family = school_family(public, record)
        family_pages += len(family)
        root = page_path(public, str(record["root_url"])).resolve()
        if len(family) != 9:
            errors.append({"school": str(record["school_name"]), "issue": f"family count {len(family)} != 9"})
        for page in family:
            source = page.read_text(encoding="utf-8")
            is_root = page.resolve() == root
            block = marked_block(source)
            if is_root and not bool(record.get("insert_link")):
                excluded_roots += 1
                if block:
                    errors.append({"page": str(page), "issue": "excluded root contains link marker"})
                continue
            if source.count(START) != 1 or source.count(END) != 1 or not block:
                errors.append({"page": str(page), "issue": "marker pair missing or duplicated"})
                continue
            body_at = source.find('<article class="content-body-card">')
            if source.find(START) > body_at or body_at < 0:
                errors.append({"page": str(page), "issue": "button is not immediately before content body"})
            href_match = re.search(r'<a href="([^"]+)"', block)
            href = html.unescape(href_match.group(1)) if href_match else ""
            if is_root:
                roots_external += 1
                if href != str(record.get("homepage", "")) or 'target="_blank"' not in block or "학교 공식 홈페이지" not in block:
                    errors.append({"page": str(page), "issue": "wrong official homepage root link"})
            else:
                details_internal += 1
                if href != str(record["root_url"]) or 'target="_blank"' in block or "학교정보는" not in block:
                    errors.append({"page": str(page), "issue": "wrong detail-to-root link"})

    css = (public / "static" / "css" / "site.css").read_text(encoding="utf-8")
    if css.count(CSS_START) != 1 or css.count(CSS_END) != 1:
        errors.append({"page": "static/css/site.css", "issue": "CSS marker pair missing or duplicated"})
    summary = {
        "passed": not errors,
        "schools": len(records),
        "familyPages": family_pages,
        "rootExternalLinks": roots_external,
        "rootExcluded": excluded_roots,
        "detailInternalLinks": details_internal,
        "errorCount": len(errors),
        "errors": errors[:100],
    }
    output = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
