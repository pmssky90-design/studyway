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
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_clean_without_reviews"
OUTPUT = ROOT / "candidate_output_excel_reviews"
REPORT_DIR = ROOT / "reports" / "excel-review-pilot"
URL_PLAN = ROOT / "reports" / "url-plan.csv"
XLSX = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\자료\후기글.xlsx")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


ERROR_VALUES = {"#ERROR!", "#N/A", "#VALUE!", "#REF!", "#NAME?", "#NUM!", "#DIV/0!", "ERROR", "오류"}
STATE_RE = re.compile(r"^(?:로드\s*중|loading|생성\s*중|처리\s*중)(?:\.{0,3}|…)?$", re.I)
FOREIGN_SCRIPT_RE = re.compile(r"[\u0400-\u052f\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\u0a80-\u0aff\u0e00-\u0e7f]")
FORMULA_RE = re.compile(r"^\s*=|_xlfn\.|(?:^|[^A-Za-z])GPT\s*\(", re.I)
SENTENCE_END_RE = re.compile(r"(?:[.!?…]|(?:습니다|입니다|했습니다|됐습니다|보였습니다|느껴졌습니다|생겼습니다|달라졌습니다|좋았습니다|편해졌습니다|놓였습니다|되었습니다|되었어요|했어요|됐어요|있어요|같아요|보여요|느꼈어요|생겼어요))[\"'”’)]*$")


def classify_f_value(value: str) -> tuple[str | None, str | None]:
    text = (value or "").strip()
    if not text: return None, "빈칸"
    if text.upper() in ERROR_VALUES or text.startswith("#"): return None, "오류"
    if STATE_RE.fullmatch(text): return None, "로드 중"
    if FORMULA_RE.search(text): return None, "기타"
    if "�" in text or FOREIGN_SCRIPT_RE.search(text): return None, "깨진 문자"
    # A review body must have enough context to stand alone; short status/fragments are not repaired.
    if len(text) < 100: return None, "기타"
    if not SENTENCE_END_RE.search(text): return None, "잘린 문장"
    if "개봉동" in text and not re.search(r"개봉동(?:에서|의|으로|과외|수업|지역|에|을|를|은|는)", text):
        return None, "기타"
    return text, None


def read_excel_f(path: Path) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    result, audit = {}, {}
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rel = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        relmap = {x.attrib["Id"]: x.attrib["Target"] for x in rel}
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(NS + "t")) for si in ss.findall(NS + "si")]
        for sheet in wb.find(NS + "sheets"):
            name = sheet.attrib["name"]
            if name not in {"수학", "영어"}:
                continue
            target = relmap[sheet.attrib[RNS + "id"]].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            root = ET.fromstring(z.read(target))
            values = []
            counts = Counter({"전체 F": 0, "정상 F": 0, "빈칸": 0, "오류": 0, "로드 중": 0, "깨진 문자": 0, "잘린 문장": 0, "기타": 0})
            for row in root.iter(NS + "row"):
                row_num = int(row.attrib.get("r", "0"))
                if row_num <= 1: continue
                value = ""
                for cell in row.findall(NS + "c"):
                    if not re.fullmatch(r"F\d+", cell.attrib.get("r", "")):
                        continue
                    typ, v, inline = cell.attrib.get("t"), cell.find(NS + "v"), cell.find(NS + "is")
                    if typ == "s" and v is not None:
                        value = shared[int(v.text)]
                    elif typ == "inlineStr" and inline is not None:
                        value = "".join(t.text or "" for t in inline.iter(NS + "t"))
                    elif v is not None:
                        value = v.text or ""
                counts["전체 F"] += 1
                cleaned, reason = classify_f_value(value)
                if reason:
                    counts[reason] += 1
                else:
                    counts["정상 F"] += 1
                    values.append({"sheet": name, "row": row_num, "original": cleaned})
            result[name] = values
            audit[name] = dict(counts)
    return result, audit


def page_path(base: Path, url: str) -> Path:
    return base / unquote(url.strip("/")) / "index.html"


def subject_kind(row: dict) -> str:
    return "math" if row["subject"] == "수학" else "english" if row["subject"] == "영어" else "general"


def grade_group(value: str) -> str:
    if value in {"초", "초1", "초2", "초3", "초4", "초5", "초6"}: return "elementary"
    if value in {"중", "중1", "중2", "중3"}: return "middle"
    if value in {"고1", "고2", "고3"}: return value
    return "all"


def choose_pages(rows: list[dict]) -> list[dict]:
    # Exact pilot matrix: page type(2) x province(2), each cell 10 math + 10 English + 5 general.
    chosen = []
    grade_cycle = ["elementary", "middle", "고1", "고2", "고3", "all"]
    for ptype in ("region_content", "school_content"):
        for province in ("서울", "경기"):
            for kind, quota in (("math", 10), ("english", 10), ("general", 5)):
                pool = [r for r in rows if r["page_type"] == ptype and
                        (r["region"] == province or (province == "경기" and r["region"].startswith("경기"))) and
                        subject_kind(r) == kind]
                pool.sort(key=lambda r: sha(r["url"]))
                used = set()
                for i in range(quota):
                    desired = grade_cycle[i % len(grade_cycle)]
                    pick = next((r for r in pool if r["url"] not in used and grade_group(r["grade"]) == desired), None)
                    if pick is None:
                        pick = next(r for r in pool if r["url"] not in used)
                    used.add(pick["url"]); chosen.append(pick)
    return chosen


def category(text: str) -> str:
    groups = [
        ("질문", r"질문|물어|모르는"), ("숙제", r"숙제|과제"), ("오답", r"오답|틀린"),
        ("시험", r"시험|내신|모의고사"), ("계획", r"계획|일정|루틴"), ("개념", r"개념|이해"),
        ("태도", r"태도|자신감|부담|편안"), ("복습", r"복습|다시"), ("풀이", r"풀이|문제"),
        ("습관", r"습관|스스로|미루"), ("수업", r"수업|선생님"),
    ]
    for name, pat in groups:
        if re.search(pat, text): return name
    return "변화"


def representative_region(row: dict) -> tuple[str, bool]:
    # url-plan is the verified source for the 619 region-school relationships.
    value = row["dong_eup_myeon"] or row["district"] or row["city"]
    return value, bool(value)


def adapt(text: str, row: dict) -> tuple[str, list[str]]:
    changes = []
    region, linked = representative_region(row)
    if "개봉동" in text:
        if region:
            text = text.replace("개봉동", region); changes.append("region_replace")
        else:
            text = text.replace("개봉동에서 ", "").replace("개봉동에서", "").replace("개봉동", "")
            changes.append("region_remove")
    target = row["grade"]
    if target and target not in {"초", "중"}:
        mapping = {
            "초1": "초등학교 1학년", "초2": "초등학교 2학년", "초3": "초등학교 3학년",
            "초4": "초등학교 4학년", "초5": "초등학교 5학년", "초6": "초등학교 6학년",
            "중1": "중학교 1학년", "중2": "중학교 2학년", "중3": "중학교 3학년",
            "고1": "고등학교 1학년", "고2": "고등학교 2학년", "고3": "고등학교 3학년",
        }
        replacement = mapping.get(target)
        if replacement:
            pat = r"(?:초등학교|중학교|고등학교)\s*[1-6]학년|(?<![가-힣])(?:초[1-6]|중[1-3]|고[1-3])(?![가-힣])"
            if re.search(pat, text):
                text = re.sub(pat, replacement, text); changes.append("grade_adjust")
    return re.sub(r"\s{2,}", " ", text).strip(), changes


def short_title(text: str, cat: str, i: int) -> str:
    variants = {
        "질문": ["질문이 편해진 수업", "먼저 묻게 된 변화", "모르는 걸 말하는 힘"],
        "숙제": ["숙제를 챙기는 습관", "밀리지 않는 과제", "스스로 확인한 숙제"],
        "오답": ["틀린 문제를 다시 보는 법", "오답에서 찾은 변화", "실수를 넘기지 않는 습관"],
        "시험": ["시험 준비가 차분해졌어요", "흔들리지 않는 시험 준비", "시험 전에 생긴 여유"],
        "계획": ["공부 순서가 보이기 시작했어요", "지킬 수 있는 학습 계획", "하루 공부가 정돈됐어요"],
        "개념": ["이해부터 확인한 수업", "개념이 연결된 순간", "천천히 이해한 뒤의 변화"],
        "태도": ["공부가 한결 편안해졌어요", "부담을 덜어낸 수업", "자신감이 생긴 과정"],
        "복습": ["복습을 이어 가는 힘", "다시 보는 습관의 변화", "복습 순서가 잡혔어요"],
        "풀이": ["풀이를 설명하게 됐어요", "문제를 대하는 방식의 변화", "답보다 과정을 보는 수업"],
        "습관": ["스스로 시작하는 공부", "미루지 않는 작은 변화", "공부 습관이 달라졌어요"],
        "수업": ["기다려 주는 수업의 힘", "차분하게 이어 간 수업", "수업 뒤 달라진 모습"],
        "변화": ["작지만 분명한 변화", "공부가 달라진 계기", "조금씩 생긴 자신감"],
    }
    return variants[cat][i % len(variants[cat])]


def select_reviews(pool: list[dict], row: dict, count: int, global_used: set[tuple], global_bodies: set[str], page_categories: set[str]) -> list[dict]:
    ordered = sorted(pool, key=lambda x: sha(row["url"] + ":" + x["sheet"] + ":" + str(x["row"])))
    picked, cats = [], set(page_categories)
    for prefer_new_category in (True, False):
        for item in ordered:
            key = (item["sheet"], item["row"])
            cat = category(item["original"])
            body_key = re.sub(r"\s+", "", item["original"])
            if key in global_used or body_key in global_bodies or item in picked or (prefer_new_category and cat in cats): continue
            picked.append(item); cats.add(cat); global_used.add(key)
            global_bodies.add(body_key)
            if len(picked) == count: return picked
    raise RuntimeError("review pool exhausted")


def review_html(cards: list[dict]) -> str:
    chunks = []
    for c in cards:
        chunks.append(
            '<article class="excel-review-card">'
            f'<h3>{html.escape(c["title"])}</h3><p>{html.escape(c["body"])}</p>'
            f'<div class="excel-review-stars" aria-label="별점 {c["stars"]}점">{("★" * c["stars"] + "☆" * (5-c["stars"]))}</div></article>'
        )
    return '<section class="excel-review-section" aria-labelledby="excel-review-heading"><h2 id="excel-review-heading">수업을 경험한 이야기</h2><div class="excel-review-grid">' + "".join(chunks) + "</div></section>"


CSS = r'''

/* Excel review pilot: scoped to the 100 selected content pages. */
.excel-review-section{margin:28px 0 0;padding:28px;background:#f5f7fb;border:1px solid #e2e8f0;border-radius:20px}
.excel-review-section>h2{margin:0 0 18px;color:#172033;font-size:clamp(1.25rem,2vw,1.55rem);line-height:1.35}
.excel-review-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.excel-review-card{min-width:0;padding:20px;background:#fff;border:1px solid #dde4ee;border-radius:15px;box-shadow:0 5px 18px rgba(30,41,59,.055)}
.excel-review-stars{margin-top:14px;color:#f59e0b;font-size:1rem;letter-spacing:.06em;line-height:1;text-align:right}
.excel-review-card h3{margin:0 0 10px;color:#172033;font-size:1.05rem;line-height:1.45;overflow-wrap:anywhere}
.excel-review-card p{margin:0;color:#475569;font-size:.96rem;line-height:1.78;overflow-wrap:anywhere}
@media(max-width:640px){.excel-review-section{margin:22px 0 0;padding:18px 14px;border-radius:16px}.excel-review-grid{grid-template-columns:1fr;gap:12px}.excel-review-card{padding:17px}.excel-review-card h3{font-size:1rem}.excel-review-card p{font-size:.93rem;line-height:1.72}}
'''


def protected_snapshot(text: str) -> dict:
    def one(pat):
        m = re.search(pat, text, re.S); return m.group(1) if m else ""
    return {
        "title": one(r"<title>(.*?)</title>"), "h1": one(r"<h1[^>]*>(.*?)</h1>"),
        "canonical": one(r'<link rel="canonical" href="([^"]+)"'),
        "body": one(r'(<article class="content-body-card">.*?</article>)'),
        "images": re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', text),
        "links": re.findall(r'<a\b[^>]*\bhref="([^"]+)"', text),
        "description": one(r'<meta name="description" content="([^"]*)"'),
    }


def main():
    excel, f_filter = read_excel_f(XLSX)
    with URL_PLAN.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["page_type"] in {"region_content", "school_content"}]
    pages = choose_pages(rows)
    if len(pages) != 100: raise RuntimeError(f"expected 100 pages, got {len(pages)}")
    if OUTPUT.exists(): shutil.rmtree(OUTPUT)
    shutil.copytree(SOURCE, OUTPUT)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    css_path = OUTPUT / "static" / "css" / "site.css"
    css_path.write_text(css_path.read_text(encoding="utf-8") + CSS, encoding="utf-8")

    global_used, global_bodies, cards, page_audit = set(), set(), [], []
    baselines = {}
    for page_index, row in enumerate(pages):
        path = page_path(OUTPUT, row["url"]); src_path = page_path(SOURCE, row["url"])
        if not path.is_file(): raise FileNotFoundError(path)
        original_html = src_path.read_text(encoding="utf-8")
        baselines[row["url"]] = protected_snapshot(original_html)
        kind = subject_kind(row)
        if kind == "math": sources = [("수학", 5)]
        elif kind == "english": sources = [("영어", 5)]
        else:
            sources = [("수학", 3), ("영어", 2)] if int(sha(row["url"])[0], 16) % 2 == 0 else [("영어", 3), ("수학", 2)]
        selected, page_categories = [], set()
        for sheet, n in sources:
            batch = select_reviews(excel[sheet], row, n, global_used, global_bodies, page_categories)
            selected.extend(batch); page_categories.update(category(x["original"]) for x in batch)
        selected.sort(key=lambda x: sha(row["url"] + str(x["row"])))
        page_cards = []
        for card_index, item in enumerate(selected):
            body, changes = adapt(item["original"], row)
            cat = category(item["original"])
            star = 4 if int(sha(row["url"] + str(item["row"]))[-1], 16) % 5 == 0 else 5
            card = {"url": row["url"], "page_type": row["page_type"], "province": row["region"],
                    "region": representative_region(row)[0], "school": row["school_name"], "page_subject": kind,
                    "page_grade": row["grade"], "sheet": item["sheet"], "excel_row": item["row"],
                    "category": cat, "title": short_title(body, cat, card_index + page_index), "body": body,
                    "original": item["original"], "changes": changes, "stars": star,
                    "source_preserved": body.replace(representative_region(row)[0], "개봉동", 1) == item["original"] if representative_region(row)[0] else False}
            page_cards.append(card); cards.append(card)
        block = review_html(page_cards)
        if "</div><section class=\"related-navigation" not in original_html: raise RuntimeError("insertion point missing: " + row["url"])
        output_html = original_html.replace("</div><section class=\"related-navigation", "</div>" + block + "<section class=\"related-navigation", 1)
        path.write_text(output_html, encoding="utf-8")
        page_audit.append({"url": row["url"], "page_type": row["page_type"], "province": row["region"],
                           "subject": kind, "grade": row["grade"], "cards": len(page_cards),
                           "sheets": dict(Counter(x["sheet"] for x in page_cards)),
                           "categories": [x["category"] for x in page_cards]})

    regress = Counter()
    for row in pages:
        now = protected_snapshot(page_path(OUTPUT, row["url"]).read_text(encoding="utf-8"))
        for field, before in baselines[row["url"]].items():
            if now[field] != before: regress[field] += 1
    source_hash = sha(XLSX.read_bytes().hex())
    category_counts = Counter(c["category"] for c in cards)
    sheet_counts = Counter(c["sheet"] for c in cards)
    changes = Counter(x for c in cards for x in c["changes"])
    audit = {
        "excel": {"path": str(XLSX.resolve()), "sha256": source_hash, "valid_math_f": len(excel["수학"]), "valid_english_f": len(excel["영어"]), "valid_total_f": sum(map(len, excel.values())), "f_review_filter": f_filter},
        "placement": {"pilot_pages": len(pages), "cards": len(cards), "cards_per_page": dict(Counter(x["cards"] for x in page_audit)), "sheet_counts": dict(sheet_counts),
                      "unique_excel_rows_used": len(global_used), "page_type_counts": dict(Counter(x["page_type"] for x in page_audit)),
                      "province_counts": dict(Counter(x["province"] for x in page_audit)), "subject_counts": dict(Counter(x["subject"] for x in page_audit)),
                      "grade_counts": dict(Counter(grade_group(x["grade"]) for x in page_audit))},
        "replacement": {"changes": dict(changes), "remaining_placeholder": sum("개봉동" in c["body"] for c in cards),
                        "school_pages_unlinked": sum(1 for x in page_audit if x["page_type"] == "school_content" and not next(r for r in pages if r["url"] == x["url"])["dong_eup_myeon"]),
                        "exact_region_school_mapping_used": sum(1 for x in page_audit if x["page_type"] == "school_content" and next(r for r in pages if r["url"] == x["url"])["dong_eup_myeon"])},
        "diversity": {"categories": dict(category_counts), "duplicate_bodies": len(cards)-len({c["body"] for c in cards}),
                      "duplicate_excel_rows": len(cards)-len(global_used), "pages_with_duplicate_category": sum(len(x["categories"]) != len(set(x["categories"])) for x in page_audit),
                      "max_excel_row_usage": max(Counter((c["sheet"], c["excel_row"]) for c in cards).values())},
        "regression": {"c_body_changed": regress["body"], "images_changed": regress["images"], "title_changed": regress["title"], "h1_changed": regress["h1"],
                       "canonical_changed": regress["canonical"], "internal_links_changed": regress["links"], "description_changed": regress["description"],
                       "url_changed": 0, "sitemap_changed": int((SOURCE/"sitemap-content.xml").read_bytes() != (OUTPUT/"sitemap-content.xml").read_bytes())},
        "ui": {"heading": "수업을 경험한 이야기", "desktop_columns": 2, "mobile_columns": 1, "schema_review_markup": 0},
    }
    (REPORT_DIR / "cards.json").write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "pages.json").write_text(json.dumps(page_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    with (REPORT_DIR / "pages.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["url","page_type","province","subject","grade","cards","sheets","categories"]); w.writeheader()
        for x in page_audit: w.writerow({**x, "sheets": json.dumps(x["sheets"], ensure_ascii=False), "categories": "|".join(x["categories"])})
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
