from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote


START = "<!-- SCHOOL_OFFICIAL_HOMEPAGE_START -->"
END = "<!-- SCHOOL_OFFICIAL_HOMEPAGE_END -->"
CSS_START = "/* SCHOOL_OFFICIAL_HOMEPAGE_START */"
CSS_END = "/* SCHOOL_OFFICIAL_HOMEPAGE_END */"

CSS = f"""{CSS_START}
.school-page-reference {{
  margin: 0 auto;
  padding: 0 18px 22px;
  max-width: 1040px;
}}
.school-page-reference a {{
  box-sizing: border-box;
  display: flex;
  width: 100%;
  min-height: 52px;
  align-items: center;
  justify-content: center;
  padding: 13px 18px;
  border: 1px solid rgba(24, 91, 78, .28);
  border-radius: 14px;
  background: #eef8f4;
  color: #155a4c;
  font-weight: 800;
  line-height: 1.4;
  text-align: center;
  text-decoration: none;
}}
.school-page-reference a:hover {{ border-color: #25816e; background: #e4f4ee; }}
.school-page-reference a:focus-visible {{ outline: 3px solid rgba(37, 129, 110, .28); outline-offset: 3px; }}
@media (max-width: 640px) {{
  .school-page-reference {{ padding: 0 12px 18px; }}
  .school-page-reference a {{ min-height: 50px; padding: 12px 14px; }}
}}
{CSS_END}"""


def replace_marked(source: str, start: str, end: str, replacement: str) -> tuple[str, bool]:
    start_at = source.find(start)
    if start_at < 0:
        return source, False
    end_at = source.find(end, start_at)
    if end_at < 0:
        raise ValueError(f"missing end marker {end}")
    return source[:start_at] + replacement + source[end_at + len(end) :], True


def load_records(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("records list missing")
    return [item for item in records if isinstance(item, dict)]


def markup(record: dict[str, object], root_page: bool) -> str:
    school = str(record["school_name"]).strip()
    if root_page:
        homepage = str(record.get("homepage", "")).strip()
        if not homepage.startswith(("http://", "https://")):
            raise ValueError(f"invalid official homepage for {school}: {homepage}")
        href = homepage
        label = '학교 공식 홈페이지 <span aria-hidden="true">↗</span>'
        aria = f"{school} 공식 홈페이지 새 창 열림"
        attrs = ' target="_blank" rel="noopener noreferrer external"'
        css_class = "school-official-homepage"
    else:
        href = str(record["root_url"])
        label = f'학교정보는 {html.escape(school)} 과외 페이지에서 확인하세요 <span aria-hidden="true">→</span>'
        aria = f"{school} 과외 학교정보 페이지로 이동"
        attrs = ""
        css_class = "school-parent-page-link"
    return (
        f'{START}<nav class="school-page-reference {css_class}" aria-label="{html.escape(school, quote=True)} 학교정보 안내">'
        f'<a href="{html.escape(href, quote=True)}"{attrs} aria-label="{html.escape(aria, quote=True)}">{label}</a>'
        f'</nav>{END}'
    )


def insert_markup(source: str, block: str) -> str:
    updated, replaced = replace_marked(source, START, END, block)
    if replaced:
        return updated
    marker = '<article class="content-body-card">'
    at = source.find(marker)
    if at < 0:
        raise ValueError("content-body-card marker missing")
    return source[:at] + block + source[at:]


def page_path(public: Path, url: str) -> Path:
    return public / unquote(url.strip("/")) / "index.html"


def school_family(public: Path, record: dict[str, object]) -> list[Path]:
    root = page_path(public, str(record["root_url"]))
    school_dir = root.parent.parent
    if not school_dir.is_dir():
        return []
    return sorted(school_dir.glob("*/index.html"))


def ensure_css(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    updated, replaced = replace_marked(source, CSS_START, CSS_END, CSS)
    if not replaced:
        updated = source.rstrip() + "\n\n" + CSS + "\n"
    if updated == source:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply official-homepage and parent-school links to StudyWay school pages.")
    parser.add_argument("public", type=Path)
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "studyway_school_homepages.json")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--school-key", action="append", default=[])
    args = parser.parse_args()
    if args.all == bool(args.school_key):
        raise ValueError("choose --all or one or more --school-key values")

    records = load_records(args.data.resolve())
    selected = records if args.all else [item for item in records if item.get("school_key") in set(args.school_key)]
    public = args.public.resolve()
    counts: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    css_changed = ensure_css(public / "static" / "css" / "site.css")
    for record in selected:
        pages = school_family(public, record)
        root = page_path(public, str(record["root_url"]))
        if not pages:
            errors.append({"school_key": str(record.get("school_key", "")), "issue": "school family missing"})
            continue
        for page in pages:
            root_page = page.resolve() == root.resolve()
            if root_page and not bool(record.get("insert_link")):
                counts["root_skipped"] += 1
                continue
            try:
                source = page.read_text(encoding="utf-8")
                updated = insert_markup(source, markup(record, root_page))
                if updated != source:
                    page.write_text(updated, encoding="utf-8")
                    counts["root_updated" if root_page else "detail_updated"] += 1
                else:
                    counts["unchanged"] += 1
            except Exception as exc:
                errors.append({"page": str(page), "issue": str(exc)})
    result = {"public": str(public), "schools": len(selected), "counts": dict(counts), "css_changed": css_changed, "errors": errors[:100]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
