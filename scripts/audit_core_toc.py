#!/usr/bin/env python3
"""Audit StudyWay core TOCs and heading anchors."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from add_core_toc import ARTICLE_MARKER, END, H2_RE, ID_RE, MAX_ITEMS, START


HREF_RE = re.compile(r'<a href="#([^"]+)">', re.I)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("public", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    public = args.public.resolve()

    eligible = 0
    toc_pages = 0
    skipped_few = 0
    errors: list[dict[str, str]] = []

    for path in public.rglob("index.html"):
        source = path.read_text(encoding="utf-8")
        article_at = source.find(ARTICLE_MARKER)
        if article_at < 0:
            continue
        h2s = list(H2_RE.finditer(source[article_at:]))
        if len(h2s) < 2:
            skipped_few += 1
            if START in source or END in source:
                errors.append({"file": str(path), "error": "TOC found on page with fewer than two H2 headings"})
            continue
        eligible += 1
        if source.count(START) != 1 or source.count(END) != 1:
            errors.append({"file": str(path), "error": "TOC marker count is not exactly one"})
            continue
        toc_pages += 1
        toc_start = source.find(START)
        toc_end = source.find(END, toc_start)
        if not (toc_start < article_at and toc_end < article_at):
            errors.append({"file": str(path), "error": "TOC is not immediately before content article"})
        hrefs = HREF_RE.findall(source[toc_start:toc_end])
        expected = min(len(h2s), MAX_ITEMS)
        if len(hrefs) != expected:
            errors.append({"file": str(path), "error": f"TOC item count {len(hrefs)} != {expected}"})
        article_ids = {match.group(1) for h2 in h2s for match in [ID_RE.search(h2.group("attrs"))] if match}
        missing = [target for target in hrefs if target not in article_ids]
        if missing:
            errors.append({"file": str(path), "error": f"missing heading targets: {missing}"})

    css = (public / "static" / "css" / "site.css").read_text(encoding="utf-8")
    if css.count("/* CORE_TOC_START */") != 1 or css.count("/* CORE_TOC_END */") != 1:
        errors.append({"file": "static/css/site.css", "error": "TOC CSS marker count is not exactly one"})

    report = {
        "passed": not errors,
        "eligiblePages": eligible,
        "tocPages": toc_pages,
        "skippedFewHeadings": skipped_few,
        "errorCount": len(errors),
        "errors": errors[:100],
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
