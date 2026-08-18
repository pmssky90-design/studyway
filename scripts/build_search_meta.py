from __future__ import annotations

import csv, hashlib, html, json, re, shutil
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT=Path(__file__).resolve().parents[1];REPORTS=ROOT/"reports"
SOURCE=ROOT/"candidate_output_clean_without_reviews";OUTPUT=ROOT/"candidate_output_search_meta"
PLAN=REPORTS/"clean-without-reviews-validation/url-plan.csv"
BEFORE=REPORTS/"search-meta-before-audit.json";AFTER=REPORTS/"search-meta-after-audit.json"
SAMPLE=REPORTS/"search-meta-sample-100.csv";INSPECTOR=ROOT/"search_meta_inspector"
FIELDS=("title","description","robots","canonical","og:title","og:description","og:type","og:url","og:image","twitter:card","twitter:title","twitter:description","twitter:image","BreadcrumbList")

def attrs(tag):return {k.lower():html.unescape(v) for k,v in re.findall(r'([:\w-]+)=["\'](.*?)["\']',tag,re.S)}
def extract(text):
    head=text.split("</head>",1)[0];data=defaultdict(list)
    data["title"]=[html.unescape(x.strip()) for x in re.findall(r"<title>(.*?)</title>",head,re.S|re.I)]
    for tag in re.findall(r"<meta\b[^>]*>",head,re.I):
        a=attrs(tag);name=a.get("name") or a.get("property")
        if name:data[name].append(a.get("content",""))
    for tag in re.findall(r"<link\b[^>]*>",head,re.I):
        a=attrs(tag)
        if a.get("rel","").lower()=="canonical":data["canonical"].append(a.get("href",""))
    crumbs=[];json_errors=0;forbidden=[]
    for raw in re.findall(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',head,re.S|re.I):
        try:
            value=json.loads(html.unescape(raw));values=value if isinstance(value,list) else [value]
            for obj in values:
                typ=obj.get("@type") if isinstance(obj,dict) else None
                if typ=="BreadcrumbList":crumbs.append(obj)
                if typ in ("Review","AggregateRating","FAQPage"):forbidden.append(typ)
                blob=json.dumps(obj,ensure_ascii=False)
                for term in ("ratingValue","reviewCount","bestRating","worstRating"):
                    if term in blob:forbidden.append(term)
        except Exception:json_errors+=1
    data["BreadcrumbList"]=crumbs
    return data,json_errors,forbidden

def html_breadcrumb(text,canonical):
    m=re.search(r'<nav class="breadcrumbs"[^>]*>\s*<ol>(.*?)</ol>\s*</nav>',text,re.S|re.I)
    if not m:return []
    result=[]
    for li in re.findall(r"<li>(.*?)</li>",m.group(1),re.S|re.I):
        link=re.search(r'<a[^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>',li,re.S|re.I)
        if link:
            href=html.unescape(link.group(1));url="https://studyway.kr"+href if href.startswith("/") else href
            result.append((html.unescape(re.sub(r"<[^>]+>","",link.group(2))).strip(),url))
        else:result.append((html.unescape(re.sub(r"<[^>]+>","",li)).strip(),canonical))
    return result

def audit(root,rows):
    counts={k:{"present":0,"missing":0,"duplicate_pages":0,"empty":0} for k in FIELDS};mismatch=Counter();parse_errors=0;forbidden=Counter();school_prefix=Counter();image_assets=0;bad_images=0;breadcrumb_broken=0;records=[]
    for row in rows:
        path=unquote(urlsplit(row["url"]).path.strip("/"))+"/index.html";text=(root/path).read_text(encoding="utf-8");d,err,bad=extract(text);parse_errors+=err;forbidden.update(bad)
        for field in FIELDS:
            values=d.get(field,[]);counts[field]["present"]+=bool(values);counts[field]["missing"]+=not values;counts[field]["duplicate_pages"]+=len(values)>1;counts[field]["empty"]+=bool(values) and (not values[0] if field!="BreadcrumbList" else False)
            if any("(학교)" in str(v) for v in values):school_prefix[field]+=1
        one=lambda k:d.get(k,[""])[0] if d.get(k) else ""
        mismatch["og_title"]+=bool(one("og:title")) and one("og:title")!=one("title")
        mismatch["twitter_title"]+=bool(one("twitter:title")) and one("twitter:title")!=one("title")
        mismatch["og_description"]+=bool(one("og:description")) and one("og:description")!=one("description")
        mismatch["twitter_description"]+=bool(one("twitter:description")) and one("twitter:description")!=one("description")
        mismatch["og_url"]+=bool(one("og:url")) and one("og:url")!=one("canonical")
        mismatch["twitter_image"]+=bool(one("twitter:image")) and one("twitter:image")!=one("og:image")
        mismatch["og_type"]+=bool(one("og:type")) and one("og:type")!="article"
        mismatch["twitter_card"]+=bool(one("twitter:card")) and one("twitter:card")!="summary_large_image"
        image=one("og:image")
        if image:
            rel=unquote(urlsplit(image).path.lstrip("/"));image_assets+=not(root/rel).is_file();bad_images+=not re.fullmatch(r"https://studyway\.kr/assets/images/search-thumbnails/(0[1-9]|1[0-3])\.png",image)
        actual=html_breadcrumb(text,one("canonical"));crumb=d.get("BreadcrumbList",[])
        if crumb:
            items=crumb[0].get("itemListElement",[]);structured=[(str(x.get("name","")),str(x.get("item","")),x.get("position")) for x in items]
            expected=[(name,url,i+1) for i,(name,url) in enumerate(actual)]
            mismatch["breadcrumb_html"]+=structured!=expected
            for _,url,_ in structured:
                if url.startswith("https://studyway.kr/"):
                    rel=unquote(urlsplit(url).path.strip("/"));target=root/(rel+"/index.html" if rel else "index.html");breadcrumb_broken+=not target.is_file()
        records.append({"path":path,"url":row["url"],"page_type":row["page_type"],**{k:one(k) for k in FIELDS if k!="BreadcrumbList"},"breadcrumb":actual})
    return {"content_pages":len(rows),"fields":counts,"mismatch":dict(mismatch),"html_parse_errors":0,"json_ld_parse_errors":parse_errors,"forbidden_schema":dict(forbidden),"school_prefix":dict(school_prefix),"og_image_asset_errors":image_assets,"og_image_not_allowed":bad_images,"breadcrumb_broken":breadcrumb_broken},records

def add_meta(text,d):
    one=lambda k:d.get(k,[""])[0] if d.get(k) else "";title=one("title");desc=one("description");canonical=one("canonical");image=one("og:image")
    wanted=[("property","og:title",title),("property","og:description",desc),("property","og:type","article"),("property","og:url",canonical),("name","twitter:card","summary_large_image"),("name","twitter:title",title),("name","twitter:description",desc),("name","twitter:image",image)]
    tags=[]
    for attr,name,value in wanted:
        if not d.get(name) and value:tags.append(f'<meta {attr}="{name}" content="{html.escape(value,quote=True)}">')
    return text.replace("</head>","".join(tags)+"</head>",1)

def make_sample(records):
    strata=defaultdict(list)
    for r in records:
        title=r["title"];kind="school" if r["page_type"]=="school_content" else "region";province="서울" if re.search(r"/school/11|강남구|강동구|강북구|강서구|관악구|광진구|구로구|금천구|노원구|도봉구|동대문|동작구|마포구|서대문|서초구|성동구|성북구|송파구|양천구|영등포|용산구|은평구|종로구|중구|중랑구",unquote(r["url"])) else "경기";subject="수학" if "수학" in title else "영어" if "영어" in title else "일반";grade=next((x for x in ("초등","중등","고등","고1","고2","고3") if x in title),"기본");strata[(province,kind,subject,grade)].append(r)
    for values in strata.values():values.sort(key=lambda x:hashlib.sha256(x["url"].encode()).hexdigest())
    sample=[]
    while len(sample)<100:
        moved=False
        for k in sorted(strata):
            if strata[k] and len(sample)<100:sample.append(strata[k].pop());moved=True
        if not moved:break
    fields=["url","title","description","canonical","og:title","og:description","og:type","og:url","og:image","twitter:card","twitter:title","twitter:description","twitter:image"]
    with SAMPLE.open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k] for k in fields} for r in sample)

def make_inspector(records):
    INSPECTOR.mkdir(exist_ok=True);data=[{k:r[k] for k in ("url","title","description","canonical","og:title","og:description","og:type","og:url","og:image","twitter:card","twitter:title","twitter:description","twitter:image","breadcrumb")} for r in records]
    (INSPECTOR/"data.json").write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
    page='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>StudyWay 검색 메타 검사기</title><style>body{font-family:system-ui;margin:0;background:#f3f6fa;color:#172033}main{max-width:1100px;margin:auto;padding:28px}input{width:100%;box-sizing:border-box;padding:14px;border:1px solid #b9c4d6;border-radius:10px;font-size:16px}.result{margin-top:16px;display:grid;gap:16px}.item,.share{background:#fff;border:1px solid #d9e1ec;border-radius:14px;padding:18px}.share{display:grid;grid-template-columns:180px 1fr;gap:16px}.share img{width:180px;height:180px;object-fit:cover;border-radius:10px}.meta{font-size:13px;word-break:break-all}.pass{color:#087b43;font-weight:800}@media(max-width:600px){.share{grid-template-columns:1fr}.share img{width:100%;height:auto}}</style></head><body><main><h1>StudyWay 검색 메타 검사기</h1><input id="q" placeholder="지역명 / 학교명 / title / URL"><p id="count"></p><div id="out" class="result"></div></main><script>let rows=[];fetch('data.json').then(r=>r.json()).then(x=>{rows=x;draw('')});q.oninput=()=>draw(q.value);function e(s){return String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}function draw(v){let z=rows.filter(x=>(x.title+' '+x.url+' '+x.canonical).toLowerCase().includes(v.toLowerCase())).slice(0,50);count.textContent=`${z.length}개 표시 / 전체 ${rows.length}`;out.innerHTML=z.map(x=>{let ok=x.title==x['og:title']&&x.title==x['twitter:title']&&x.description==x['og:description']&&x.description==x['twitter:description']&&x.canonical==x['og:url']&&x['og:image']==x['twitter:image'];let img=x['og:image'].replace('https://studyway.kr','http://127.0.0.1:8771');return `<article class=item><div class=share><img src="${e(img)}"><div><h2>${e(x.title)}</h2><p>${e(x.description)}</p><strong>studyway.kr</strong></div></div><p class="${ok?'pass':''}">${ok?'PASS':'ERROR'}</p><div class=meta>${Object.entries(x).filter(([k])=>k!='breadcrumb').map(([k,v])=>`<p><b>${e(k)}</b>: ${e(v)}</p>`).join('')}<p><b>Breadcrumb</b>: ${e(x.breadcrumb.map(b=>b[0]).join(' › '))}</p></div></article>`}).join('')}</script></body></html>'''.replace(".join('')}</script>",".join('')}</script>" if False else ".join('')}</script>")
    (INSPECTOR/"index.html").write_text(page,encoding="utf-8")

def main():
    with PLAN.open(encoding="utf-8-sig",newline="") as f:rows=[r for r in csv.DictReader(f) if r["page_type"] in ("region_content","school_content")]
    before,records=audit(SOURCE,rows);BEFORE.write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding="utf-8")
    if OUTPUT.exists():shutil.rmtree(OUTPUT)
    shutil.copytree(SOURCE,OUTPUT)
    for row in rows:
        path=unquote(urlsplit(row["url"]).path.strip("/"))+"/index.html";target=OUTPUT/path;text=target.read_text(encoding="utf-8");d,_,_=extract(text);target.write_text(add_meta(text,d),encoding="utf-8")
    after,records=audit(OUTPUT,rows);body_changes=0
    for file in SOURCE.rglob("*.html"):
        rel=file.relative_to(SOURCE);a=file.read_text(encoding="utf-8");b=(OUTPUT/rel).read_text(encoding="utf-8");body_changes+=a.split("<body>",1)[1]!=b.split("<body>",1)[1]
    after["body_changes_all_html"]=body_changes;AFTER.write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding="utf-8");make_sample(records);make_inspector(records)
    print(json.dumps({"before":before,"after":after,"output":str(OUTPUT),"inspector":str(INSPECTOR)},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
