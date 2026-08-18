from __future__ import annotations

import csv
import html
import importlib.util
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
SOURCE = ROOT / "candidate_output_review_stress_500_v2"
OUTPUT = ROOT / "candidate_output_reviews_full"
URL_PLAN = REPORTS / "url-plan.csv"
SAMPLE_PLANS = REPORTS / "review-stress-500-v2-story-plans.csv"
SAMPLE_CARDS = REPORTS / "review-stress-500-v2-cards.json"
PLANS = REPORTS / "review-full-story-plans.csv"
CARDS = REPORTS / "review-full-cards.json"
CHECKPOINT = REPORTS / "review-full-checkpoint.json"
CARDS_JSONL = REPORTS / "review-full-cards.checkpoint.jsonl"

spec = importlib.util.spec_from_file_location("review_v2", ROOT / "scripts/build_review_stress_500_v2.py")
v2 = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(v2)

PLAN_FIELDS = [
    "page_id", "card_id", "content_type", "region_or_school", "grade", "subject", "page_topic",
    "scene_type", "scene_timing", "starting_state", "trigger", "first_action", "specific_mistake",
    "missed_information", "student_reaction", "teacher_or_training_action", "correction_method",
    "verification_method", "ending_state", "headline_angle", "opening_angle", "ending_angle",
    "source_cues", "source_excerpt", "canonical", "path",
]


def load_rows() -> list[dict]:
    with URL_PLAN.open(encoding="utf-8-sig", newline="") as f:
        raw = [r for r in csv.DictReader(f) if r["page_type"] in ("region_content", "school_content")]
    rows = []
    for r in raw:
        path = unquote(urlsplit(r["url"]).path.strip("/")) + "/index.html"
        text = (SOURCE / path).read_text(encoding="utf-8")
        title_match = re.search(r"<title>(.*?)</title>", text, re.S)
        kind = "region" if r["page_type"] == "region_content" else "school"
        topic = r["source_sheet"].removeprefix("(학교)")
        subject = r["subject"] or ("수학" if "수학" in topic else "영어" if "영어" in topic else "")
        grade = re.sub(r"[^초중고0-9]", "", topic) or "기본"
        region_name = "-".join(x for x in (r["district"], r["dong_eup_myeon"]) if x)
        rows.append({
            "kind": kind, "province": r["region"], "type": f"{grade}-{subject or '일반'}",
            "region": region_name if kind == "region" else "", "school": r["school_name"] if kind == "school" else "",
            "grade": grade, "subject": subject or "일반", "title": html.unescape(title_match.group(1)).strip(),
            "canonical": r["canonical"], "path": path,
        })
    if len(rows) != 19188:
        raise SystemExit(f"expected 19188 content rows, got {len(rows)}")
    return rows


def checkpoint(stage: str, page_id: int, card_id: int, pages: int, cards: int) -> None:
    CHECKPOINT.write_text(json.dumps({
        "version": "story-v2-full", "stage": stage, "last_completed_page_id": page_id,
        "last_completed_card_id": card_id, "completed_pages": pages, "completed_cards": cards,
        "plans_file": str(PLANS.relative_to(ROOT)), "cards_checkpoint": str(CARDS_JSONL.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def choose_headline(p: dict, used: set[str]) -> str:
    sub = v2.headline(p)
    candidates = [
        sub,
        f"{p['specific_mistake'][:10]} 뒤 {p['correction_method'][:14]}",
        f"{p['scene_timing']}, {p['verification_method'][:17]}",
        f"{p['first_action'][:11]}에서 찾은 {p['specific_mistake'][:10]}",
        f"{p['scene_type'][:10]} · {p['ending_angle'][:15]}",
        f"{p['scene_type'][:6]}·{p['specific_mistake'][:6]}·{p['correction_method'][:6]}·{p['verification_method'][:6]}",
        f"{p['first_action'][:7]}·{p['specific_mistake'][:7]}·{p['ending_angle'][:9]}",
    ]
    value = next((x[:30] for x in candidates if x[:30] not in used), "")
    if not value:
        # The seven-field plan tuple is globally unique. This semantic-only fallback
        # keeps that uniqueness without exposing counters, page IDs, or card IDs.
        value = " · ".join((p["scene_type"], p["first_action"], p["specific_mistake"],
                            p["correction_method"], p["verification_method"], p["ending_angle"]))
        if value in used:
            value = " · ".join((p["scene_timing"], p["trigger"], value))
    if not value:
        raise SystemExit(f"headline collision unresolved: {p['canonical']} #{p['card_id']}")
    used.add(value)
    return value


def section(cards: list[dict]) -> str:
    return '<section class="learning-case-section" aria-labelledby="learning-cases"><h2 id="learning-cases">학습 과정에서 확인한 사례</h2><div class="learning-case-grid">' + ''.join(
        f'<article class="learning-case-card"><h3>{html.escape(c["subheading"])}</h3><p>{html.escape(c["body"])}</p><div class="learning-case-meta"><span class="learning-case-stars" aria-label="디자인용 별 아이콘">{c["stars"]}</span></div></article>'
        for c in cards) + '</div></section>'


def main() -> None:
    rows = load_rows()
    sample_cards = json.loads(SAMPLE_CARDS.read_text(encoding="utf-8"))
    sample_by_key = {(c["canonical"], int(c["card"])): c for c in sample_cards}
    sample_paths = {c["path"] for c in sample_cards}

    # V2 generates the globally collision-free plan space first. The already-PASSed
    # sample records are then restored byte-for-byte at the data-record level.
    generated = v2.make_plans(rows)
    with SAMPLE_PLANS.open(encoding="utf-8-sig", newline="") as f:
        old_plans = {(p["canonical"], int(p["card_id"])): p for p in csv.DictReader(f)}
    sample_page_ids = {}
    for c in sample_cards:
        sample_page_ids.setdefault(c["canonical"], int(c["page_index"]))
    next_page_id = 501
    full_page_ids = {}
    for row in rows:
        if row["canonical"] in sample_page_ids:
            full_page_ids[row["canonical"]] = sample_page_ids[row["canonical"]]
        else:
            full_page_ids[row["canonical"]] = next_page_id
            next_page_id += 1
    plans = []
    for p in generated:
        old = old_plans.get((p["canonical"], int(p["card_id"])))
        if old:
            keep = dict(p)
            keep.update(old)
            keep["page_id"] = int(old["page_id"])
            keep["card_id"] = int(old["card_id"])
            plans.append(keep)
        else:
            p["page_id"] = full_page_ids[p["canonical"]]
            plans.append(p)
    with PLANS.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PLAN_FIELDS, extrasaction="ignore")
        w.writeheader(); w.writerows(plans)
    checkpoint("plans_complete", 0, 0, 0, 0)

    if not OUTPUT.exists():
        shutil.copytree(SOURCE, OUTPUT)
    completed_paths = set()
    cards = []
    if CARDS_JSONL.exists():
        for line in CARDS_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c = json.loads(line); cards.append(c); completed_paths.add(c["path"])
    used_headlines = {c["subheading"] for c in cards} | {c["subheading"] for c in sample_cards}
    used_last = {re.split(r"(?<=[.!?])\s+", c["body"])[-1] for c in cards + sample_cards}
    grouped = defaultdict(list)
    for p in plans:
        grouped[p["path"]].append(p)
    mode = "a" if CARDS_JSONL.exists() else "w"
    completed_pages = len(completed_paths)
    with CARDS_JSONL.open(mode, encoding="utf-8", newline="\n") as stream:
        for row in rows:
            page_id = full_page_ids[row["canonical"]]
            if row["path"] in sample_paths or row["path"] in completed_paths:
                continue
            page_cards = []
            for p in grouped[row["path"]]:
                idx = len(cards) + len(sample_cards)
                sub = choose_headline(p, used_headlines)
                body = v2.render_body(p, idx)
                ending = re.split(r"(?<=[.!?])\s+", body)[-1]
                if ending in used_last:
                    body = body[:-1] + f"; {p['region_or_school']} {p['page_topic']} 재확인."
                    ending = re.split(r"(?<=[.!?])\s+", body)[-1]
                if ending in used_last:
                    raise SystemExit(f"ending collision unresolved: {p['canonical']} #{p['card_id']}")
                used_last.add(ending)
                stars = "★★★★☆" if v2.sha(p["canonical"] + f"#{p['card_id']}") % 5 in (0, 3) else "★★★★★"
                n = len([x for x in re.split(r"(?<=[.!?])\s+", body) if x])
                c = {**{k: p[k] for k in ("kind", "province", "type", "region", "school", "grade", "subject", "title", "canonical", "path")},
                     "page_index": int(p["page_id"]), "card": int(p["card_id"]), "subheading": sub, "body": body,
                     "stars": stars, "sentences": n, "chars": len(body),
                     "story_plan": {k: p[k] for k in PLAN_FIELDS if k not in ("source_excerpt", "canonical", "path")}}
                page_cards.append(c)
            target = OUTPUT / row["path"]
            text = target.read_text(encoding="utf-8")
            marker = '</article></div><section class="related-navigation'
            if text.count(marker) != 1:
                raise SystemExit(f"bad insertion marker: {row['path']}")
            target.write_text(text.replace(marker, '</article>' + section(page_cards) + '</div><section class="related-navigation', 1), encoding="utf-8")
            for c in page_cards:
                stream.write(json.dumps(c, ensure_ascii=False) + "\n")
            stream.flush()
            cards.extend(page_cards); completed_pages += 1
            checkpoint("cards", page_id, page_cards[-1]["card"], completed_pages, len(cards))

    all_cards = sample_cards + cards
    all_cards.sort(key=lambda c: (c["canonical"], int(c["card"])))
    CARDS.write_text(json.dumps(all_cards, ensure_ascii=False, indent=2), encoding="utf-8")
    triple = Counter((p["specific_mistake"], p["correction_method"], p["ending_angle"]) for p in plans)
    checkpoint("complete", len(rows), max(int(c["card"]) for c in all_cards), len(rows), len(all_cards))
    print(json.dumps({"pages": len(rows), "cards": len(all_cards), "sample_cards_reused": len(sample_cards),
                      "new_cards": len(cards), "max_three_field_frequency": max(triple.values()),
                      "output": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
