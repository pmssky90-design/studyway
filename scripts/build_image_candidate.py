from __future__ import annotations

import csv, hashlib, json, re, shutil, struct
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_navigation_v4_bidirectional_home_return"
OUT = ROOT / "candidate_output_images"
REPORTS = ROOT / "reports" / "images"
THUMB_SOURCE = Path(r"C:\PROJECTS\이미지\썸네일")
CONTENT_SOURCE = Path(r"C:\PROJECTS\이미지\본문이미지")
BASE = "https://studyway.kr"


def natural_key(path: Path):
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", path.name)]


def png_size(path: Path):
    with path.open("rb") as f:
        header = f.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("invalid PNG")
    return struct.unpack(">II", header[16:24])


def inspect(paths):
    rows = []
    for path in paths:
        try:
            width, height = png_size(path); broken = False
        except Exception:
            width = height = None; broken = True
        rows.append({"name": path.name, "extension": path.suffix.lower(), "width": width, "height": height, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "broken": broken})
    hashes = Counter(row["sha256"] for row in rows)
    for row in rows: row["duplicate_suspected"] = hashes[row["sha256"]] > 1
    return rows


def file_for(url):
    return OUT / unquote(url.strip("/")) / "index.html"


def main():
    thumbs = sorted([p for p in THUMB_SOURCE.iterdir() if p.is_file()], key=natural_key)
    content_images = sorted([p for p in CONTENT_SOURCE.iterdir() if p.is_file()], key=natural_key)
    thumb_info = inspect(thumbs); content_info = inspect(content_images)
    if any(r["broken"] for r in thumb_info + content_info): raise RuntimeError("broken source image")
    if OUT.exists(): shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT); REPORTS.mkdir(parents=True, exist_ok=True)
    thumb_out = OUT / "assets" / "images" / "search-thumbnails"; thumb_out.mkdir(parents=True)
    content_out = OUT / "assets" / "images" / "content"; content_out.mkdir(parents=True)
    thumb_assets=[]; content_assets=[]
    for i,(source,info) in enumerate(zip(thumbs,thumb_info),1):
        name=f"{i:02d}{source.suffix.lower()}";shutil.copy2(source,thumb_out/name);thumb_assets.append({**info,"asset":f"/assets/images/search-thumbnails/{name}"})
    for i,(source,info) in enumerate(zip(content_images,content_info),1):
        name=f"{i:02d}{source.suffix.lower()}";shutil.copy2(source,content_out/name);content_assets.append({**info,"asset":f"/assets/images/content/{name}"})

    with (ROOT/"reports/url-plan.csv").open(encoding="utf-8-sig") as f: plan=list(csv.DictReader(f))
    pages=[r for r in plan if r["page_type"] in {"region_content","school_content"}]
    sequence=[]
    for i,img in enumerate(content_assets):
        attrs=f'src="{img["asset"]}" width="{img["width"]}" height="{img["height"]}" alt="과외 학습 안내 이미지 {i+1}"'
        attrs += ' loading="eager" fetchpriority="high" decoding="async"' if i==0 else ' loading="lazy" decoding="async"'
        sequence.append(f'<img {attrs}>')
    sequence_html='<div class="content-image-sequence" aria-label="과외 학습 안내 이미지">'+''.join(sequence)+'</div>'
    usage=Counter()
    for row in pages:
        path=file_for(row["url"]);markup=path.read_text(encoding="utf-8");canonical=row["canonical"]
        index=int.from_bytes(hashlib.sha256(canonical.encode("utf-8")).digest()[:8],"big")%len(thumb_assets);thumb=thumb_assets[index];usage[thumb["asset"]]+=1
        absolute=BASE+thumb["asset"]
        metadata=(f'<meta property="og:image" content="{absolute}"><meta property="og:image:width" content="{thumb["width"]}">'
                  f'<meta property="og:image:height" content="{thumb["height"]}"><meta name="twitter:image" content="{absolute}">')
        markup=markup.replace("</head>",metadata+"</head>",1)
        article=re.search(r"<article>.*?</article>",markup,re.S)
        if not article:raise RuntimeError(f"article missing: {row['url']}")
        replaced,count=re.subn(r"(<article>\s*<h1>.*?</h1>)",r"\1"+sequence_html,article.group(),count=1,flags=re.S)
        if count!=1:raise RuntimeError(f"H1 placement failed: {row['url']}")
        markup=markup[:article.start()]+replaced+markup[article.end():];path.write_text(markup,encoding="utf-8")
    css_path=OUT/"static/css/site.css"
    css_path.write_text(css_path.read_text(encoding="utf-8")+'\n.content-image-sequence{width:100%;max-width:100%;margin:.9rem auto 1.5rem;padding:0;overflow:visible}.content-image-sequence img{display:block;width:100%;max-width:100%;height:auto;object-fit:contain;margin:0 auto;padding:0}\n',encoding="utf-8")
    inventory={"thumbnail_source":str(THUMB_SOURCE),"content_source":str(CONTENT_SOURCE),"thumbnails":thumb_assets,"content_images":content_assets,"content_order":[p.name for p in content_images],"thumbnail_usage":dict(sorted(usage.items()))}
    (REPORTS/"image-inventory.json").write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding="utf-8")
    source_reports=ROOT/"reports/navigation-v4-bidirectional-home-return"
    for name in ("url-plan.csv","url-plan.json","relationship-plan.json","relationship-audit.json"):
        shutil.copy2(source_reports/name,REPORTS/name)
    print(json.dumps({"pages":len(pages),"thumbnails":len(thumbs),"content_images":len(content_images),"usage":usage},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
