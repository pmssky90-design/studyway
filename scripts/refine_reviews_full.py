from __future__ import annotations

import csv, hashlib, html, json, re, shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; R=ROOT/"reports"
SOURCE=ROOT/"candidate_output_reviews_full"; OUTPUT=ROOT/"candidate_output_reviews_full_refined"
CARDS_IN=R/"review-full-cards.json"; PLANS_IN=R/"review-full-story-plans.csv"; AUDIT_IN=R/"review-full-audit.json"
CARDS_OUT=R/"review-full-refined-cards.json"; PLANS_OUT=R/"review-full-refined-story-plans.csv"
TARGETS_OUT=R/"review-full-refine-targets.json"; CHANGES_OUT=R/"review-full-refine-changes.json"

TIMINGS=["처음 판단 전","첫 표시 직후","풀이 두 줄째","중간 검산에서","답 확정 직전","채점 직후","해설을 보기 전","해설을 덮은 뒤","다음 학습 시작 때"]
ANGLES=["장면 서술형","풀이 추적형","비교형","문제 해결형","재풀이 관찰형","시간 흐름형","오답 추적형","선택 근거형"]

def norm(s): return re.sub(r"[^0-9A-Za-z가-힣]","",html.unescape(s)).lower()
def sentences(s): return [x.strip() for x in re.split(r"(?<=[.!?])\s+",s) if x.strip()]
def key(c): return (c["canonical"],int(c["card"]))
def digest(s): return int(hashlib.sha256(s.encode()).hexdigest(),16)

def unique_opening(p, used, salt):
    variants=[
      f"{p['scene_type']}에 {p['first_action']}한 흔적을 따라가자 {p['missed_information']}는 지점이 먼저 드러났다.",
      f"{p['first_action']}한 뒤 남은 두 판단을 {p['scene_timing']}에 맞춰 보니 {p['specific_mistake']}가 시작된 위치가 보였다.",
      f"{p['missed_information']}는 대목을 확인한 순간, {p['scene_type']}의 첫 행동인 {p['first_action']}부터 다시 살폈다.",
      f"{p['scene_timing']}의 기록에는 {p['first_action']}한 위치와 {p['specific_mistake']}가 갈린 지점이 함께 남아 있었다.",
      f"{p['scene_type']}에서 답을 확정하기 전 {p['first_action']}한 이유와 {p['missed_information']}는 부분을 나란히 놓았다.",
      f"{p['region_or_school']} {p['page_topic']} 과정에서는 {p['scene_type']}에 {p['first_action']}한 순서부터 복원했다.",
      f"{p['first_action']}한 직후 {p['specific_mistake']}를 의심하고, {p['missed_information']}는 대목으로 시선을 돌렸다.",
      f"{p['scene_type']}의 풀이를 펼치자 {p['first_action']}한 흔적 뒤로 {p['specific_mistake']}가 이어진 과정이 확인됐다.",
    ]
    start=salt%len(variants)
    for n in range(len(variants)):
        value=variants[(start+n)%len(variants)]
        if norm(value) not in used: used.add(norm(value)); return value
    value=f"{variants[start][:-1]} 이후 {p['correction_method']} 전에 {p['verification_method']} 기준도 함께 세웠다."
    if norm(value) in used:
        value=f"{value[:-1]} 끝에는 {p['ending_angle']} 여부까지 구분했다."
    if norm(value) in used: raise SystemExit(f"opening collision: {p['canonical']} #{p['card_id']}")
    used.add(norm(value)); return value

def refined_body(c,p,used_first,high):
    old=sentences(c["body"]); opening=unique_opening(p,used_first,digest(p["canonical"]+str(p["card_id"])))
    if not high:
        return " ".join([opening]+old[1:])
    middle=[
      f"{p['region_or_school']} 기록에서 학생은 {p['student_reaction']}; 정답보다 {p['correction_method']} 순서로 어긋난 행동을 좁혔다.",
      f"{p['page_topic']} 교정 단계에서는 {p['correction_method']} 뒤 {p['verification_method']} 방식으로 판단의 재발 여부를 확인했다.",
      f"{p['region_or_school']}에서 {p['teacher_or_training_action']} 상태를 유지하자 학생이 {p['specific_mistake']}의 근거를 직접 설명했다.",
    ]
    pick=digest(p["canonical"]+"|middle|"+str(p["card_id"]))%len(middle)
    ending=f"{p['verification_method']}으로 {p['first_action']}의 변화를 확인한 뒤, {p['region_or_school']} {p['page_topic']} 기록에는 {p['ending_angle']}."
    return " ".join([opening,middle[pick],ending])

def render_section(cards):
    return '<section class="learning-case-section" aria-labelledby="learning-cases"><h2 id="learning-cases">학습 과정에서 확인한 사례</h2><div class="learning-case-grid">'+''.join(
      f'<article class="learning-case-card"><h3>{html.escape(c["subheading"])}</h3><p>{html.escape(c["body"])}</p><div class="learning-case-meta"><span class="learning-case-stars" aria-label="디자인용 별 아이콘">{c["stars"]}</span></div></article>' for c in cards)+'</div></section>'

def main():
    before=json.loads(CARDS_IN.read_text(encoding="utf-8")); audit=json.loads(AUDIT_IN.read_text(encoding="utf-8"))
    first_groups=defaultdict(list)
    for c in before: first_groups[norm(sentences(c["body"])[0])].append(key(c))
    first_targets={k for values in first_groups.values() if len(values)>1 for k in values}
    high_pairs=[]
    for pair in audit["card_similarity"]["top"]:
        if pair["similarity"]<.80: break
        a=pair["a"];b=pair["b"]; high_pairs.append((pair["similarity"],key(a),key(b)))
    high_targets={k for _,a,b in high_pairs for k in (a,b)}
    targets=first_targets|high_targets
    target_report={"first_sentence_unique_cards":len(first_targets),"high_similarity_unique_cards":len(high_targets),
      "intersection":len(first_targets&high_targets),"final_unique_targets":len(targets),"high_pairs":len(high_pairs),
      "targets":[{"canonical":k[0],"card":k[1],"first_duplicate":k in first_targets,"high_similarity":k in high_targets} for k in sorted(targets)]}
    TARGETS_OUT.write_text(json.dumps(target_report,ensure_ascii=False,indent=2),encoding="utf-8")
    with PLANS_IN.open(encoding="utf-8-sig",newline="") as f: plans=list(csv.DictReader(f))
    plan_index={(p["canonical"],int(p["card_id"])):p for p in plans}
    used_first={norm(sentences(c["body"])[0]) for c in before if key(c) not in targets}
    after=[]; changes=[]
    for c in before:
        k=key(c)
        if k not in targets: after.append(c); continue
        n=json.loads(json.dumps(c,ensure_ascii=False)); p=plan_index[k]
        if k in high_targets:
            old_t=p["scene_timing"]; old_a=p["opening_angle"]
            p["scene_timing"]=TIMINGS[(TIMINGS.index(old_t)+1+digest(p["canonical"])%8)%len(TIMINGS)]
            p["opening_angle"]=ANGLES[(ANGLES.index(old_a)+1+digest(p["canonical"]+str(p["card_id"]))%7)%len(ANGLES)]
            n["story_plan"]["scene_timing"]=p["scene_timing"];n["story_plan"]["opening_angle"]=p["opening_angle"]
        old_body=n["body"]; n["body"]=refined_body(n,p,used_first,k in high_targets)
        n["sentences"]=len(sentences(n["body"]));n["chars"]=len(n["body"])
        after.append(n);changes.append({"canonical":k[0],"card":k[1],"old_body":old_body,"new_body":n["body"],"high_similarity":k in high_targets})
    CARDS_OUT.write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding="utf-8")
    with PLANS_OUT.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(plans[0]),extrasaction="ignore");w.writeheader();w.writerows(plans)
    CHANGES_OUT.write_text(json.dumps({"changed":len(changes),"unchanged":len(after)-len(changes),"changes":changes},ensure_ascii=False,indent=2),encoding="utf-8")
    if OUTPUT.exists(): shutil.rmtree(OUTPUT)
    shutil.copytree(SOURCE,OUTPUT)
    bypath=defaultdict(list)
    for c in after: bypath[c["path"]].append(c)
    changed_paths={c["path"] for c in after if key(c) in targets}
    pattern=re.compile(r'<section class="learning-case-section".*?</section>',re.S)
    for path in changed_paths:
        target=OUTPUT/path;text=target.read_text(encoding="utf-8")
        if len(pattern.findall(text))!=1: raise SystemExit(f"bad section: {path}")
        target.write_text(pattern.sub(render_section(sorted(bypath[path],key=lambda c:int(c["card"]))),text,count=1),encoding="utf-8")
    print(json.dumps({**target_report,"changed_pages":len(changed_paths),"output":str(OUTPUT)},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
