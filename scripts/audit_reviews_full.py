from __future__ import annotations

import csv, hashlib, html, json, os, re, statistics, zlib
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "reports"
CARDS = Path(os.environ.get("STUDYWAY_REVIEW_CARDS", R / "review-full-cards.json"))
PLANS = Path(os.environ.get("STUDYWAY_REVIEW_PLANS", R / "review-full-story-plans.csv"))
AUDIT = Path(os.environ.get("STUDYWAY_REVIEW_AUDIT", R / "review-full-audit.json"))
HIGH = Path(os.environ.get("STUDYWAY_REVIEW_HIGH", R / "review-full-high-similarity.txt"))
SAMPLE = Path(os.environ.get("STUDYWAY_REVIEW_SAMPLE", R / "review-full-sample-300.txt"))

def norm(s): return re.sub(r"[^0-9A-Za-z가-힣]", "", html.unescape(s)).lower()
def sent(s): return [x.strip() for x in re.split(r"(?<=[.!?])\s+", s) if x.strip()]
def dup(values): return sum(v - 1 for v in Counter(values).values() if v > 1)
def strip_fields(c, fields, key="body"):
    s = c[key]
    for f in fields:
        if c.get(f): s = s.replace(c[f], "")
    return norm(s)

def similarity(items, topn=500):
    texts = [norm(x["body"]) for x in items]
    sets = [{x[i:i+3] for i in range(max(1, len(x)-2))} for x in texts]
    buckets = defaultdict(list)
    for i, grams in enumerate(sets):
        sig = sorted(zlib.crc32(g.encode("utf-8")) for g in grams)[:8]
        sig += [0] * (8-len(sig))
        length_bin = len(texts[i]) // 32
        for band in range(4):
            buckets[(band, length_bin, sig[band*2], sig[band*2+1])].append(i)
    candidates = set()
    for ids in buckets.values():
        if 1 < len(ids) <= 1000:
            for x in range(len(ids)):
                for y in range(x): candidates.add((ids[y], ids[x]))
    pairs = []
    for i, j in candidates:
        if min(len(texts[i]), len(texts[j])) / max(len(texts[i]), len(texts[j])) < .58: continue
        score = 2 * len(sets[i] & sets[j]) / (len(sets[i]) + len(sets[j]))
        if score >= .55: pairs.append((score, i, j))
    pairs.sort(reverse=True)
    levels = {f"ge_{int(t*100):03d}": sum(x[0] >= t for x in pairs) for t in (.60,.65,.70,.75,.80,.85,.90)}
    return {"method":"bottom-k CRC32 character-trigram LSH + exact character-trigram Dice",
            "candidate_pairs":len(candidates), "scored_pairs":len(pairs),
            "maximum":round(pairs[0][0],4) if pairs else 0, **levels,
            "top":[{"similarity":round(s,4),"a":items[i],"b":items[j]} for s,i,j in pairs[:topn]], "_pairs":pairs}

def main():
    cards = json.loads(CARDS.read_text(encoding="utf-8"))
    with PLANS.open(encoding="utf-8-sig", newline="") as f: plans = list(csv.DictReader(f))
    bodies=[c["body"] for c in cards]; headings=[c["subheading"] for c in cards]
    first=[sent(x)[0] for x in bodies]; last=[sent(x)[-1] for x in bodies]
    duplicates={
        "exact":dup(bodies), "normalized":dup(map(norm,bodies)),
        "region_removed":dup(strip_fields(c,["region"]) for c in cards),
        "school_removed":dup(strip_fields(c,["school"]) for c in cards),
        "grade_removed":dup(strip_fields(c,["grade"]) for c in cards),
        "subject_removed":dup(strip_fields(c,["subject"]) for c in cards),
        "all_entity_fields_removed":dup(strip_fields(c,["region","school","grade","subject"]) for c in cards),
        "subheading_exact":dup(headings), "subheading_normalized":dup(map(norm,headings)),
        "subheading_entity_removed":dup(strip_fields(c,["region","school","grade","subject"],"subheading") for c in cards),
        "first_exact":dup(first), "first_normalized":dup(map(norm,first)),
        "last_exact":dup(last), "last_normalized":dup(map(norm,last)),
    }
    seven_fields=("scene_type","trigger","first_action","specific_mistake","correction_method","verification_method","ending_angle")
    triples=Counter((p["specific_mistake"],p["correction_method"],p["ending_angle"]) for p in plans)
    bypage=defaultdict(list)
    for p in plans: bypage[p["canonical"]].append(p)
    event_dup=sum(dup((p["scene_type"],p["specific_mistake"]) for p in ps) for ps in bypage.values())
    correction_dup=sum(dup(p["correction_method"] for p in ps) for ps in bypage.values())
    ending_dup=sum(dup(p["ending_angle"] for p in ps) for ps in bypage.values())
    story={"total":len(plans),"seven_field_duplicates":dup(tuple(p[k] for k in seven_fields) for p in plans),
           "max_three_field_frequency":max(triples.values()),"same_page_event":event_dup,
           "same_page_correction":correction_dup,"same_page_ending":ending_dup,
           "top_100_three_field_combinations":[{"values":k,"count":v} for k,v in triples.most_common(100)]}
    ngrams={}; phrase_candidates=Counter()
    for n in (3,4):
        count=Counter()
        for body in bodies:
            words=body.split(); count.update(tuple(words[i:i+n]) for i in range(len(words)-n+1))
        ngrams[str(n)]={"repeated_unique":sum(v>1 for v in count.values()),"repeated_excess":sum(v-1 for v in count.values() if v>1),
                        "top200":[{"text":" ".join(k),"count":v,"category":"검토 필요" if v>=100 else "문법/일반"} for k,v in count.most_common(200)]}
        for k,v in count.most_common(2000):
            text=" ".join(k)
            if 8 <= len(norm(text)) <= 15: phrase_candidates[text]=max(phrase_candidates[text],v)
    print("card similarity", flush=True)
    card_sim=similarity(cards,500)
    page_items=[]
    cardpages=defaultdict(list)
    for c in cards: cardpages[c["canonical"]].append(c)
    for cs in cardpages.values(): page_items.append({**cs[0],"body":" ".join(c["body"] for c in cs),"cards":len(cs)})
    print("page similarity", flush=True)
    page_sim=similarity(page_items,500)
    action=["표시","밑줄","기록","계산","비교","연결","분리","설명","재풀이","확인","추적","그림","풀이"]
    abstract=["독해력이 부족","문제를 많이","실력이 향상","효율적으로 공부","체계적인 학습"]
    reality={"no_action_scene":sum(not c["story_plan"].get("first_action") or not c["story_plan"].get("correction_method") for c in cards),
             "abstract_only":sum(any(w in b for w in abstract) and not any(w in b for w in action) for b in bodies),
             "same_page_event":event_dup,"same_page_correction":correction_dup,"same_page_ending":ending_dup,
             "top_events":Counter(p["scene_type"] for p in plans).most_common(30),
             "top_corrections":Counter(p["correction_method"] for p in plans).most_common(30),
             "top_endings":Counter(p["ending_angle"] for p in plans).most_common(30)}
    group={}
    for field in ("kind","subject","grade","province","type"):
        group[field]={}
        for key in sorted({c[field] for c in cards}):
            subset=[c for c in cards if c[field]==key]
            group[field][key]={"cards":len(subset),"exact":dup(c["body"] for c in subset),
                               "normalized":dup(norm(c["body"]) for c in subset)}
    lens=[len(x) for x in bodies]; sc=Counter(len(sent(x)) for x in bodies)
    distribution={"cards_per_page":Counter(len(x) for x in cardpages.values()),"sentence_counts":sc,
      "characters":{"min":min(lens),"max":max(lens),"mean":round(statistics.mean(lens),2),"median":statistics.median(lens),
                    "100_144":sum(100<=x<=144 for x in lens),"145_205":sum(145<=x<=205 for x in lens),
                    "206_280":sum(206<=x<=280 for x in lens),"281_plus":sum(x>=281 for x in lens)},"stars":Counter(c["stars"] for c in cards)}
    starts=Counter(re.sub(r"\s+"," ",x)[:24] for x in first); ends=Counter(re.sub(r"\s+"," ",x)[-24:] for x in last)
    audit={"pages":len(cardpages),"cards":len(cards),"story_plan":story,"duplicates":duplicates,"ngrams":ngrams,
           "phrases_8_15_top200":[{"text":k,"cards":v} for k,v in phrase_candidates.most_common(200)],
           "opening_patterns":{"maximum":starts.most_common(1)[0][1],"top100":starts.most_common(100)},
           "ending_patterns":{"maximum":ends.most_common(1)[0][1],"top100":ends.most_common(100)},
           "card_similarity":{k:v for k,v in card_sim.items() if k!="_pairs"},
           "page_similarity":{k:v for k,v in page_sim.items() if k!="_pairs"},"groups":group,"reality":reality,"distribution":distribution}
    # Deterministic round-robin stratified sample.
    strata=defaultdict(list)
    for c in cards: strata[(c["kind"],c["province"],c["subject"],c["grade"])].append(c)
    for values in strata.values(): values.sort(key=lambda c:hashlib.sha256((c["canonical"]+str(c["card"])).encode()).hexdigest())
    sample=[]
    while len(sample)<300:
        for key in sorted(strata):
            if strata[key] and len(sample)<300: sample.append(strata[key].pop())
    lines=[]
    for i,c in enumerate(sample,1):
        p=c["story_plan"]; core=" | ".join(f"{k}={p[k]}" for k in ("scene_type","first_action","specific_mistake","correction_method","verification_method","ending_angle"))
        lines += [f"[{i}] {c['kind']} / {c['province']} / {c['subject']} / {c['grade']}",f"페이지: {c['canonical']}",f"카드: {c['card']}",f"STORY PLAN: {core}",f"소제목: {c['subheading']}",f"본문: {c['body']}",f"별: {c['stars']}",f"문장 수: {c['sentences']} / 글자 수: {c['chars']}",""]
    SAMPLE.write_text("\n".join(lines),encoding="utf-8")
    high=[]
    for score,i,j in card_sim["_pairs"][:500]:
        if score<.70: break
        a,b=cards[i],cards[j]; high += [f"[유사도 {score:.4f}]",f"A: {a['canonical']} / 카드 {a['card']}",a["subheading"],a["body"],f"B: {b['canonical']} / 카드 {b['card']}",b["subheading"],b["body"],""]
    HIGH.write_text("\n".join(high) if high else "0.70 이상 카드 쌍 없음",encoding="utf-8")
    hard=story["seven_field_duplicates"] or duplicates["exact"] or duplicates["normalized"] or duplicates["subheading_exact"] or duplicates["first_exact"] or card_sim["ge_080"] or page_sim["ge_070"] or reality["no_action_scene"] or reality["abstract_only"] or event_dup or ending_dup
    review=duplicates["all_entity_fields_removed"] or duplicates["last_normalized"] or card_sim["ge_070"] or correction_dup
    audit["verdict"]="FAIL" if hard else "REVIEW" if review else "PASS"
    AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"pages":len(cardpages),"cards":len(cards),"story":story,"duplicates":duplicates,
      "card_similarity":{k:v for k,v in card_sim.items() if k not in ("_pairs","top")},
      "page_similarity":{k:v for k,v in page_sim.items() if k not in ("_pairs","top")},"reality":reality,"distribution":distribution,"verdict":audit["verdict"]},ensure_ascii=False,indent=2))

if __name__ == "__main__": main()
