#!/usr/bin/env python3
"""Add an idempotent, H2-driven core table of contents to StudyWay pages."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path


START = "<!-- CORE_TOC_START -->"
END = "<!-- CORE_TOC_END -->"
CSS_START = "/* CORE_TOC_START */"
CSS_END = "/* CORE_TOC_END */"
ARTICLE_MARKER = '<article class="content-body-card">'
MAX_ITEMS = 7

H2_RE = re.compile(r"<h2(?P<attrs>[^>]*)>(?P<body>.*?)</h2>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
ID_RE = re.compile(r'\bid=["\']([^"\']+)["\']', re.I)

CSS = f"""{CSS_START}
.core-toc {{
  box-sizing: border-box;
  width: min(100% - 36px, 1040px);
  margin: 0 auto 22px;
  padding: 18px 20px;
  border: 1px solid #dbe8e3;
  border-radius: 16px;
  background: #f6fbf9;
}}
.core-toc__title {{ display: block; margin: 0 0 12px; color: #173f36; font-size: 1rem; }}
.core-toc ol {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 24px;
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: core-toc;
}}
.core-toc li {{ counter-increment: core-toc; min-width: 0; }}
.core-toc a {{
  display: flex;
  gap: 8px;
  align-items: flex-start;
  color: #285a4e;
  line-height: 1.5;
  text-decoration: none;
}}
.core-toc a::before {{ content: counter(core-toc, decimal-leading-zero); flex: 0 0 auto; color: #6b9087; font-size: .78rem; font-weight: 700; padding-top: .15rem; }}
.core-toc a:hover {{ color: #16705d; text-decoration: underline; text-underline-offset: 3px; }}
.core-toc a:focus-visible {{ outline: 3px solid rgba(37, 129, 110, .28); outline-offset: 3px; border-radius: 4px; }}
.content-body-card h2[id] {{ scroll-margin-top: 88px; }}
@media (max-width: 640px) {{
  .core-toc {{ width: calc(100% - 24px); margin-bottom: 18px; padding: 16px; border-radius: 14px; }}
  .core-toc ol {{ grid-template-columns: 1fr; gap: 7px; }}
}}
{CSS_END}"""


def plain_text(fragment: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", fragment)).split())


def replace_marked(source: str, start: str, end: str, replacement: str) -> tuple[str, bool]:
    start_at = source.find(start)
    if start_at < 0:
        return source, False
    end_at = source.find(end, start_at)
    if end_at < 0:
        raise ValueError(f"missing end marker: {end}")
    return source[:start_at] + replacement + source[end_at + len(end) :], True


def add_heading_ids(article: str) -> tuple[str, list[tuple[str, str]]]:
    headings: list[tuple[str, str]] = []
    used: set[str] = set(ID_RE.findall(article))

    def replace(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        body = match.group("body")
        label = plain_text(body)
        if not label:
            return match.group(0)
        existing = ID_RE.search(attrs)
        if existing:
            heading_id = existing.group(1)
        else:
            base = f"content-section-{len(headings) + 1}"
            heading_id = base
            suffix = 2
            while heading_id in used:
                heading_id = f"{base}-{suffix}"
                suffix += 1
            attrs = f'{attrs} id="{heading_id}"'
            used.add(heading_id)
        headings.append((heading_id, label))
        return f"<h2{attrs}>{body}</h2>"

    return H2_RE.sub(replace, article), headings


def toc_block(headings: list[tuple[str, str]]) -> str:
    items = "".join(
        f'<li><a href="#{html.escape(heading_id, quote=True)}">{html.escape(label)}</a></li>'
        for heading_id, label in headings[:MAX_ITEMS]
    )
    return (
        f'{START}<nav class="core-toc" aria-label="페이지 핵심 목차">'
        f'<strong class="core-toc__title">핵심 목차</strong><ol>{items}</ol>'
        f'</nav>{END}'
    )


def transform_page(source: str) -> tuple[str, str]:
    article_at = source.find(ARTICLE_MARKER)
    if article_at < 0:
        return source, "skipped_no_article"

    article = source[article_at:]
    updated_article, headings = add_heading_ids(article)
    if len(headings) < 2:
        return source, "skipped_few_headings"

    without_old, had_old = replace_marked(source[:article_at], START, END, "")
    updated = without_old + toc_block(headings) + updated_article
    return updated, "updated_existing" if had_old else "updated_new"


def ensure_css(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    updated, replaced = replace_marked(source, CSS_START, CSS_END, CSS)
    if not replaced:
        updated = source.rstrip() + "\n\n" + CSS + "\n"
    if updated == source:
        return False
    path.write_text(updated, encoding="utf-8", newline="")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("public", type=Path)
    args = parser.parse_args()
    public = args.public.resolve()

    counts: dict[str, int] = {}
    errors: list[dict[str, str]] = []
    for path in public.rglob("index.html"):
        try:
            source = path.read_text(encoding="utf-8")
            updated, status = transform_page(source)
            counts[status] = counts.get(status, 0) + 1
            if updated != source:
                path.write_text(updated, encoding="utf-8", newline="")
        except Exception as exc:  # noqa: BLE001
            errors.append({"file": str(path), "error": str(exc)})

    css_changed = ensure_css(public / "static" / "css" / "site.css")
    print(json.dumps({"public": str(public), "counts": counts, "css_changed": css_changed, "errors": errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
