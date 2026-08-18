from __future__ import annotations

import csv
import html
import json
import shutil
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build

SOURCE_OUTPUT = ROOT / "output"
CANDIDATE = ROOT / "candidate_output_navigation_v2"
REPORTS = ROOT / "reports" / "navigation-v2"
BASE = "https://studyway.kr"
CATEGORIES = {
    "basic": ("기본", {"과외", "영어과외", "수학과외"}),
    "elementary": ("초등", {"초등과외", "초등영어과외", "초등수학과외"}),
    "middle": ("중등", {"중등과외", "중등영어과외", "중등수학과외", "중1과외", "중2과외", "중3과외", "중1영어과외", "중2영어과외", "중3영어과외", "중1수학과외", "중2수학과외", "중3수학과외"}),
    "high": ("고등", {"고등과외", "고등영어과외", "고등수학과외", "고1과외", "고2과외", "고3과외", "고1영어과외", "고2영어과외", "고3영어과외", "고1수학과외", "고2수학과외", "고3수학과외"}),
}


def local_file(url: str) -> Path:
    return CANDIDATE / unquote(url.strip("/")) / "index.html" if url != "/" else CANDIDATE / "index.html"


def write(url: str, markup: str) -> None:
    target = local_file(url); target.parent.mkdir(parents=True, exist_ok=True); target.write_text(markup, encoding="utf-8")


def card_sections(sections):
    chunks=[]
    for heading, links in sections:
        if not links: continue
        chunks.append(f"<h2>{html.escape(heading)}</h2><div class=\"link-grid\">"+"".join(f'<a href="{url}">{html.escape(label)}</a>' for label,url in links)+"</div>")
    return "".join(chunks)


class MetaParser(HTMLParser):
    def __init__(self): super().__init__(); self.canonical=""; self.title=""; self._title=False
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=="link" and attrs.get("rel")=="canonical": self.canonical=attrs.get("href","")
        if tag=="title": self._title=True
    def handle_endtag(self, tag):
        if tag=="title": self._title=False
    def handle_data(self, data):
        if self._title:self.title+=data


def main():
    if CANDIDATE.exists(): shutil.rmtree(CANDIDATE)
    shutil.copytree(SOURCE_OUTPUT, CANDIDATE)
    REPORTS.mkdir(parents=True, exist_ok=True)
    with (ROOT/"reports/url-plan.csv").open(encoding="utf-8-sig") as f: old=list(csv.DictReader(f))
    region_content=[r for r in old if r["page_type"]=="region_content"]
    entity_hubs=[r for r in old if r["page_type"]=="region_entity_hub"]
    city_hubs={r["district"]:r for r in old if r["page_type"]=="region_city_hub"}
    school_hubs=[r for r in old if r["page_type"]=="school_hub"]
    content_by_hub=defaultdict(list)
    for row in region_content: content_by_hub[row["hub_url"]].append(row)

    book=build.Workbook(build.SOURCE)
    hierarchy=[]; top_for_local={}; group_for_local={}; top_regions=set(); province_for_top={}
    for _,row in book.rows("구조"):
        province,top,group,local=[row.get(i,"").strip() for i in range(1,5)]
        if not group: continue
        actual_top=top or group
        top_regions.add(actual_top); province_for_top[actual_top]=province
        if local:
            top_for_local[local]=actual_top; group_for_local[local]=group
        hierarchy.append((province,actual_top,group,local))
    for _,row in build.table_rows(book,"추가지역허브"):
        name=row.get("필요시군구허브","")
        if name: top_regions.add(name); province_for_top[name]=row.get("시도","경기도")

    # Remove old 297 fine-grained school grouping hubs; school/content pages remain byte-identical.
    for row in [r for r in old if r["page_type"]=="school_group_hub"]:
        path=local_file(row["url"]).parent
        if path.exists(): shutil.rmtree(path)

    new_rows=[]
    def register(url,page_type): new_rows.append({"url":url,"page_type":page_type})

    # HOME: direct top-level region access, no Seoul/Gyeonggi click layer.
    seoul=[]; gyeonggi=[]
    for name in sorted(top_regions):
        hub=city_hubs.get(name)
        if not hub: continue
        pair=(name,hub["url"])
        (seoul if "서울" in province_for_top.get(name,"") else gyeonggi).append(pair)
    body="<p>서울과 경기의 구·시·군 또는 학교를 기준으로 과외 학습정보를 찾을 수 있습니다.</p>"+card_sections([("서울",seoul),("경기",gyeonggi),("학교",[("학교별 과외 찾기","/school/")])])
    write("/",build.layout("StudyWay | 서울·경기 과외 학습정보","서울·경기 과외 학습정보",BASE+"/",[("홈","/")],body))
    register("/","home")

    # Auxiliary /region/ remains, but it is no longer required to reach content.
    all_top=seoul+gyeonggi
    auxiliary=[(name,row["url"]) for name,row in sorted(city_hubs.items()) if name not in top_regions]
    write("/region/",build.layout("지역별 과외 찾기 | StudyWay","지역별 과외 찾기",BASE+"/region/",[("홈","/"),("지역별 과외","/region/")],"<p>구·시·군을 선택하세요.</p>"+card_sections([("서울",seoul),("경기",gyeonggi),("보조 구 탐색",auxiliary)])))
    register("/region/","region_finder")

    entity_by_name={}
    for hub in entity_hubs:
        name=hub["dong_eup_myeon"] or hub["district"]
        entity_by_name[(hub["district"],name)]=hub
    for top in sorted(top_regions):
        city=city_hubs.get(top)
        if not city: continue
        groups=defaultdict(list)
        # top-wide entity hub, where Excel has top-level content.
        overall=next((h for h in entity_hubs if not h["dong_eup_myeon"] and h["district"]==top),None)
        if overall: groups["전체"].append((f"{top} 전체",overall["url"]))
        district_groups={group for _,actual_top,group,_ in hierarchy if actual_top==top and group!=top}
        for group in sorted(district_groups):
            district_overall=next((h for h in entity_hubs if not h["dong_eup_myeon"] and h["district"]==group),None)
            if district_overall: groups[group].append((f"{group} 전체",district_overall["url"]))
        for province,actual_top,group,local in hierarchy:
            if actual_top!=top or not local: continue
            hub=next((h for h in entity_hubs if h["dong_eup_myeon"]==local and h["district"]==group),None)
            if hub: groups[group].append((local,hub["url"]))
        sections=[(group,sorted(links)) for group,links in sorted(groups.items())]
        body=f"<p>{html.escape(top)}의 전체 지역과 세부 생활권을 선택하세요.</p>"+card_sections(sections)
        write(city["url"],build.layout(f"{top} 과외 학습정보 | StudyWay",f"{top} 과외",BASE+city["url"],[("홈","/"),(top,city["url"])],body))
        register(city["url"],"region_top_hub")

    # Entity hubs now expose only four category hubs.
    for hub in entity_hubs:
        entity=hub["dong_eup_myeon"] or hub["district"]
        top=top_for_local.get(entity,hub["district"])
        top_url=city_hubs.get(top,{}).get("url","/")
        category_links=[]
        for key,(label,types) in CATEGORIES.items():
            matching=[r for r in content_by_hub[hub["url"]] if r["source_sheet"] in types]
            if not matching: continue
            cat_url=hub["url"]+"category/"+key+"/"
            category_links.append((label,cat_url))
            links=[(r["source_sheet"],r["url"]) for r in sorted(matching,key=lambda x:x["source_sheet"])]
            crumbs=[("홈","/"),(top,top_url),(entity,hub["url"]),(label,cat_url)]
            write(cat_url,build.layout(f"{entity} {label} 과외 분류 | StudyWay",f"{entity} {label} 과외",BASE+cat_url,crumbs,"<p>실제 제공되는 학습 유형을 선택하세요.</p>"+card_sections([(label,links)])))
            register(cat_url,"region_category_hub")
        crumbs=[("홈","/"),(top,top_url),(entity,hub["url"])]
        write(hub["url"],build.layout(f"{entity} 과외 학습정보 | StudyWay",f"{entity} 과외",BASE+hub["url"],crumbs,"<p>학습 분류를 선택하세요.</p>"+card_sections([("학습분류",category_links)])))
        register(hub["url"],"region_entity_hub")

    # School finder: top-level district/city only.
    school_meta={}
    for _,row in build.table_rows(book,"학교페이지대상"):
        if row.get("KEDI코드"):school_meta[row["KEDI코드"]]=row
    schools_by_top=defaultdict(list)
    school_top_for_code={}
    for hub in school_hubs:
        code=hub["slug"].split("-",1)[0]; meta=school_meta.get(code,{})
        if meta.get("시도")=="서울": top=meta.get("주소상구") or meta.get("시군구")
        else:
            top=(meta.get("시군구") or "").removesuffix("시")
        schools_by_top[top].append((hub,meta))
        school_top_for_code[code]=top
    top_school_links=[]
    for top,items in sorted(schools_by_top.items()):
        if not top: continue
        url="/school/area-top-"+quote(build.safe_slug(top),safe="-._~")+"/";top_school_links.append((top,url))
        groups=defaultdict(list)
        for hub,meta in items:
            group=meta.get("주소상구") or meta.get("주소상동읍면") or top
            groups[group].append((hub["school_name"],hub["url"]))
        body=f"<p>{html.escape(top)}의 학교를 선택하세요.</p>"+card_sections([(g,sorted(v)) for g,v in sorted(groups.items())])
        write(url,build.layout(f"{top} 학교별 과외 | StudyWay",f"{top} 학교 찾기",BASE+url,[("홈","/"),("학교별 과외","/school/"),(top,url)],body))
        register(url,"school_top_hub")
    write("/school/",build.layout("학교별 과외 찾기 | StudyWay","학교별 과외 찾기",BASE+"/school/",[("홈","/"),("학교별 과외","/school/")],"<p>학교가 위치한 상위 구·시·군을 선택하세요.</p>"+card_sections([("상위 지역",top_school_links)])))
    register("/school/","school_finder")

    # Point existing school hub/content breadcrumbs at the new top-level school hubs.
    top_school_url={label:url for label,url in top_school_links}
    school_content_rows=[r for r in old if r["page_type"]=="school_content"]
    content_for_school=defaultdict(list)
    for row in school_content_rows: content_for_school[row["parent_url"]].append(row)
    for hub in school_hubs:
        code=hub["slug"].split("-",1)[0]; new_parent=top_school_url[school_top_for_code[code]]; old_parent=hub["parent_url"]
        for url in [hub["url"]]+[row["url"] for row in content_for_school[hub["url"]]]:
            target=local_file(url); markup=target.read_text(encoding="utf-8").replace(f'href="{old_parent}"',f'href="{new_parent}"')
            target.write_text(markup,encoding="utf-8")

    # Keep original school representative pages and all content pages.
    for row in old:
        if row["page_type"] in {"region_content","school_content","school_hub"}: register(row["url"],row["page_type"])
    # Keep auxiliary legacy region city hubs not used as top regions, reachable from /region/.
    for name,row in city_hubs.items():
        if name not in top_regions: register(row["url"],"legacy_region_hub")

    # Remove sitemap files and recreate from candidate pages. Content URL membership is unchanged.
    for sitemap in CANDIDATE.glob("sitemap*.xml"): sitemap.unlink()
    pages=[]
    for file in CANDIDATE.rglob("index.html"):
        rel=file.relative_to(CANDIDATE).as_posix(); url="/" if rel=="index.html" else "/"+"/".join(quote(p,safe="-._~") for p in rel.removesuffix("index.html").strip("/").split("/"))+"/"
        parser=MetaParser();parser.feed(file.read_text(encoding="utf-8"));pages.append({"url":url,"canonical":parser.canonical,"slug":url.rstrip("/").split("/")[-1] if url!="/" else "","page_type":next((r["page_type"] for r in new_rows if r["url"]==url),"navigation")})
    sitemap='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{html.escape(BASE+p["url"])}</loc></url>' for p in pages)+'</urlset>'
    (CANDIDATE/"sitemap-candidate.xml").write_text(sitemap,encoding="utf-8")
    (CANDIDATE/"sitemap-index.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://studyway.kr/sitemap-candidate.xml</loc></sitemap></sitemapindex>',encoding="utf-8")
    (CANDIDATE/"robots.txt").write_text("User-agent: *\nAllow: /\n\nSitemap: https://studyway.kr/sitemap-index.xml\n",encoding="utf-8")
    with (REPORTS/"url-plan.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["url","canonical","slug","page_type"]);w.writeheader();w.writerows(pages)
    (REPORTS/"url-plan.json").write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"candidate":str(CANDIDATE),"pages":len(pages),"content_pages":len(region_content)+sum(1 for r in old if r['page_type']=='school_content'),"new_navigation_pages":sum(1 for p in pages if p['page_type'] not in {'region_content','school_content','school_hub'})},ensure_ascii=False,indent=2))


if __name__=="__main__": main()
