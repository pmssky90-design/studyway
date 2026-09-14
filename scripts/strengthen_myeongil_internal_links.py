from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import quote, unquote


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
AREA = "강동구-명일동"


def url(kind: str, area: str = AREA) -> str:
    return "/region/" + quote(area) + "/" + quote(kind) + "/"


def page(kind: str, area: str = AREA) -> Path:
    return OUTPUT / "region" / area / kind / "index.html"


def add_links(kind: str, links: list[tuple[str, str]], area: str = AREA) -> None:
    path = page(kind, area)
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
        if href == url(kind, area) or href in seen:
            continue
        target = OUTPUT / unquote(href.strip("/")) / "index.html"
        if not target.is_file():
            raise RuntimeError(f"Broken related link: {href}")
        seen.add(href)
        unique.append((href, label))

    rendered = "".join(
        f'<a href="{href}">{html.escape(label)}</a>' for href, label in unique
    )
    updated = markup[: match.start()] + match.group(1) + rendered + match.group(3) + markup[match.end() :]
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    target = ("명일동고등수학과외", url("고등수학과외"))
    related = [
        ("명일동수학과외", url("수학과외")),
        ("명일동고등과외", url("고등과외")),
        ("명일동고1수학과외", url("고1수학과외")),
        ("명일동고2수학과외", url("고2수학과외")),
        ("명일동고3수학과외", url("고3수학과외")),
        ("강동구고등수학과외", url("고등수학과외", "강동구/all")),
    ]

    add_links("고등수학과외", related)
    for kind in ("수학과외", "고등과외", "고1수학과외", "고2수학과외", "고3수학과외"):
        add_links(kind, [target])
    add_links("고등수학과외", [target], "강동구/all")


if __name__ == "__main__":
    main()
