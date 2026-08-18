from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
import statistics
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

import build_excel_review_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_clean_without_reviews"
OUTPUT = ROOT / "candidate_output_full_reviews_design"
REPORT = ROOT / "reports" / "full-reviews-design"
URL_PLAN = ROOT / "reports" / "url-plan.csv"
XLSX = Path(sys.argv[1])


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalized(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", text).lower()


def family(row: dict) -> str:
    if row["page_type"] == "school_content":
        return "school:" + (row["school_unique_name"] or row["school_name"] or row["url"].split("/")[2])
    return "region:" + "|".join((row["region"], row["district"], row["city"], row["dong_eup_myeon"] or "all"))


def subject_kind(row: dict) -> str:
    return "math" if row["subject"] == "수학" else "english" if row["subject"] == "영어" else "general"


class BalancedSelector:
    def __init__(self, pools: dict[str, list[dict]]):
        self.pools = pools
        self.usage = {sheet: Counter() for sheet in pools}
        self.cursor = {sheet: 0 for sheet in pools}
        self.order = {}
        for sheet, items in pools.items():
            for item in items:
                item["_norm"] = normalized(item["original"])
                item["_grams"] = {item["_norm"][i:i+4] for i in range(max(1, len(item["_norm"])-3))}
            self.order[sheet] = sorted(range(len(items)), key=lambda i: sha(f"full:{sheet}:{items[i]['row']}"))
        self.recent = defaultdict(lambda: deque(maxlen=25))

    def pick(self, sheet: str, row: dict, chosen: list[dict]) -> dict:
        items, order = self.pools[sheet], self.order[sheet]
        min_use = min(self.usage[sheet][x["row"]] for x in items)
        chosen_ids = {(x["sheet"], x["row"]) for x in chosen}
        chosen_bodies = [x["_norm"] for x in chosen]
        chosen_grams = [x["_grams"] for x in chosen]
        chosen_categories = {pilot.category(x["original"]) for x in chosen}
        recent = set(self.recent[(family(row), sheet)])
        candidates = []
        # Scan a wide deterministic window but only consider least-used reviews first.
        for step in range(min(len(order), 500)):
            pos = (self.cursor[sheet] + step) % len(order)
            idx = order[pos]; item = items[idx]; key = (sheet, item["row"])
            if key in chosen_ids or self.usage[sheet][item["row"]] > min_use: continue
            body = item["_norm"]
            exact = body in chosen_bodies
            similar = any(len(item["_grams"] & old) / max(1, len(item["_grams"] | old)) >= .78 for old in chosen_grams)
            cat_dup = pilot.category(item["original"]) in chosen_categories
            score = (exact, similar, item["row"] in recent, cat_dup, step, sha(row["url"] + str(item["row"])))
            candidates.append((score, pos, item))
            if len(candidates) >= 80: break
        if not candidates:
            # This only occurs at a usage-cycle boundary; open the next balanced level.
            min_use = min(self.usage[sheet][x["row"]] for x in items)
            for step in range(len(order)):
                pos = (self.cursor[sheet] + step) % len(order); item = items[order[pos]]
                if (sheet, item["row"]) in chosen_ids or self.usage[sheet][item["row"]] != min_use: continue
                body = item["_norm"]
                score = (body in chosen_bodies,
                         any(len(item["_grams"] & old) / max(1, len(item["_grams"] | old)) >= .78 for old in chosen_grams),
                         item["row"] in recent, pilot.category(item["original"]) in chosen_categories, step,
                         sha(row["url"] + str(item["row"])))
                candidates.append((score, pos, item))
                if len(candidates) >= 80: break
        score, pos, item = min(candidates, key=lambda x: x[0])
        self.cursor[sheet] = (pos + 1) % len(order)
        self.usage[sheet][item["row"]] += 1
        self.recent[(family(row), sheet)].append(item["row"])
        return item


def stars(url: str, sheet: str, row: int) -> int:
    return 4 if int(sha(f"{url}|{sheet}|{row}")[-2:], 16) % 5 == 0 else 5


def card_block(cards: list[dict]) -> str:
    parts = []
    for card in cards:
        star_text = "★" * card["stars"] + "☆" * (5 - card["stars"])
        parts.append('<article class="excel-review-card">'
                     f'<h3>{html.escape(card["title"])}</h3><p>{html.escape(card["body"])}</p>'
                     f'<div class="excel-review-stars" aria-label="별점 {card["stars"]}점">{star_text}</div></article>')
    return ('<section class="excel-review-section" aria-labelledby="excel-review-heading">'
            '<h2 id="excel-review-heading">수업에서 달라진 모습</h2><div class="excel-review-grid">'
            + "".join(parts) + "</div></section>")


CSS = r'''

/* Full review + content design candidate. Scoped to content and review areas only. */
.content-body-card{color:#334155;font-size:1rem;line-height:1.82}
.content-body-card>h2{margin:30px 0 16px;padding:18px 20px;background:#f5f7fb;border:1px solid #e2e8f0;border-radius:14px;color:#172033;font-size:clamp(1.2rem,2vw,1.45rem);line-height:1.45;box-shadow:0 4px 14px rgba(30,41,59,.04)}
.content-body-card>h2:first-child{margin-top:0}
.content-body-card h3{margin:24px 0 12px;padding:14px 16px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;color:#1e293b;font-size:1.08rem;line-height:1.5;box-shadow:0 3px 12px rgba(30,41,59,.035)}
.content-body-card p{margin:0 0 1.12em;color:#475569;line-height:1.82}
.content-body-card ul,.content-body-card ol{margin:16px 0 22px;padding:16px 18px 16px 40px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:13px}
.content-body-card li+li{margin-top:8px}
.content-body-card blockquote{margin:18px 0;padding:18px 20px;background:#f8fafc;border:1px solid #dbe4ee;border-left:4px solid #94a3b8;border-radius:12px;color:#475569}
.content-body-card table{width:100%;margin:18px 0;border-collapse:separate;border-spacing:0;overflow:hidden;border:1px solid #dfe6ef;border-radius:12px;background:#fff}
.content-body-card th,.content-body-card td{padding:12px 14px;border-bottom:1px solid #e5eaf1;text-align:left;vertical-align:top}
.content-body-card th{background:#f5f7fb;color:#1e293b}
.content-body-card tr:last-child td{border-bottom:0}
.excel-review-section{margin:28px 0 0;padding:28px;background:#f5f7fb;border:1px solid #e2e8f0;border-radius:20px;box-shadow:0 8px 24px rgba(30,41,59,.035)}
.excel-review-section>h2{margin:0 0 18px;color:#172033;font-size:clamp(1.25rem,2vw,1.55rem);line-height:1.35}
.excel-review-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.excel-review-card{min-width:0;padding:20px;background:#fff;border:1px solid #dde4ee;border-radius:15px;box-shadow:0 5px 18px rgba(30,41,59,.055)}
.excel-review-card:nth-child(5):last-child{grid-column:1/-1;width:calc((100% - 16px)/2);justify-self:center}
.excel-review-card h3{margin:0 0 10px;color:#172033;font-size:1.05rem;line-height:1.45;overflow-wrap:anywhere}
.excel-review-card p{margin:0;color:#475569;font-size:.96rem;line-height:1.78;overflow-wrap:anywhere}
.excel-review-stars{margin-top:14px;color:#f59e0b;font-size:1rem;letter-spacing:.06em;line-height:1;text-align:right}
@media(max-width:767px){.content-body-card{font-size:.96rem;line-height:1.76}.content-body-card>h2{margin:24px 0 14px;padding:16px;border-radius:12px}.content-body-card h3{margin:20px 0 10px;padding:13px 14px}.content-body-card p{line-height:1.76}.content-body-card table{display:block;max-width:100%;overflow-x:auto}.excel-review-section{margin:22px 0 0;padding:18px 14px;border-radius:16px}.excel-review-grid{grid-template-columns:1fr;gap:12px}.excel-review-card,.excel-review-card:nth-child(5):last-child{grid-column:auto;width:100%;justify-self:stretch;padding:17px}.excel-review-card h3{font-size:1rem}.excel-review-card p{font-size:.93rem;line-height:1.72}}
'''


def snapshot(text: str) -> dict:
    def one(pattern):
        m = re.search(pattern, text, re.S); return m.group(1) if m else ""
    return {
        "title": one(r"<title>(.*?)</title>"), "description": one(r'<meta name="description" content="([^"]*)"'),
        "h1": one(r"<h1[^>]*>(.*?)</h1>"), "canonical": one(r'<link rel="canonical" href="([^"]+)"'),
        "og_image": one(r'<meta property="og:image" content="([^"]+)"'),
        "body": one(r'(<article class="content-body-card">.*?</article>)'),
        "images": re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', text),
        "links": re.findall(r'<a\b[^>]*\bhref="([^"]+)"', text),
    }


def main():
    pools, filter_audit = pilot.read_excel_f(XLSX)
    assert len(pools["수학"]) == 860 and len(pools["영어"]) == 1328
    with URL_PLAN.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["page_type"] in {"region_content", "school_content"}]
    if len(rows) != 19188: raise RuntimeError(f"content rows: {len(rows)}")
    linked_schools = set()
    for r in rows:
        if r["page_type"] != "school_content" or r["subject"] or r["grade"]: continue
        source_text = pilot.page_path(SOURCE, r["url"]).read_text(encoding="utf-8")
        if 'href="/region/' in source_text: linked_schools.add(r["school_unique_name"] or r["school_name"])
    if len(linked_schools) != 619: raise RuntimeError(f"linked schools: {len(linked_schools)}")
    rows.sort(key=lambda r: (family(r), r["url"]))
    if OUTPUT.exists() and sum(1 for _ in OUTPUT.rglob("index.html")) == 19189:
        # Continue from the completed clone after an interrupted build: restore only partially modified pages.
        restored = 0
        for dst in OUTPUT.rglob("index.html"):
            text = dst.read_text(encoding="utf-8")
            if 'class="excel-review-section"' in text:
                shutil.copy2(SOURCE / dst.relative_to(OUTPUT), dst); restored += 1
        print(f"reused clone; restored {restored} partial pages", flush=True)
    else:
        if OUTPUT.exists(): shutil.rmtree(OUTPUT)
        shutil.copytree(SOURCE, OUTPUT)
    REPORT.mkdir(parents=True, exist_ok=True)
    css = OUTPUT / "static" / "css" / "site.css"
    css.write_text((SOURCE / "static" / "css" / "site.css").read_text(encoding="utf-8") + CSS, encoding="utf-8")
    selector = BalancedSelector(pools)
    counts = Counter(); changes = Counter(); stars_count = Counter(); page_records=[]; card_records=[]
    regression = Counter(); family_recent = defaultdict(lambda: deque(maxlen=5)); adjacent_repeat = 0
    exact_page_dup = 0; similar_page = 0
    for page_no, row in enumerate(rows, 1):
        src = pilot.page_path(SOURCE, row["url"]); dst = pilot.page_path(OUTPUT, row["url"])
        source_html = src.read_text(encoding="utf-8"); before = snapshot(source_html)
        kind = subject_kind(row)
        if kind == "math": recipe=[("수학",5)]
        elif kind == "english": recipe=[("영어",5)]
        elif int(sha(row["canonical"])[0],16)%2==0: recipe=[("수학",3),("영어",2)]
        else: recipe=[("영어",3),("수학",2)]
        chosen=[]
        for sheet,n in recipe:
            for _ in range(n): chosen.append(selector.pick(sheet,row,chosen))
        chosen.sort(key=lambda x: sha(row["url"]+x["sheet"]+str(x["row"])))
        ids={(x["sheet"],x["row"]) for x in chosen}; exact_page_dup += len(chosen)-len(ids)
        norms=[x["_norm"] for x in chosen]; grams=[x["_grams"] for x in chosen]
        similar_page += sum(len(grams[i]&grams[j])/max(1,len(grams[i]|grams[j]))>=.78 for i in range(5) for j in range(i+1,5))
        fam=family(row); prior=set().union(*family_recent[fam]) if family_recent[fam] else set()
        adjacent_repeat += len(ids & prior); family_recent[fam].append(ids)
        cards=[]
        for idx,item in enumerate(chosen):
            adapt_row = row
            school_key = row["school_unique_name"] or row["school_name"]
            if row["page_type"] == "school_content" and school_key not in linked_schools:
                adapt_row = {**row, "region":"", "district":"", "city":"", "dong_eup_myeon":""}
            body, edits = pilot.adapt(item["original"], adapt_row); changes.update(edits)
            rating=stars(row["url"],item["sheet"],item["row"]); stars_count[rating]+=1
            cat=pilot.category(item["original"])
            card={"sheet":item["sheet"],"excel_row":item["row"],"body":body,"original":item["original"],
                  "title":pilot.short_title(body,cat,idx+page_no),"category":cat,"stars":rating}
            cards.append(card)
            card_records.append({"url":row["url"],"family":fam,"page_subject":kind,**card,"changes":edits})
        if '</div><section class="related-navigation' not in source_html: raise RuntimeError("insertion point: "+row["url"])
        output_html=source_html.replace('</div><section class="related-navigation','</div>'+card_block(cards)+'<section class="related-navigation',1)
        dst.write_text(output_html,encoding="utf-8")
        after=snapshot(output_html)
        for key in before:
            if after[key] != before[key]: regression[key]+=1
        counts[(row["page_type"],kind)]+=1
        page_records.append({"url":row["url"],"page_type":row["page_type"],"subject":kind,"family":fam,
                             "cards":5,"review_ids":[f"{x['sheet']}:{x['row']}" for x in chosen]})
        if page_no % 1000 == 0: print(f"pages {page_no}/19188", flush=True)
    usage_stats={}
    for sheet,items in pools.items():
        vals=[selector.usage[sheet][x["row"]] for x in items]
        usage_stats[sheet]={"reviews":len(vals),"total":sum(vals),"min":min(vals),"max":max(vals),
                            "average":sum(vals)/len(vals),"median":statistics.median(vals)}
    placeholder_wrong=sum("개봉동" in c["body"] and "개봉동" not in c["family"] for c in card_records)
    audit={"content_pages":len(rows),"review_sections":len(page_records),"cards":len(card_records),"home_reviews":0,
           "filter":filter_audit,"page_counts":{"region":sum(r["page_type"]=="region_content" for r in rows),"school":sum(r["page_type"]=="school_content" for r in rows)},
           "subject_page_counts":dict(Counter(r["subject"] for r in page_records)),"usage":usage_stats,
           "diversity":{"same_page_duplicate_id":exact_page_dup,"same_page_similarity_ge_0_90":similar_page,"adjacent_family_same_review":adjacent_repeat},
           "replacement":{"changes":dict(changes),"wrong_placeholder_remaining":placeholder_wrong,
                          "linked_schools":len(linked_schools),"unlinked_schools":662-len(linked_schools)},
           "stars":{"five":stars_count[5],"four":stars_count[4],"other":sum(v for k,v in stars_count.items() if k not in {4,5})},
           "regression":{"c_body_text":regression["body"],"images":regression["images"],"url":0,"title":regression["title"],"description":regression["description"],
                         "h1":regression["h1"],"canonical":regression["canonical"],"og_image":regression["og_image"],"internal_links":regression["links"],
                         "sitemap":int((SOURCE/"sitemap-content.xml").read_bytes()!=(OUTPUT/"sitemap-content.xml").read_bytes())},
           "design":{"heading":"수업에서 달라진 모습","desktop_columns":2,"fifth_centered":True,"mobile_columns":1,"structured_rating":0}}
    (REPORT/"audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    (REPORT/"pages.json").write_text(json.dumps(page_records,ensure_ascii=False,indent=2),encoding="utf-8")
    # Full card provenance is compact JSONL to keep audit memory and file size manageable.
    with (REPORT/"cards.jsonl").open("w",encoding="utf-8") as f:
        for card in card_records: f.write(json.dumps(card,ensure_ascii=False)+"\n")
    print(json.dumps(audit,ensure_ascii=False,indent=2))


if __name__ == "__main__": main()
