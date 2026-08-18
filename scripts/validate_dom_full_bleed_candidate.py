from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_images_mobile_full_bleed_real_chrome"
CANDIDATE = ROOT / "candidate_output_images_mobile_dom_full_bleed"
REPORT = ROOT / "reports" / "images-mobile-dom-full-bleed" / "dom-regression-audit.json"

SOURCE_RE = re.compile(r'<article>(?P<h1><h1>.*?</h1>)<div class="content-image-sequence".*?</div>(?P<body>.*?)</article>', re.DOTALL)
NEW_RE = re.compile(r'<div class="content-shell"><section class="content-heading-card">(?P<h1><h1>.*?</h1>)</section><div class="content-image-sequence".*?</div><article class="content-body-card">(?P<body>.*?)</article></div>', re.DOTALL)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
CANONICAL_RE = re.compile(r'<link rel="canonical" href="([^"]+)">')
HREF_RE = re.compile(r'<a\b[^>]*\bhref="([^"]*)"')


def one(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1) if match else None


def main() -> None:
    failures: dict[str, list[str]] = {k: [] for k in ("missing_wrapper", "body", "title", "h1", "canonical", "href")}
    content = region = school = 0
    for source_path in SOURCE.rglob("*.html"):
        relative = source_path.relative_to(SOURCE)
        source_text = source_path.read_text(encoding="utf-8")
        source_match = SOURCE_RE.search(source_text)
        if not source_match:
            continue
        content += 1
        if relative.parts[0] == "region": region += 1
        if relative.parts[0] == "school": school += 1
        new_text = (CANDIDATE / relative).read_text(encoding="utf-8")
        new_match = NEW_RE.search(new_text)
        key = relative.as_posix()
        if not new_match:
            failures["missing_wrapper"].append(key)
            continue
        if source_match.group("body") != new_match.group("body"): failures["body"].append(key)
        if one(TITLE_RE, source_text) != one(TITLE_RE, new_text): failures["title"].append(key)
        if source_match.group("h1") != new_match.group("h1"): failures["h1"].append(key)
        if one(CANONICAL_RE, source_text) != one(CANONICAL_RE, new_text): failures["canonical"].append(key)
        if HREF_RE.findall(source_text) != HREF_RE.findall(new_text): failures["href"].append(key)
    result = {
        "content_pages": content,
        "region_content": region,
        "school_content": school,
        "dom_wrappers_changed": content,
        "image_parent_after": ".content-shell",
        "heading_parent_after": ".content-shell",
        "body_parent_after": ".content-shell",
        "failures": {key: len(value) for key, value in failures.items()},
        "examples": {key: value[:3] for key, value in failures.items() if value},
        "pass": not any(failures.values()),
    }
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["pass"]: raise SystemExit(1)


if __name__ == "__main__": main()
