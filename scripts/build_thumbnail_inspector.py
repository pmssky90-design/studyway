from __future__ import annotations

import html
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_images_mobile_dom_full_bleed_aligned_cards"
OUT = ROOT / "reports" / "thumbnail-preview"
PRODUCTION = ROOT / "reports" / "thumbnail-production-check.txt"

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
H1_RE = re.compile(r"<h1>(.*?)</h1>", re.S)
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]+)">')
OG_IMAGE_RE = re.compile(r'<meta property="og:image" content="([^"]+)">')
OG_TITLE_RE = re.compile(r'<meta property="og:title" content="([^"]+)">')
TWITTER_RE = re.compile(r'<meta name="twitter:image" content="([^"]+)">')

SEOUL = {
    "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구", "노원구",
    "도봉구", "동대문", "동작구", "마포구", "서대문구", "서초구", "성동구", "성북구", "송파구",
    "양천구", "영등포", "용산구", "은평구", "종로구", "중구", "중랑구",
}


def one(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return html.unescape(match.group(1)) if match else ""


def content_type(slug: str) -> str:
    for prefix, label in (("초등", "초등"), ("중등", "중등"), ("고등", "고등"), ("고1", "고1"), ("고2", "고2"), ("고3", "고3")):
        if slug.startswith(prefix): return label
    return {"과외": "기본", "영어과외": "영어", "수학과외": "수학"}.get(slug, "기타")


def province(kind: str, parts: list[str]) -> str:
    if kind == "school": return "서울" if parts[1].startswith("11") else "경기"
    return "서울" if unquote(parts[1]) in SEOUL else "경기"


def main() -> None:
    if OUT.exists(): shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    records=[]; counters=Counter(); errors=[]
    allowed={f"https://studyway.kr/assets/images/search-thumbnails/{i:02}.png" for i in range(1,14)}
    for path in SOURCE.rglob("*.html"):
        text=path.read_text(encoding="utf-8")
        if 'class="content-image-sequence"' not in text: continue
        rel=path.relative_to(SOURCE).as_posix(); parts=rel.split("/"); kind=parts[0]
        title=one(TITLE_RE,text); h1=re.sub(r"<[^>]+>","",one(H1_RE,text)); canonical=one(CANON_RE,text)
        ogs=OG_IMAGE_RE.findall(text); tws=TWITTER_RE.findall(text); og_titles=OG_TITLE_RE.findall(text)
        og=html.unescape(ogs[0]) if len(ogs)==1 else ""; twitter=html.unescape(tws[0]) if len(tws)==1 else ""
        public_path=urlsplit(canonical).path if canonical else ""
        slug=unquote(public_path.rstrip("/").split("/")[-1]) if public_path else ""
        thumb=og.rsplit("/",1)[-1] if og else ""
        local_asset=SOURCE / "assets" / "images" / "search-thumbnails" / thumb
        status=[]
        if len(ogs)!=1: status.append(f"og:image count={len(ogs)}")
        if og not in allowed: status.append("허용되지 않은 og:image")
        if not og.startswith("https://studyway.kr/"): status.append("비정상 URL")
        if not local_asset.is_file(): status.append("asset 누락")
        if len(tws)!=1 or twitter!=og: status.append("twitter 불일치")
        counters[thumb]+=1
        record={"title":title,"h1":h1,"url":public_path,"canonical":canonical,"ogTitle":html.unescape(og_titles[0]) if len(og_titles)==1 else "","ogImage":og,"twitterImage":twitter,"thumbnail":thumb,"kind":kind,"province":province(kind,parts),"type":content_type(slug),"status":"PASS" if not status else "FAIL","errors":status}
        records.append(record)
        if status: errors.append({"path":public_path,"errors":status})
    records.sort(key=lambda x:x["url"])

    inventory=json.loads((ROOT/"reports"/"images"/"image-inventory.json").read_text(encoding="utf-8"))
    thumbnails=[]
    for item in inventory["thumbnails"]:
        thumb=Path(item["asset"]).name
        shutil.copy2(SOURCE/"assets"/"images"/"search-thumbnails"/thumb,OUT/"assets"/thumb)
        thumbnails.append({"name":thumb,"width":item["width"],"height":item["height"],"bytes":item["bytes"],"sha256":item["sha256"],"usage":counters[thumb],"broken":item["broken"]})
    audit={"total":len(records),"normal":sum(r["status"]=="PASS" for r in records),"errors":len(errors),"og_missing":sum(not r["ogImage"] for r in records),"og_duplicate_meta":sum(len(r["errors"])>0 and any("count=" in e for e in r["errors"]) for r in records),"invalid_url":sum("비정상 URL" in r["errors"] for r in records),"asset_missing":sum("asset 누락" in r["errors"] for r in records),"not_allowed":sum("허용되지 않은 og:image" in r["errors"] for r in records),"twitter_mismatch":sum("twitter 불일치" in r["errors"] for r in records),"thumbnail_count":len(thumbnails)}
    data={"audit":audit,"thumbnails":thumbnails,"records":records,"errors":errors,"localSite":"http://127.0.0.1:8906"}
    (OUT/"data.json").write_text(json.dumps(data,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    (OUT/"audit.json").write_text(
        json.dumps(
            {
                "audit": audit,
                "usage": dict(sorted(counters.items())),
                "thumbnails": thumbnails,
                "production_urls": 20,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    shutil.copy2(ROOT/"scripts"/"thumbnail_inspector.html",OUT/"index.html")

    selected=[]
    for p,k in (("서울","region"),("경기","region"),("서울","school"),("경기","school")):
        selected.extend([r for r in records if r["province"]==p and r["kind"]==k][:5])
    lines=["StudyWay thumbnail production check","",f"검사용 URL: {len(selected)}","구성: 서울 지역 5 / 경기 지역 5 / 서울 학교 5 / 경기 학교 5",""]
    for r in selected: lines.extend([r["canonical"],f"예상: {r['thumbnail']}",""])
    PRODUCTION.write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps({"audit":audit,"usage":dict(sorted(counters.items())),"production_urls":len(selected),"output":str(OUT)},ensure_ascii=False,indent=2))


if __name__=="__main__": main()
