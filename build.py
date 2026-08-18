from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).parent
SOURCE = next(path for path in ROOT.glob("*.xlsx") if ".backup-" not in path.name)
OUTPUT = ROOT / "output"
REPORTS = ROOT / "reports"
BASE = "https://studyway.kr"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN_NS}
MANAGEMENT = {"구조", "시트2", "학교페이지대상", "학교지역연결", "학교연결요약", "추가지역허브"}


def safe_slug(value: str) -> str:
    value = re.sub(r"\s+", "-", value.strip())
    value = re.sub(r"[^0-9A-Za-z가-힣._~-]", "-", value)
    return re.sub(r"-+", "-", value).strip("-").lower() or "item"


def url_path(*parts: str) -> str:
    return "/" + "/".join(quote(part, safe="-._~") for part in parts) + "/"


class Workbook:
    def __init__(self, path: Path):
        self.path = path
        self.book = zipfile.ZipFile(path)
        self.strings = self._strings()
        wb = ET.fromstring(self.book.read("xl/workbook.xml"))
        rels = ET.fromstring(self.book.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in rels.findall(f"{{{PKG_REL_NS}}}Relationship")}
        self.sheets = {}
        for sheet in wb.find(f"{{{MAIN_NS}}}sheets"):
            target = targets[sheet.attrib[f"{{{DOC_REL_NS}}}id"]].lstrip("/")
            self.sheets[sheet.attrib["name"]] = target if target.startswith("xl/") else "xl/" + target

    def _strings(self):
        try:
            source = self.book.open("xl/sharedStrings.xml")
        except KeyError:
            return []
        values = []
        for _, elem in ET.iterparse(source, events=("end",)):
            if elem.tag.endswith("}si"):
                values.append("".join(n.text or "" for n in elem.iter() if n.tag.endswith("}t")))
                elem.clear()
        return values

    def rows(self, name: str):
        with self.book.open(self.sheets[name]) as source:
            for _, elem in ET.iterparse(source, events=("end",)):
                if not elem.tag.endswith("}row"):
                    continue
                row = {}
                for cell in elem.findall("m:c", NS):
                    match = re.match(r"[A-Z]+", cell.attrib.get("r", "A1"))
                    col = 0
                    for letter in match.group(0):
                        col = col * 26 + ord(letter) - 64
                    kind = cell.attrib.get("t")
                    value = cell.find("m:v", NS)
                    if kind == "inlineStr":
                        text = "".join(n.text or "" for n in cell.iter() if n.tag.endswith("}t"))
                    else:
                        text = "" if value is None or value.text is None else value.text
                        if kind == "s" and text:
                            text = self.strings[int(text)]
                    if text != "":
                        row[col] = text
                yield int(elem.attrib.get("r", 0)), row
                elem.clear()


def content_rows(book: Workbook, sheet: str, school=False):
    for row_num, row in book.rows(sheet):
        if school and row_num == 1:
            continue
        entity = row.get(1, "").strip()
        title = row.get(2, "").strip()
        bodies = [v for c, v in row.items() if c >= 3 and ("<p" in v.lower() or "<h" in v.lower())]
        body = max(bodies, key=len, default="")
        if entity and title and body:
            yield row_num, entity, title, body


def table_rows(book: Workbook, sheet: str):
    iterator = iter(book.rows(sheet))
    _, header_row = next(iterator)
    headers = {col: value.strip() for col, value in header_row.items()}
    for row_num, row in iterator:
        yield row_num, {headers[col]: value.strip() for col, value in row.items() if col in headers}


def description(body: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:155]


def layout(title: str, h1: str, canonical: str, breadcrumbs, body: str, links=()):
    base_title = re.sub(r"\s*\|\s*StudyWay\s*$", "", title).strip()
    route_tail = unquote(urlsplit(canonical).path.rstrip("/").split("/")[-1]) if urlsplit(canonical).path != "/" else ""
    qualifier_parts = [label for label, _ in breadcrumbs[1:-1]]
    if route_tail and route_tail not in qualifier_parts:
        qualifier_parts.append(route_tail)
    qualifier = " · ".join(qualifier_parts)
    document_title = f"{base_title}{' | ' + qualifier if qualifier else ''} | StudyWay"
    crumb_html = "<ol>" + "".join(f'<li><a href="{href}">{html.escape(label)}</a></li>' for label, href in breadcrumbs[:-1]) + f"<li>{html.escape(breadcrumbs[-1][0])}</li></ol>"
    crumb_json = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": i, "name": label, "item": BASE + href} for i, (label, href) in enumerate(breadcrumbs, 1)]}
    related = ""
    if links:
        related = '<aside class="related"><h2>관련 페이지</h2><div class="link-grid">' + "".join(f'<a href="{href}">{html.escape(label)}</a>' for label, href in links) + "</div></aside>"
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(document_title)}</title><meta name="description" content="{html.escape(description(body or h1))}"><meta name="robots" content="index,follow"><link rel="canonical" href="{canonical}"><link rel="stylesheet" href="/static/css/site.css"><script type="application/ld+json">{json.dumps(crumb_json, ensure_ascii=False)}</script></head><body><header><a class="brand" href="/">StudyWay</a><nav><a href="/region/">지역별 과외</a><a href="/school/">학교별 과외</a></nav></header><main><nav class="breadcrumbs" aria-label="현재 위치">{crumb_html}</nav><article><h1>{html.escape(h1)}</h1>{body}</article>{related}</main><footer><p>StudyWay · 서울·경기 과외 학습정보</p></footer></body></html>'''


def write_page(path: str, markup: str):
    target = OUTPUT / unquote(path.strip("/")) / "index.html" if path != "/" else OUTPUT / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markup, encoding="utf-8")


def build():
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(); REPORTS.mkdir(exist_ok=True)
    book = Workbook(SOURCE)
    structure = []
    for _, row in book.rows("구조"):
        values = [row.get(i, "").strip() for i in range(1, 5)]
        if any(values): structure.append(values)
    parent_for = {}
    province_for = {}
    city_members = defaultdict(list)
    explicit_cities = set()
    for province, _, city, local in structure:
        if city:
            province_for[city] = province
            explicit_cities.add(city)
        if local and local != city:
            parent_for[local] = city
            province_for[local] = province
            city_members[city].append(local)
    additions = list(table_rows(book, "추가지역허브"))
    for _, row in additions:
        city = row.get("필요시군구허브", "")
        if city: province_for[city] = row.get("시도", "경기")

    region_sheets = [s for s in book.sheets if s not in MANAGEMENT and not s.startswith("(학교)")]
    school_sheets = [s for s in book.sheets if s.startswith("(학교)")]
    regions = defaultdict(dict)
    source_rows = {}
    bad_cells = []
    for sheet in region_sheets:
        for row_num, entity, title, body in content_rows(book, sheet):
            regions[entity][sheet] = (title, body)
            source_rows[(entity, sheet)] = row_num
    for sheet in school_sheets:
        for row_num, row in book.rows(sheet):
            for value in row.values():
                if value in {"#ERROR!", "#NAME?", "#REF!", "#VALUE!"}:
                    bad_cells.append({"sheet": sheet, "row": row_num, "value": value})

    schools_meta = {}
    meta_by_row = {}
    for row_num, row in table_rows(book, "학교페이지대상"):
        if not row.get("학교명"): continue
        uid = row.get("KEDI코드") or f"row-{row_num}"
        schools_meta[uid] = row
        meta_by_row[row_num] = uid
    school_links = {}
    for _, row in table_rows(book, "학교지역연결"):
        school_links[row.get("KEDI코드", "")] = row
    schools = defaultdict(dict)
    for sheet in school_sheets:
        kind = sheet.removeprefix("(학교)")
        for row_num, entity, title, body in content_rows(book, sheet, school=True):
            uid = meta_by_row.get(row_num)
            if uid:
                schools[uid][kind] = (title, body, row_num)

    region_slug = {}
    for entity in regions:
        parent = parent_for.get(entity, "")
        region_slug[entity] = safe_slug(f"{parent}-{entity}" if parent else entity)
    school_slug = {uid: safe_slug(f"{uid}-{meta.get('학교명','')}") for uid, meta in schools_meta.items()}
    plan = []
    graph = defaultdict(set)
    index_urls = {"/"}

    def add_link(source, target): graph[source].add(target)
    def add_plan(**row): plan.append(row); index_urls.add(row["url"])

    # Homepage and finder hubs
    home_links = [("지역별 과외 찾기", "/region/"), ("학교별 과외 찾기", "/school/")]
    write_page("/", layout("StudyWay | 서울·경기 과외 학습정보", "서울·경기 과외 학습정보", BASE + "/", [("홈", "/")], "<p>지역과 학교를 기준으로 필요한 과외 학습정보를 찾을 수 있습니다.</p>", home_links))
    for _, href in home_links: add_link("/", href)
    add_plan(page_type="home", source_sheet="", source_row="", entity_type="core", region="", district="", city="", dong_eup_myeon="", school_name="", school_unique_name="", subject="", grade="", slug="", url="/", parent_url="", hub_url="/", canonical=BASE+"/", click_depth=0)

    cities = sorted(explicit_cities | {e for e in regions if not parent_for.get(e)})
    city_links = [(city, url_path("region", region_slug.get(city, safe_slug(city)))) for city in cities if city]
    write_page("/region/", layout("지역별 과외 찾기 | StudyWay", "지역별 과외 찾기", BASE+"/region/", [("홈","/"),("지역별 과외","/region/")], "<p>서울과 경기의 구·시·군을 선택하세요.</p>", city_links))
    add_link("/", "/region/")
    for _, href in city_links: add_link("/region/", href)
    add_plan(page_type="region_finder", source_sheet="", source_row="", entity_type="hub", region="", district="", city="", dong_eup_myeon="", school_name="", school_unique_name="", subject="", grade="", slug="region", url="/region/", parent_url="/", hub_url="/region/", canonical=BASE+"/region/", click_depth=1)

    for city, city_url in city_links:
        members = sorted(set(city_members.get(city, [])))
        entity_links = []
        if city in regions:
            entity_links.append((f"{city} 전체", city_url + "all/"))
        entity_links += [(local, url_path("region", region_slug[local])) for local in members if local in regions]
        if not entity_links and city in regions:
            entity_links = [(f"{city} 콘텐츠", city_url + "all/")]
        write_page(city_url, layout(f"{city} 과외 학습정보 | StudyWay", f"{city} 과외", BASE+city_url, [("홈","/"),("지역별 과외","/region/"),(city,city_url)], f"<p>{html.escape(city)}의 지역별 과외 학습정보입니다.</p>", entity_links))
        for _, href in entity_links: add_link(city_url, href)
        add_plan(page_type="region_city_hub", source_sheet="구조", source_row="", entity_type="region_hub", region=province_for.get(city,""), district=city, city=city, dong_eup_myeon="", school_name="", school_unique_name="", subject="", grade="", slug=city_url.strip('/').split('/')[-1], url=city_url, parent_url="/region/", hub_url=city_url, canonical=BASE+city_url, click_depth=2)
        targets = list(dict.fromkeys(([city] if city in regions else []) + [m for m in members if m in regions]))
        for entity in targets:
            hub = city_url + "all/" if entity == city else url_path("region", region_slug[entity])
            content_links = [(regions[entity][kind][0], hub + quote(safe_slug(kind), safe="-._~") + "/") for kind in region_sheets if kind in regions[entity]]
            crumbs=[("홈","/"),("지역별 과외","/region/"),(city,city_url),(entity,hub)]
            write_page(hub, layout(f"{entity} 과외 학습정보 | StudyWay", f"{entity} 과외", BASE+hub, crumbs, f"<p>{html.escape(entity)}에서 제공되는 과외 유형을 선택하세요.</p>", content_links))
            add_link(city_url, hub)
            for _, href in content_links: add_link(hub, href)
            add_plan(page_type="region_entity_hub", source_sheet="구조", source_row="", entity_type="region", region=province_for.get(entity,""), district=city, city=city, dong_eup_myeon=entity if entity != city else "", school_name="", school_unique_name="", subject="", grade="", slug=region_slug[entity], url=hub, parent_url=city_url, hub_url=hub, canonical=BASE+hub, click_depth=3)
            for kind in region_sheets:
                if kind not in regions[entity]: continue
                title, body = regions[entity][kind]
                path = hub + quote(safe_slug(kind), safe="-._~") + "/"
                related = [(regions[entity][k][0], hub + quote(safe_slug(k), safe="-._~") + "/") for k in region_sheets if k in regions[entity] and k != kind][:8]
                write_page(path, layout(title, title.strip(), BASE+path, crumbs+[(title,path)], body, [(entity,hub)]+related))
                add_link(hub,path); add_link(path,hub)
                for _, href in related: add_link(path,href)
                add_plan(page_type="region_content", source_sheet=kind, source_row=source_rows[(entity,kind)], entity_type="region", region=province_for.get(entity,""), district=city, city=city, dong_eup_myeon=entity if entity != city else "", school_name="", school_unique_name="", subject="수학" if "수학" in kind else "영어" if "영어" in kind else "", grade=re.sub(r"[^초중고0-9]","",kind), slug=safe_slug(kind), url=path, parent_url=hub, hub_url=hub, canonical=BASE+path, click_depth=4)

    groups = defaultdict(list)
    for uid, meta in schools_meta.items():
        link = school_links.get(uid, {})
        group = link.get("최종연결지역명") or meta.get("시군구") or "기타"
        groups[group].append(uid)
    group_links = [(group, url_path("school", "area-"+safe_slug(group))) for group in sorted(groups)]
    write_page("/school/", layout("학교별 과외 찾기 | StudyWay", "학교별 과외 찾기", BASE+"/school/", [("홈","/"),("학교별 과외","/school/")], "<p>학교가 위치한 지역을 선택하세요.</p>", group_links))
    add_link("/", "/school/")
    for _, href in group_links: add_link("/school/",href)
    add_plan(page_type="school_finder", source_sheet="", source_row="", entity_type="hub", region="", district="", city="", dong_eup_myeon="", school_name="", school_unique_name="", subject="", grade="", slug="school", url="/school/", parent_url="/", hub_url="/school/", canonical=BASE+"/school/", click_depth=1)
    for group, group_url in group_links:
        links=[(schools_meta[uid].get("학교명",uid),url_path("school",school_slug[uid])) for uid in sorted(groups[group], key=lambda item: schools_meta[item].get("학교명",""))]
        write_page(group_url, layout(f"{group} 학교별 과외 | StudyWay", f"{group} 학교 찾기", BASE+group_url, [("홈","/"),("학교별 과외","/school/"),(group,group_url)], f"<p>{html.escape(group)}의 학교를 선택하세요.</p>", links))
        for _, href in links: add_link(group_url,href)
        add_plan(page_type="school_group_hub", source_sheet="학교지역연결", source_row="", entity_type="school_group", region="", district=group, city=group, dong_eup_myeon="", school_name="", school_unique_name="", subject="", grade="", slug=group_url.strip('/').split('/')[-1], url=group_url, parent_url="/school/", hub_url=group_url, canonical=BASE+group_url, click_depth=2)
        for uid in sorted(groups[group], key=lambda item: schools_meta[item].get("학교명","")):
            meta=schools_meta[uid]; name=meta.get("학교명",uid); school_url=url_path("school",school_slug[uid])
            content_links=[(schools[uid][kind][0],school_url+quote(safe_slug(kind),safe="-._~")+"/") for kind in (sheet.removeprefix("(학교)") for sheet in school_sheets) if kind in schools[uid]]
            crumbs=[("홈","/"),("학교별 과외","/school/"),(group,group_url),(name,school_url)]
            info=f'<p>{html.escape(meta.get("주소", ""))}</p>'
            write_page(school_url, layout(f"{name} 과외 학습정보 | StudyWay", f"{name} 과외", BASE+school_url, crumbs, info, content_links))
            add_link(group_url,school_url)
            for _, href in content_links: add_link(school_url,href)
            add_plan(page_type="school_hub", source_sheet="학교페이지대상", source_row=meta.get("원본행",""), entity_type="school", region=meta.get("시도",""), district=meta.get("시군구",""), city=meta.get("시군구",""), dong_eup_myeon=meta.get("주소상동읍면",""), school_name=name, school_unique_name=meta.get("페이지고유기준명",name), subject="", grade="", slug=school_slug[uid], url=school_url, parent_url=group_url, hub_url=school_url, canonical=BASE+school_url, click_depth=3)
            for kind, (title, body, row_num) in schools[uid].items():
                path=school_url+quote(safe_slug(kind),safe="-._~")+"/"
                related=[(schools[uid][k][0],school_url+quote(safe_slug(k),safe="-._~")+"/") for k in schools[uid] if k != kind][:8]
                write_page(path,layout(title,title.strip(),BASE+path,crumbs+[(title,path)],body,[(name,school_url)]+related))
                add_link(school_url,path); add_link(path,school_url)
                for _,href in related: add_link(path,href)
                add_plan(page_type="school_content", source_sheet="(학교)"+kind, source_row=row_num, entity_type="school", region=meta.get("시도",""), district=meta.get("시군구",""), city=meta.get("시군구",""), dong_eup_myeon=meta.get("주소상동읍면",""), school_name=name, school_unique_name=meta.get("페이지고유기준명",name), subject="수학" if "수학" in kind else "영어" if "영어" in kind else "", grade=re.sub(r"[^고0-9]","",kind), slug=safe_slug(kind), url=path, parent_url=school_url, hub_url=school_url, canonical=BASE+path, click_depth=4)

    css=(ROOT/"static/css/site.css").read_text(encoding="utf-8")
    (OUTPUT/"static/css").mkdir(parents=True); (OUTPUT/"static/css/site.css").write_text(css,encoding="utf-8")
    (OUTPUT/"robots.txt").write_text("User-agent: *\nAllow: /\n\nSitemap: https://studyway.kr/sitemap-index.xml\n",encoding="utf-8")
    content_urls=[p["url"] for p in plan]
    sitemap_groups=defaultdict(list)
    for p in plan: sitemap_groups[p["page_type"]].append(p["url"])
    sitemap_files=[]
    for kind, urls in sitemap_groups.items():
        filename=f"sitemap-{safe_slug(kind)}.xml"; sitemap_files.append(filename)
        xml='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{html.escape(BASE+u)}</loc></url>' for u in urls)+'</urlset>'
        (OUTPUT/filename).write_text(xml,encoding="utf-8")
    index='<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<sitemap><loc>{BASE}/{f}</loc></sitemap>' for f in sitemap_files)+'</sitemapindex>'
    (OUTPUT/"sitemap-index.xml").write_text(index,encoding="utf-8")
    fields=list(plan[0])
    with (REPORTS/"url-plan.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(plan)
    (REPORTS/"url-plan.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8")
    # BFS over the generated logical link graph.
    depths={"/":0}; queue=deque(["/"])
    while queue:
        source=queue.popleft()
        for target in graph[source]:
            if target in index_urls and target not in depths:
                depths[target]=depths[source]+1; queue.append(target)
    depth_counts={str(i):sum(d==i for d in depths.values()) for i in range(5)}
    backup = next(ROOT.glob("*.backup-before-c196-c301.xlsx"), None)
    source_digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    source_modified = bool(backup and source_digest != hashlib.sha256(backup.read_bytes()).hexdigest())
    summary={"source":SOURCE.name,"sha256":source_digest,"source_modified":source_modified,"sheet_count":len(book.sheets),"content_sheets":len(region_sheets)+len(school_sheets),"region_entities":len(regions),"schools":len(schools_meta),"region_content_pages":sum(1 for p in plan if p['page_type']=='region_content'),"school_content_pages":sum(1 for p in plan if p['page_type']=='school_content'),"html_pages":len(plan),"duplicate_urls":len(plan)-len({p['url'] for p in plan}),"duplicate_canonicals":len(plan)-len({p['canonical'] for p in plan}),"depth_counts":depth_counts,"depth_5_plus":sum(d>=5 for d in depths.values()),"unreachable":len(index_urls-set(depths)),"sitemaps":len(sitemap_files),"sitemap_urls":len(content_urls),"data_errors":bad_cells}
    (REPORTS/"build-report.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__": build()
