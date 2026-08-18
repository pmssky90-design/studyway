from pathlib import Path
from html.parser import HTMLParser
from collections import Counter
from urllib.parse import urlsplit, unquote
import csv, json, re, struct

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_mobile_contact_cta_emphasis"
OUTPUT = ROOT / "candidate_output_search_meta_final"
REPORT = ROOT / "reports" / "search-meta-final"
REPORT.mkdir(parents=True, exist_ok=True)

EXACT_KEYS = [
    "title", "description", "canonical", "og:title", "og:description", "og:url",
    "og:type", "og:image", "twitter:card", "twitter:title", "twitter:description", "twitter:image",
]
FORBIDDEN_RATING = ["Review", "AggregateRating", "ratingValue", "reviewCount", "bestRating", "worstRating", 'itemprop="rating"', "data-rating"]


class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_parts = []
        self.meta = []
        self.links = []
        self.in_json = False
        self.json_buf = []
        self.jsonld = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "title": self.in_title = True
        elif tag == "meta": self.meta.append(d)
        elif tag == "link": self.links.append(d)
        elif tag == "script" and d.get("type") == "application/ld+json": self.in_json = True; self.json_buf = []

    def handle_endtag(self, tag):
        if tag == "title": self.in_title = False
        elif tag == "script" and self.in_json:
            self.jsonld.append("".join(self.json_buf)); self.in_json = False

    def handle_data(self, data):
        if self.in_title: self.title_parts.append(data)
        if self.in_json: self.json_buf.append(data)

    def values(self, key):
        if key == "title": return ["".join(self.title_parts).strip()] if self.title_parts else []
        if key == "canonical": return [x.get("href", "") for x in self.links if x.get("rel") == "canonical"]
        attr = "property" if key.startswith("og:") else "name"
        return [x.get("content", "") for x in self.meta if x.get(attr) == key]


def png_size(path):
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n": return None
    return struct.unpack(">II", data[16:24])


def is_prod_absolute(url):
    p = urlsplit(url)
    return p.scheme == "https" and p.netloc == "studyway.kr" and not url.startswith(("file:", "/"))


def main():
    pages = sorted(OUTPUT.rglob("index.html"))
    errors = Counter(); og_images = Counter(); breadcrumb_ok = 0; breadcrumb_error = 0
    forbidden = Counter(); structured_types = Counter(); structured_keys = Counter(); preserved_errors = Counter(); samples = []
    allowed_thumb_urls = {f"https://studyway.kr/assets/images/search-thumbnails/{i:02d}.png" for i in range(1,14)}
    thumbnail_asset_errors = 0; content_og_ok = 0; twitter_match = 0
    for page in pages:
        html = page.read_text(encoding="utf-8")
        src_html = (SOURCE / page.relative_to(OUTPUT)).read_text(encoding="utf-8")
        p = Parser(); p.feed(html); sp = Parser(); sp.feed(src_html)
        vals = {k:p.values(k) for k in EXACT_KEYS}
        for key in EXACT_KEYS:
            if len(vals[key]) != 1: errors[f"{key}:count"] += 1
            elif not vals[key][0]: errors[f"{key}:empty"] += 1
        if any(len(vals[k]) != 1 for k in EXACT_KEYS): continue
        title, desc, canonical = vals["title"][0], vals["description"][0], vals["canonical"][0]
        if vals["og:title"][0] != title: errors["og:title:mismatch"] += 1
        if vals["og:description"][0] != desc: errors["og:description:mismatch"] += 1
        if vals["og:url"][0] != canonical: errors["canonical-og:url:mismatch"] += 1
        if vals["twitter:title"][0] != vals["og:title"][0]: errors["twitter:title:mismatch"] += 1
        if vals["twitter:description"][0] != vals["og:description"][0]: errors["twitter:description:mismatch"] += 1
        if vals["twitter:image"][0] != vals["og:image"][0]: errors["twitter:image:mismatch"] += 1
        else: twitter_match += 1
        if vals["twitter:card"][0] != "summary_large_image": errors["twitter:card:value"] += 1
        is_home = page == OUTPUT / "index.html"
        if vals["og:type"][0] != ("website" if is_home else "article"): errors["og:type:value"] += 1
        for key in ("canonical", "og:url", "og:image", "twitter:image"):
            value = vals[key][0]
            if not is_prod_absolute(value): errors[f"{key}:not-production-absolute"] += 1
            if "localhost" in value: errors["localhost"] += 1
            if "127.0.0.1" in value: errors["127.0.0.1"] += 1
            if value.startswith("file:"): errors["file-url"] += 1
        image = vals["og:image"][0]; og_images[image] += 1
        local_image = OUTPUT / unquote(urlsplit(image).path.lstrip("/"))
        if not local_image.is_file(): errors["image:missing-asset"] += 1
        width = p.values("og:image:width"); height = p.values("og:image:height")
        if len(width) != 1 or len(height) != 1: errors["image:dimension-meta-count"] += 1
        elif local_image.is_file() and png_size(local_image) != (int(width[0]), int(height[0])): errors["image:dimension-mismatch"] += 1
        if not is_home:
            if image not in allowed_thumb_urls: errors["content:image:not-allowed-thumbnail"] += 1
            elif local_image.is_file() and png_size(local_image) == (1254,1254): content_og_ok += 1
            else: thumbnail_asset_errors += 1
        for key in ("title", "description", "canonical", "og:image", "og:image:width", "og:image:height", "twitter:image"):
            before = sp.values(key)
            after = p.values(key)
            if before and before != after: preserved_errors[key] += 1
        if html[html.index("<body"): ] != src_html[src_html.index("<body"): ]: preserved_errors["body"] += 1
        try:
            docs = [json.loads(x) for x in p.jsonld]
            types=[]
            def walk(x):
                if isinstance(x,dict):
                    if "@type" in x: types.append(x["@type"])
                    for k,v in x.items(): structured_keys[k] += 1; walk(v)
                elif isinstance(x,list):
                    for v in x: walk(v)
            for doc in docs: walk(doc)
            structured_types.update(types)
            if types.count("BreadcrumbList") == 1: breadcrumb_ok += 1
            else: breadcrumb_error += 1
        except Exception: breadcrumb_error += 1
        forbidden["Review"] += types.count("Review") if 'types' in locals() else 0
        forbidden["AggregateRating"] += types.count("AggregateRating") if 'types' in locals() else 0
        for marker in ("ratingValue","reviewCount","bestRating","worstRating"):
            forbidden[marker] += structured_keys[marker] - forbidden.get("_seen_"+marker,0)
            forbidden["_seen_"+marker] = structured_keys[marker]
        forbidden['itemprop="rating"'] += html.count('itemprop="rating"')
        forbidden["data-rating"] += html.count("data-rating")

    thumbs = {}
    for i in range(1,14):
        path = OUTPUT / f"assets/images/search-thumbnails/{i:02d}.png"
        thumbs[f"{i:02d}.png"] = {"exists":path.is_file(), "size":png_size(path) if path.is_file() else None}
    with (REPORT / "url-plan.csv").open(encoding="utf-8-sig") as f: plan = list(csv.DictReader(f))
    wanted = [
        ("HOME", lambda u,t:u=="/"),
        ("서울 지역 일반", lambda u,t:"강남구/all/과외" in t),
        ("경기 지역 일반", lambda u,t:"부천/all/과외" in t),
        ("서울 지역 수학", lambda u,t:"강남구/all/고2수학과외" in t),
        ("서울 지역 영어", lambda u,t:"개봉동/고1영어과외" in t),
        ("경기 지역 수학", lambda u,t:"영통동/고2수학과외" in t),
        ("경기 지역 영어", lambda u,t:"부천/all/고2영어과외" in t),
        ("지역 초등 수학", lambda u,t:"초등수학과외" in t and "/region/" in u),
        ("지역 초등 영어", lambda u,t:"초등영어과외" in t and "/region/" in u),
        ("지역 중등 수학", lambda u,t:"중2수학과외" in t and "/region/" in u),
        ("지역 중등 영어", lambda u,t:"중2영어과외" in t and "/region/" in u),
        ("서울 학교 일반", lambda u,t:"가락고등학교/과외" in t),
        ("경기 학교 일반", lambda u,t:"청명고등학교/과외" in t),
        ("서울 학교 고1 수학", lambda u,t:"가락고등학교/고1수학과외" in t),
        ("서울 학교 고2 수학", lambda u,t:"가락고등학교/고2수학과외" in t),
        ("서울 학교 고3 수학", lambda u,t:"가락고등학교/고3수학과외" in t),
        ("서울 학교 고1 영어", lambda u,t:"가락고등학교/고1영어과외" in t),
        ("서울 학교 고2 영어", lambda u,t:"가락고등학교/고2영어과외" in t),
        ("서울 학교 고3 영어", lambda u,t:"가락고등학교/고3영어과외" in t),
        ("경기 학교 고2 수학", lambda u,t:"청명고등학교/고2수학과외" in t),
    ]
    representatives=[]; used=set()
    for label,pred in wanted:
        found=next((r["url"] for r in plan if r["url"] not in used and pred(r["url"],unquote(r["url"]))),None)
        if found: representatives.append({"label":label,"url":found});used.add(found)
    result={
        "html":len(pages),"home":1,"content":len(pages)-1,"errors":errors,"preserved_errors":preserved_errors,
        "og_image_distinct":len(og_images),"og_images":og_images,"content_og_image_ok":content_og_ok,
        "thumbnail_asset_errors":thumbnail_asset_errors,"twitter_image_match":twitter_match,"thumbnails":thumbs,
        "breadcrumb_ok":breadcrumb_ok,"breadcrumb_error":breadcrumb_error,"structured_types":structured_types,
        "forbidden_rating":{k:v for k,v in forbidden.items() if not k.startswith('_seen_')},
        "representatives":representatives,
    }
    (REPORT / "meta-audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    (REPORT / "representative-20.json").write_text(json.dumps(representatives,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == "__main__": main()
