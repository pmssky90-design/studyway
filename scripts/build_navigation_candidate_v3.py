from __future__ import annotations

import csv
import html
import importlib.util
import json
import re
import shutil
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parents[1]
V2_SCRIPT = ROOT / "scripts" / "build_navigation_candidate.py"
V2_OUTPUT = ROOT / "candidate_output_navigation_v2"
CANDIDATE = ROOT / "candidate_output_navigation_v3"
REPORTS = ROOT / "reports" / "navigation-v3"
BASE = "https://studyway.kr"

GROUPS = ("기본", "초등", "중등", "고등", "고1", "고2", "고3")


def group_for(sheet: str) -> str:
    name = sheet.removeprefix("(학교)")
    for group in ("고1", "고2", "고3"):
        if name.startswith(group):
            return group
    for group in ("초등", "중등", "고등"):
        if name.startswith(group):
            return group
    if name.startswith(("중1", "중2", "중3")):
        return "중등"
    return "기본"


def local_file(url: str) -> Path:
    if url == "/":
        return CANDIDATE / "index.html"
    return CANDIDATE / unquote(url.strip("/")) / "index.html"


def sections(rows: list[dict]) -> str:
    grouped = defaultdict(list)
    for row in rows:
        label = row["source_sheet"].removeprefix("(학교)")
        grouped[group_for(row["source_sheet"])].append((label, row["url"]))
    chunks = []
    for group in GROUPS:
        links = grouped.get(group)
        if not links:
            continue
        chunks.append(f'<section class="content-link-group"><h2>{group}</h2><div class="link-grid">')
        chunks.extend(f'<a href="{url}">{html.escape(label)}</a>' for label, url in links)
        chunks.append("</div></section>")
    return "".join(chunks)


def replace_article(path: Path, article: str) -> None:
    markup = path.read_text(encoding="utf-8")
    updated, count = re.subn(r"<article>.*?</article>", article, markup, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"article not found: {path}")
    path.write_text(updated, encoding="utf-8")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.canonical = ""; self.title = ""; self.h1 = ""; self._title = False; self._h1 = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical": self.canonical = attrs.get("href", "")
        if tag == "title": self._title = True
        if tag == "h1": self._h1 = True
    def handle_endtag(self, tag):
        if tag == "title": self._title = False
        if tag == "h1": self._h1 = False
    def handle_data(self, data):
        if self._title: self.title += data
        if self._h1: self.h1 += data


def main() -> None:
    if not V2_OUTPUT.exists():
        raise SystemExit("navigation-v2 candidate is missing")
    if CANDIDATE.exists():
        shutil.rmtree(CANDIDATE)
    shutil.copytree(V2_OUTPUT, CANDIDATE)
    REPORTS.mkdir(parents=True, exist_ok=True)

    with (ROOT / "reports" / "url-plan.csv").open(encoding="utf-8-sig") as f:
        old = list(csv.DictReader(f))
    region_content = [r for r in old if r["page_type"] == "region_content"]
    school_content = [r for r in old if r["page_type"] == "school_content"]
    entity_hubs = [r for r in old if r["page_type"] == "region_entity_hub"]
    school_hubs = [r for r in old if r["page_type"] == "school_hub"]
    city_hubs = [r for r in old if r["page_type"] == "region_city_hub"]

    by_region_hub = defaultdict(list)
    for row in region_content: by_region_hub[row["hub_url"]].append(row)
    by_school_hub = defaultdict(list)
    for row in school_content: by_school_hub[row["parent_url"]].append(row)

    # Candidate-only category hubs are removed. Existing content URLs are untouched.
    for category in CANDIDATE.glob("region/**/category"):
        if category.is_dir(): shutil.rmtree(category)

    # Every region entity hub directly exposes its real content, visually grouped.
    for hub in entity_hubs:
        rows = by_region_hub[hub["url"]]
        entity = hub["dong_eup_myeon"] or hub["district"]
        replace_article(local_file(hub["url"]), f"<article><h1>{html.escape(entity)} 과외</h1><p>{html.escape(entity)}에서 제공되는 실제 학습 콘텐츠를 선택하세요.</p>{sections(rows)}</article>")

    # A top district/city page also directly exposes content for that top area.
    entity_by_url = {r["url"]: r for r in entity_hubs}
    for city in city_hubs:
        path = local_file(city["url"])
        if not path.exists(): continue
        overall = next((h for h in entity_hubs if h["district"] == city["district"] and not h["dong_eup_myeon"]), None)
        if not overall or not by_region_hub[overall["url"]]: continue
        markup = path.read_text(encoding="utf-8")
        direct = f'<section class="top-region-content"><h2>{html.escape(city["district"])} 전체 콘텐츠</h2>{sections(by_region_hub[overall["url"]])}</section>'
        markup, count = re.subn(r"(<article>.*?<h1>.*?</h1>)", r"\1" + direct, markup, count=1, flags=re.S)
        if count != 1: raise RuntimeError(f"top region article not found: {path}")
        path.write_text(markup, encoding="utf-8")

    # School representative pages keep direct links, now split into visual groups.
    for hub in school_hubs:
        rows = by_school_hub[hub["url"]]
        replace_article(local_file(hub["url"]), f'<article><h1>{html.escape(hub["school_name"])} 과외</h1><p>{html.escape(hub["school_name"])}의 실제 학습 콘텐츠를 선택하세요.</p>{sections(rows)}</article>')

    # Recreate candidate sitemap and URL plan after category removal.
    for sitemap in CANDIDATE.glob("sitemap*.xml"): sitemap.unlink()
    pages = []
    for file in CANDIDATE.rglob("index.html"):
        rel = file.relative_to(CANDIDATE).as_posix()
        url = "/" if rel == "index.html" else "/" + "/".join(quote(p, safe="-._~") for p in rel.removesuffix("index.html").strip("/").split("/")) + "/"
        parser = PageParser(); parser.feed(file.read_text(encoding="utf-8"))
        pages.append({"url": url, "canonical": parser.canonical, "slug": url.rstrip("/").split("/")[-1] if url != "/" else "", "page_type": next((r["page_type"] for r in old if r["url"] == url), "navigation")})
    pages.sort(key=lambda p: p["url"])
    sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f'<url><loc>{html.escape(BASE + p["url"])}</loc></url>' for p in pages) + "</urlset>"
    (CANDIDATE / "sitemap-candidate.xml").write_text(sitemap, encoding="utf-8")
    (CANDIDATE / "sitemap-index.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://studyway.kr/sitemap-candidate.xml</loc></sitemap></sitemapindex>', encoding="utf-8")
    with (REPORTS / "url-plan.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "canonical", "slug", "page_type"]); writer.writeheader(); writer.writerows(pages)
    (REPORTS / "url-plan.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidate": str(CANDIDATE), "pages": len(pages), "region_content": len(region_content), "school_content": len(school_content)}, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
