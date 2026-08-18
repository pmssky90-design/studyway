from __future__ import annotations

import csv
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(os.environ.get("STUDYWAY_OUTPUT", ROOT / "output"))
REPORTS = Path(os.environ.get("STUDYWAY_REPORTS", ROOT / "reports"))


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.h1=0; self.h1_text=[]; self.canonical=[]; self.title=[]; self.in_title=False; self.in_h1=False; self.noindex=False; self.anchor_texts=[]; self._anchor=[]; self.in_anchor=False; self.breadcrumb_text=[]; self._breadcrumb_depth=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag == "a":
            if attrs.get("href"): self.links.append(attrs["href"])
            self.in_anchor=True; self._anchor=[]
        if tag == "h1": self.h1 += 1; self.in_h1=True
        if tag == "title": self.in_title=True
        if tag == "nav" and "breadcrumbs" in attrs.get("class", "").split(): self._breadcrumb_depth=1
        elif self._breadcrumb_depth: self._breadcrumb_depth += 1
        if tag == "link" and attrs.get("rel") == "canonical": self.canonical.append(attrs.get("href", ""))
        if tag == "meta" and attrs.get("name") == "robots" and "noindex" in attrs.get("content", "").lower(): self.noindex=True
    def handle_endtag(self, tag):
        if tag == "title": self.in_title=False
        if tag == "h1": self.in_h1=False
        if tag == "a" and self.in_anchor:
            self.anchor_texts.append("".join(self._anchor).strip()); self.in_anchor=False
        if self._breadcrumb_depth:
            self._breadcrumb_depth -= 1
    def handle_data(self, data):
        if self.in_title: self.title.append(data)
        if self.in_h1: self.h1_text.append(data)
        if self.in_anchor: self._anchor.append(data)
        if self._breadcrumb_depth: self.breadcrumb_text.append(data)


def file_url(path: Path) -> str:
    rel=path.relative_to(OUTPUT).as_posix()
    if rel == "index.html": return "/"
    return "/" + "/".join(quote(part, safe="-._~") for part in rel.removesuffix("index.html").strip("/").split("/")) + "/"


def target_exists(href: str) -> bool:
    path=urlsplit(href).path
    if path.startswith("/static/"): return (OUTPUT / unquote(path.lstrip("/"))).is_file()
    if not path.endswith("/"): return (OUTPUT / unquote(path.lstrip("/"))).is_file()
    return (OUTPUT / unquote(path.lstrip("/")) / "index.html").is_file()


def main():
    pages={file_url(p):p for p in OUTPUT.rglob("index.html")}
    graph=defaultdict(set); broken=[]; h1_errors=[]; canonical_errors=[]; noindex=[]; titles=Counter(); link_counts={}
    marker="(학교)"
    school_prefix={"public_urls":[],"slugs":[],"titles":[],"h1":[],"canonicals":[],"breadcrumbs":[],"anchors":[],"html_anywhere":[]}
    for url,path in pages.items():
        parser=Parser(); parser.feed(path.read_text(encoding="utf-8"))
        if parser.h1 != 1: h1_errors.append({"url":url,"count":parser.h1})
        expected="https://studyway.kr"+url
        if parser.canonical != [expected]: canonical_errors.append({"url":url,"found":parser.canonical,"expected":expected})
        if parser.noindex: noindex.append(url)
        titles["".join(parser.title).strip()] += 1
        if marker in url: school_prefix["public_urls"].append(url)
        if marker in unquote(url): school_prefix["slugs"].append(url)
        if marker in "".join(parser.title): school_prefix["titles"].append(url)
        if marker in "".join(parser.h1_text): school_prefix["h1"].append(url)
        if any(marker in value for value in parser.canonical): school_prefix["canonicals"].append(url)
        if marker in "".join(parser.breadcrumb_text): school_prefix["breadcrumbs"].append(url)
        if any(marker in value for value in parser.anchor_texts): school_prefix["anchors"].append(url)
        if marker in path.read_text(encoding="utf-8"): school_prefix["html_anywhere"].append(url)
        internal=[]
        for href in parser.links:
            parsed=urlsplit(href)
            if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"): continue
            internal.append(parsed.path)
            if not target_exists(parsed.path): broken.append({"source":url,"target":parsed.path})
            if parsed.path in pages: graph[url].add(parsed.path)
        link_counts[url]=len(internal)
    depths={"/":0}; queue=deque(["/"])
    while queue:
        source=queue.popleft()
        for target in graph[source]:
            if target not in depths: depths[target]=depths[source]+1; queue.append(target)
    REPORTS.mkdir(parents=True, exist_ok=True)
    with (REPORTS/"url-plan.csv").open(encoding="utf-8-sig") as f: plan=list(csv.DictReader(f))
    urls=[r["url"] for r in plan]; canonicals=[r["canonical"] for r in plan]
    sitemap_hits=[]
    sitemap_urls=[]
    for sitemap in OUTPUT.glob("sitemap*.xml"):
        if marker in sitemap.read_text(encoding="utf-8"):
            sitemap_hits.append(sitemap.name)
        if sitemap.name != "sitemap-index.xml":
            sitemap_urls.extend(node.text for node in ET.parse(sitemap).getroot().iter() if node.tag.endswith("loc") and node.text)
    school_prefix["sitemaps"] = sitemap_hits
    school_prefix["url_plan_public_urls"] = [r["url"] for r in plan if marker in r["url"]]
    school_prefix["url_plan_slugs"] = [r["url"] for r in plan if marker in r["slug"]]
    school_prefix["url_plan_canonicals"] = [r["url"] for r in plan if marker in r["canonical"]]
    school_prefix_counts={key:len(value) for key,value in school_prefix.items()}
    report={
        "html_pages":len(pages), "planned_pages":len(plan), "page_count_match":len(pages)==len(plan),
        "duplicate_urls":len(urls)-len(set(urls)), "duplicate_canonicals":len(canonicals)-len(set(canonicals)),
        "broken_internal_links":len(broken), "broken_examples":broken[:20],
        "orphans":len(set(pages)-{"/"}-{t for targets in graph.values() for t in targets}),
        "unreachable":len(set(pages)-set(depths)), "depth_5_plus":sum(d>=5 for d in depths.values()),
        "depth_counts":{str(i):sum(d==i for d in depths.values()) for i in range(5)},
        "h1_errors":len(h1_errors), "canonical_errors":len(canonical_errors), "noindex":len(noindex),
        "duplicate_titles":sum(n-1 for title,n in titles.items() if title and n>1),
        "sitemap_missing":len({"https://studyway.kr"+url for url in urls}-set(sitemap_urls)),
        "sitemap_extra":len(set(sitemap_urls)-{"https://studyway.kr"+url for url in urls}),
        "sitemap_duplicates":len(sitemap_urls)-len(set(sitemap_urls)),
        "school_prefix_public_exposure":school_prefix_counts,
        "school_prefix_examples":{key:value[:20] for key,value in school_prefix.items() if value},
        "top_internal_link_pages":sorted(link_counts.items(),key=lambda x:x[1],reverse=True)[:50],
    }
    report["pass"] = all([report["page_count_match"],report["duplicate_urls"]==0,report["duplicate_canonicals"]==0,report["broken_internal_links"]==0,report["orphans"]==0,report["unreachable"]==0,report["depth_5_plus"]==0,report["h1_errors"]==0,report["canonical_errors"]==0,report["noindex"]==0,report["duplicate_titles"]==0,report["sitemap_missing"]==0,report["sitemap_extra"]==0,report["sitemap_duplicates"]==0,all(count==0 for count in school_prefix_counts.values())])
    (REPORTS/"validation-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == "__main__": main()
