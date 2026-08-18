from __future__ import annotations

import csv
import hashlib
import html
import json
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from audit_review_stress_500 import dup, norm, sent, sim_report, strip_fields

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
CARDS_FILE = REPORTS / "review-stress-500-v2-cards.json"
PLANS_FILE = REPORTS / "review-stress-500-v2-story-plans.csv"
AUDIT_FILE = REPORTS / "review-stress-500-v2-audit.json"
SAMPLE_FILE = REPORTS / "review-stress-500-v2-sample-150.txt"
HIGH_FILE = REPORTS / "review-stress-500-v2-high-similarity.txt"


def main() -> None:
    cards = json.loads(CARDS_FILE.read_text(encoding="utf-8"))
    with PLANS_FILE.open(encoding="utf-8-sig", newline="") as f:
        plans = list(csv.DictReader(f))

    bodies = [c["body"] for c in cards]
    headings = [c["subheading"] for c in cards]
    first = [sent(x)[0] for x in bodies]
    last = [sent(x)[-1] for x in bodies]
    duplicates = {
        "exact": dup(bodies), "normalized": dup(map(norm, bodies)),
        "region_removed": dup(strip_fields(c, ["region"]) for c in cards),
        "school_removed": dup(strip_fields(c, ["school"]) for c in cards),
        "grade_removed": dup(strip_fields(c, ["grade"]) for c in cards),
        "subject_removed": dup(strip_fields(c, ["subject"]) for c in cards),
        "all_entity_fields_removed": dup(strip_fields(c, ["region", "school", "grade", "subject"]) for c in cards),
        "subheading_exact": dup(headings), "subheading_normalized": dup(map(norm, headings)),
        "subheading_entity_removed": dup(strip_fields({**c, "body": c["subheading"]}, ["region", "school", "grade", "subject"]) for c in cards),
        "first_exact": dup(first), "first_normalized": dup(map(norm, first)),
        "last_exact": dup(last), "last_normalized": dup(map(norm, last)),
    }

    seven_fields = ["scene_type", "trigger", "first_action", "specific_mistake", "correction_method", "verification_method", "ending_angle"]
    seven = [tuple(p[k] for k in seven_fields) for p in plans]
    triples = Counter((p["specific_mistake"], p["correction_method"], p["ending_angle"]) for p in plans)
    by_page = defaultdict(list)
    for p in plans:
        by_page[p["page_id"]].append((p["scene_type"], p["specific_mistake"], p["correction_method"], p["ending_angle"]))
    story = {
        "total": len(plans), "seven_field_duplicates": dup(seven),
        "same_page_story_duplicates": sum(dup(v) for v in by_page.values()),
        "max_three_field_frequency": max(triples.values()),
        "top_100_three_field_combinations": [
            {"specific_mistake": k[0], "correction_method": k[1], "ending_angle": k[2], "count": v}
            for k, v in triples.most_common(100)
        ],
    }

    ngrams = {}
    for n in (3, 4):
        count = Counter()
        for body in bodies:
            words = body.split()
            count.update(tuple(words[i:i+n]) for i in range(len(words)-n+1))
        ngrams[str(n)] = {
            "repeated_unique": sum(v > 1 for v in count.values()),
            "repeated_excess": sum(v - 1 for v in count.values() if v > 1),
            "top100": [{"text": " ".join(k), "count": v, "category": "문법/일반" if v < 20 else "검토 필요"} for k, v in count.most_common(100) if v > 1],
        }
    phrases = Counter()
    for body in bodies:
        value = norm(body); seen = set()
        for n in range(8, 16):
            seen.update(value[i:i+n] for i in range(len(value)-n+1))
        phrases.update(seen)

    card_sim = sim_report(cards, 100, 50000)
    page_groups = defaultdict(list)
    for c in cards:
        page_groups[c["canonical"]].append(c)
    page_items = [{**items[0], "body": " ".join(x["body"] for x in items), "cards": len(items)} for items in page_groups.values()]
    page_sim = sim_report(page_items, 50, 50000)

    same_page_event = 0; same_page_correction = 0; same_page_ending = 0
    for values in by_page.values():
        same_page_event += dup((x[0], x[1]) for x in values)
        same_page_correction += dup(x[2] for x in values)
        same_page_ending += dup(x[3] for x in values)
    action_words = ["표시", "밑줄", "기록", "계산", "비교", "연결", "분리", "설명", "재풀이", "확인", "추적", "그림", "풀이"]
    abstract_words = ["독해력이 부족", "문제를 많이", "실력이 향상", "효율적으로 공부", "체계적인 학습"]
    reality = {
        "no_action_scene": sum(not c.get("story_plan", {}).get("first_action") or not c.get("story_plan", {}).get("correction_method") for c in cards),
        "abstract_only": sum(any(w in body for w in abstract_words) and not any(w in body for w in action_words) for body in bodies),
        "same_page_event": same_page_event, "same_page_correction": same_page_correction,
        "same_page_ending": same_page_ending,
    }

    lens = [len(x) for x in bodies]
    sentence_counts = Counter(len(sent(x)) for x in bodies)
    stars = Counter(c["stars"] for c in cards)
    starts = Counter(re.sub(r"\s+", " ", x)[:24] for x in first)
    endings = Counter(re.sub(r"\s+", " ", x)[-24:] for x in last)
    audit = {
        "pages": len(page_items), "cards": len(cards), "story_plan": story,
        "duplicates": duplicates, "ngrams": ngrams,
        "phrases_8_15_top100": [{"text": k, "cards": v, "category": "검토 필요" if v >= 20 else "문법/일반"} for k, v in phrases.most_common(100)],
        "opening_patterns": {"maximum": starts.most_common(1)[0][1], "top30": starts.most_common(30)},
        "ending_patterns": {"unique_ratio": round(len(set(map(norm, last))) / len(last), 4), "maximum": endings.most_common(1)[0][1], "top30": endings.most_common(30)},
        "card_similarity": {k: v for k, v in card_sim.items() if k != "_pairs"},
        "page_similarity": {k: v for k, v in page_sim.items() if k != "_pairs"},
        "reality": reality,
        "distribution": {
            "cards_per_page": Counter(x["cards"] for x in page_items), "sentence_counts": sentence_counts,
            "characters": {"min": min(lens), "max": max(lens), "mean": round(statistics.mean(lens), 2), "median": statistics.median(lens), "ge_350": sum(x >= 350 for x in lens)},
            "stars": stars,
        },
    }

    strata = defaultdict(list)
    for c in cards:
        strata[(c["kind"], c["province"], c["subject"], c["grade"])].append(c)
    for key in strata:
        strata[key].sort(key=lambda c: hashlib.sha256((c["canonical"] + str(c["card"])).encode()).hexdigest())
    sample = []
    while len(sample) < 150:
        progressed = False
        for key in sorted(strata):
            if strata[key] and len(sample) < 150:
                sample.append(strata[key].pop()); progressed = True
        if not progressed: break
    sample_lines = []
    for i, c in enumerate(sample, 1):
        plan = c["story_plan"]
        core = " | ".join(f"{k}={plan[k]}" for k in ("scene_type", "first_action", "specific_mistake", "correction_method", "verification_method", "ending_angle"))
        sample_lines += [f"[{i}] {c['canonical']}", f"카드: {c['card']}", f"STORY PLAN: {core}", f"소제목: {c['subheading']}", f"본문: {c['body']}", f"별: {c['stars']}", f"문장 수: {c['sentences']}", f"글자 수: {c['chars']}", ""]
    SAMPLE_FILE.write_text("\n".join(sample_lines), encoding="utf-8")

    high = []
    for score, i, j in card_sim["_pairs"]:
        if score < .65: break
        a, b = cards[i], cards[j]
        high += [f"[유사도 {score:.4f}]", f"A: {a['canonical']} / 카드 {a['card']}", a["subheading"], a["body"], f"B: {b['canonical']} / 카드 {b['card']}", b["subheading"], b["body"], ""]
    HIGH_FILE.write_text("\n".join(high) if high else "0.65 이상 카드 쌍 없음", encoding="utf-8")

    hard_fail = story["seven_field_duplicates"] or duplicates["exact"] or duplicates["normalized"] or duplicates["school_removed"] or duplicates["all_entity_fields_removed"] or duplicates["subheading_exact"] or duplicates["first_exact"] or card_sim["ge_080"] or page_sim["ge_070"] or reality["no_action_scene"] or reality["abstract_only"] or reality["same_page_event"] or reality["same_page_ending"]
    review = card_sim["ge_070"] > 25 or card_sim["ge_075"] > 5 or duplicates["last_normalized"] > 5 or reality["same_page_correction"] > 10
    audit["verdict"] = "FAIL" if hard_fail else "REVIEW" if review else "PASS"
    AUDIT_FILE.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pages": audit["pages"], "cards": audit["cards"], "story_plan": story,
                      "duplicates": duplicates, "card_similarity": {k:v for k,v in card_sim.items() if k not in ("_pairs", "top")},
                      "page_similarity": {k:v for k,v in page_sim.items() if k not in ("_pairs", "top")},
                      "reality": reality, "distribution": audit["distribution"], "verdict": audit["verdict"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
