from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from urllib.parse import quote, unquote


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"


def url(area: str, kind: str) -> str:
    return "/region/" + quote(area) + "/" + quote(kind) + "/"


def page(area: str, kind: str) -> Path:
    return OUTPUT / "region" / area / kind / "index.html"


def add_links(area: str, kind: str, links: list[tuple[str, str]]) -> None:
    path = page(area, kind)
    markup = path.read_text(encoding="utf-8")
    match = re.search(
        r'(<section class="related-navigation bidirectional-links"><h2[^>]*>이 지역의 관련 학습</h2><div class="link-grid">)(.*?)(</div></section>)',
        markup,
        re.S,
    )
    if not match:
        raise RuntimeError(f"Related-links section not found: {path}")

    existing = re.findall(r'<a href="([^"]+)">(.*?)</a>', match.group(2), re.S)
    combined = existing + [(href, label) for label, href in links]
    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href, label in combined:
        if href == url(area, kind) or href in seen:
            continue
        target = OUTPUT / unquote(href.strip("/")) / "index.html"
        if not target.is_file():
            raise RuntimeError(f"Broken related link: {href}")
        seen.add(href)
        unique.append((href, label))

    rendered = "".join(
        f'<a href="{href}">{html.escape(label)}</a>' for href, label in unique
    )
    updated = (
        markup[: match.start()]
        + match.group(1)
        + rendered
        + match.group(3)
        + markup[match.end() :]
    )
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", required=True)
    parser.add_argument("--district", required=True)
    parser.add_argument("--neighborhood", required=True)
    parser.add_argument("--level", required=True)
    parser.add_argument("--subject", required=True)
    args = parser.parse_args()

    target_kind = f"{args.level}{args.subject}과외"
    target = (f"{args.neighborhood}{target_kind}", url(args.area, target_kind))
    grade_prefix = {"중등": "중", "고등": "고"}.get(args.level, args.level)
    sibling_kinds = [
        f"{args.subject}과외",
        f"{args.level}과외",
        f"{grade_prefix}1{args.subject}과외",
        f"{grade_prefix}2{args.subject}과외",
        f"{grade_prefix}3{args.subject}과외",
    ]
    related = [
        (f"{args.neighborhood}{kind}", url(args.area, kind))
        for kind in sibling_kinds
    ]
    district_area = f"{args.district}/all"
    related.append(
        (f"{args.district}{target_kind}", url(district_area, target_kind))
    )

    add_links(args.area, target_kind, related)
    for kind in sibling_kinds:
        add_links(args.area, kind, [target])
    add_links(district_area, target_kind, [target])


if __name__ == "__main__":
    main()
