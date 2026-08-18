from __future__ import annotations

import hashlib, html, json, re, shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];R=ROOT/"reports"
SOURCE=ROOT/"candidate_output_reviews_full_refined";OUTPUT=ROOT/"candidate_output_reviews_natural_language_pilot"
CARDS_IN=R/"review-full-refined-cards.json";CARDS_OUT=R/"review-natural-language-pilot-cards.json"
REPORT=R/"review-natural-language-pilot-100.txt";META=R/"review-natural-language-pilot-meta.json"

def fix(s):
    try:return s.encode("latin1").decode("cp949")
    except (UnicodeEncodeError,UnicodeDecodeError):return s
def norm(s):return re.sub(r"[^0-9A-Za-z가-힣]","",html.unescape(s)).lower()
def sent(s):return [x.strip() for x in re.split(r"(?<=[.!?])\s+",s) if x.strip()]
def key(c):return(c["canonical"],int(c["card"]))
def h(s):return int(hashlib.sha256(s.encode()).hexdigest(),16)

TITLE={
"역접 뒤 주장 누락":["역접 뒤에서 놓친 글의 방향","그러나 뒤 문장을 다시 읽은 이유"],"지시 대상 오인":["지시어가 가리킨 대상을 잘못 본 경우","대명사를 바로 앞 단어에만 연결한 문제"],
"주절과 관계절 혼동":["관계절을 중심 문장으로 읽은 경우","주절 동사를 다시 표시한 이유"],"사례를 주장으로 확대":["한 사례를 글 전체 주장으로 본 경우","예시와 중심 주장을 다시 나눈 과정"],
"선지 강도 과장":["일부를 전부로 바꿔 읽은 선지","선지의 표현 범위를 다시 비교한 이유"],"부분 소재를 제목으로 선택":["반복된 소재만 보고 고른 제목","글의 중심보다 눈에 띈 단어를 고른 경우"],
"빈칸 뒤 근거 누락":["빈칸 앞 문장만 읽고 고른 답","빈칸 뒤 근거를 놓친 문제"],"연결어 하나에 의존":["연결어 하나만 보고 정한 글의 순서","문장 연결을 다시 따라간 이유"],
"배경지식 개입":["본문보다 익숙한 상식을 믿은 답","아는 내용 때문에 놓친 글의 근거"],"주체 변경 누락":["문장 속 주체가 바뀐 것을 놓친 경우","행위자를 다시 표시하고 찾은 답"],
"부정 표현 누락":["부정어를 빼고 읽어 달라진 답","제한 표현을 다시 표시한 이유"],"범위 제한 삭제":["only의 범위를 놓친 선지 비교","제한하는 대상을 다시 연결한 과정"],
"인과 방향 반전":["원인과 결과를 거꾸로 읽은 문장","인과 관계를 다시 그린 이유"],"대조 대상 혼선":["두 집단의 특징을 바꾸어 적은 경우","대조 대상을 나란히 놓고 찾은 오류"],
"예외 문장 생략":["마지막 예외 문장을 놓친 답","일반 규칙과 예외를 다시 나눈 과정"],"대명사 수 불일치 누락":["복수 대상을 단수로 연결한 문장","대명사의 수를 다시 확인한 이유"],
"끝점 누락":["끝점을 빠뜨린 최댓값 풀이","경계값을 다시 대입한 이유"],"정의역 누락":["정의역 밖의 값을 포함한 계산","식을 쓰기 전에 정의역을 적은 이유"],
"부호 반전":["부등호를 옮기며 놓친 부호","계산 줄마다 부호를 다시 본 이유"],"교점 하나 누락":["그래프의 한쪽 교점을 놓친 풀이","두 가지를 나누어 찾은 교점"],
"절댓값 처리 누락":["절댓값 구간을 나누지 않은 미분","부호가 바뀌는 지점을 먼저 찾은 이유"],"합성 순서 반대":["합성함수의 안팎을 바꾸어 계산한 경우","함수 적용 순서를 다시 적은 과정"],
"부분합을 일반항으로 사용":["부분합을 그대로 일반항으로 쓴 풀이","두 부분합의 차를 다시 계산한 이유"],"로그 진수 조건 누락":["로그 계산에서 빠진 양수 조건","진수 조건을 해집합과 함께 본 이유"],
"좌우극한 합침":["좌극한과 우극한을 한 번에 계산한 경우","두 방향의 극한을 따로 적은 이유"],"도함수 0을 바로 극값으로 판단":["도함수가 0인 점을 바로 극값으로 본 경우","부호 변화를 확인하고 고른 극값"],
"속도와 거리 혼동":["속도를 그대로 더해 구한 이동거리","방향과 거리를 나누어 계산한 이유"],"필요충분 방향 반대":["명제의 역을 원래 조건으로 쓴 풀이","조건의 방향을 화살표로 다시 본 이유"],
"중복근 횟수 오인":["접점을 두 교점으로 센 그래프","중복근의 개수를 다시 확인한 이유"],"매개변수 범위 누락":["해의 개수만 보고 끝낸 매개변수 문제","계수 범위까지 다시 적은 이유"],
"공차와 항 번호 혼선":["첫째항의 번호를 잘못 넣은 수열","항 번호를 다시 적고 찾은 공차"],"확률 표본공간 누락":["순서를 나누지 않아 빠진 확률 경우","표본공간을 먼저 펼쳐 본 이유"],
"계획 시간 과다":["이동 시간을 빼고 세운 공부 계획","실제 가능한 시간으로 다시 나눈 하루"],"귀가시간 미반영":["귀가 전부터 시작된 학습 계획","책상에 앉는 시각을 다시 적은 이유"],
"오답 재풀이 없음":["오답노트에 답만 적었던 경우","틀린 이유를 남기고 다시 푼 문제"],"과제 우선순위 충돌":["마감일보다 쉬운 과제를 먼저 한 경우","과제 순서를 다시 정한 기준"],
"한 과목 과몰입":["한 문제에 복습 시간을 모두 쓴 날","막힌 문제에서 멈출 시간을 정한 이유"],"시험범위 배분 실패":["큰 단원을 마지막 날에 몰아둔 계획","시험 범위를 다시 나눈 뒤 달라진 순서"],
"수행평가 일정 충돌":["수행평가와 시험 공부가 겹친 계획","제출일을 먼저 표시하고 바꾼 일정"],"복습 시점 지연":["일주일 뒤에야 다시 펼친 단원","다음 복습 날짜를 바로 적은 이유"],
"완료 기준 불명확":["읽기만 하고 끝냈다고 표시한 과제","설명할 수 있는지 확인한 완료 기준"],"이월 분량 누적":["못한 일을 그대로 다음 날로 옮긴 계획","남은 분량을 줄여 다시 세운 일정"],
"기록 없는 반복":["같은 문제를 다시 풀고도 남지 않은 기록","두 번째 풀이에서 달라진 점을 적은 이유"],"난도 순서 고정":["집중이 흐려져도 어려운 문제부터 푼 경우","시간대에 맞춰 바꾼 문제 순서"],
"교재 전환 과다":["한 단원에서 교재를 자주 바꾼 경우","한 자료를 끝까지 확인한 뒤의 변화"],"검산 시간 미확보":["시험 막판에 사라진 검산","풀이 전에 확인 시간을 남긴 이유"],
"목표 단위 과대":["하루에 끝내기 어려운 목표를 적은 계획","학습 목표를 작은 단위로 다시 나눈 이유"],"맞힌 문제 복기 생략":["맞힌 문제를 다시 본 이유","답은 맞았지만 근거가 비어 있던 문제"]}

CORRECTION={
"최초 오류가 난 줄만 다시 계산":"풀이를 모두 지우지 않고 처음 어긋난 줄부터 다시 계산했습니다.","이전 풀이와 수정 풀이를 나란히 비교":"처음 쓴 풀이와 고친 풀이를 나란히 놓고 달라진 부분을 찾았습니다.",
"조건별 체크칸을 만들어 누락을 확인":"조건 옆에 작은 확인 칸을 만들고 빠진 항목이 없는지 살폈습니다.","판단의 전후 관계를 표로 분리":"앞에서 확인한 내용과 뒤에서 판단할 내용을 두 칸으로 나누었습니다.",
"좌우 또는 앞뒤 계산을 두 칸으로 분리":"서로 다른 두 경우를 한 줄에 섞지 않고 두 칸에 따로 계산했습니다.","가능한 후보를 먼저 표에 기록":"가능한 답을 먼저 표에 적은 뒤 조건에 맞지 않는 것부터 지웠습니다.",
"선택 근거가 있는 문장 번호를 옆에 기록":"답 옆에 근거가 나온 문장 번호를 함께 적었습니다.","지시 표현과 실제 대상을 선으로 연결":"지시어와 가리키는 대상을 선으로 이어 관계를 확인했습니다.",
"중심이 되는 식이나 주절만 다시 작성":"주변 설명은 잠시 두고 중심 식이나 주절만 한 줄로 다시 썼습니다.","답을 고른 이유를 한 줄로 제한":"답을 고른 이유를 한 문장으로 적어 근거가 흐려지지 않게 했습니다.",
"결과 대신 처음 어긋난 행동을 오답란에 기록":"오답란에는 틀린 답 대신 처음 판단이 어긋난 행동을 적었습니다.","문제가 요구한 값을 별도 칸에 표시":"계산을 시작하기 전에 문제에서 구하라는 값을 별도 칸에 표시했습니다.",
"첫 풀이와 다른 시간 제한으로 재시도":"두 번째 풀이에는 짧은 제한 시간을 두고 같은 순서를 지킬 수 있는지 확인했습니다.","핵심 조건 일부를 가린 채 순서를 복원":"핵심 조건을 잠시 가린 뒤 풀이 순서를 스스로 다시 떠올렸습니다.",
"수치 또는 소재 하나만 바꾸어 즉시 재풀이":"숫자나 소재 하나만 바꾼 문제를 바로 풀어 같은 실수가 남았는지 확인했습니다.","다음 날 표시 없는 원문으로 재풀이":"다음 날에는 표시가 없는 문제를 펼쳐 처음부터 다시 풀었습니다.",
"사용하지 않은 조건을 역으로 점검":"풀이에 쓰지 않은 조건이 무엇인지 마지막 식에서 거꾸로 확인했습니다.","교사 설명 없이 학생이 오류 위치를 말로 재현":"해설을 듣기 전에 어느 줄에서 판단이 달라졌는지 직접 설명해 보았습니다.",
"마지막 판단부터 거꾸로 근거를 추적":"마지막에 고른 답부터 시작해 근거가 나온 문장이나 계산 줄을 거꾸로 찾았습니다.","정답을 가리고 풀이의 위험한 한 줄만 찾기":"정답을 가린 채 다시 틀릴 가능성이 큰 한 줄만 골라 표시했습니다."}

VERIFY={"같은 문제를 표시 없이 다시 풂":"표시를 지운 같은 문제를 다시 풀어 보니","숫자만 달라진 문항에 적용":"숫자만 바꾼 문항에도 같은 방법을 써 보니","조건 하나를 삭제한 경우와 비교":"조건 하나를 뺀 경우와 나란히 비교하니","제한 조건을 하나 추가해 다시 판단":"제한 조건을 하나 더 넣고 다시 판단하니","선지나 보기 순서를 바꾸어 재확인":"선지 순서를 바꾸어 다시 확인하니","소재가 달라진 새 지문에 적용":"소재가 다른 지문에도 같은 읽기 순서를 적용하니","처음보다 짧은 시간 안에 풀이":"처음보다 짧은 시간을 정해 다시 풀어 보니","답 없이 풀이 과정만 설명":"답을 말하지 않고 풀이 과정만 설명해 보니","완성된 풀이에서 최초 오류만 탐색":"완성된 풀이에서 처음 어긋난 부분만 찾아보니","정답을 가린 채 근거만 설명":"정답을 가리고 선택 근거만 말해 보니","두 가지 풀이의 첫 차이를 비교":"두 풀이가 처음 달라진 지점을 비교하니","결론에서 조건을 역으로 복원":"마지막 결론부터 필요한 조건을 거꾸로 찾아보니","그래프만 보고 식의 변화 예상":"그래프만 보고 식이 어떻게 달라질지 예상해 보니","식만 보고 그래프의 모양 설명":"식만 보고 그래프 모양을 설명해 보니","다음 날 빈 종이에 핵심 순서 재현":"다음 날 빈 종이에 풀이 순서를 다시 적어 보니","맞힌 문제에서도 위험한 단계를 표시":"맞힌 문제에서도 다시 틀릴 만한 단계를 표시하니","유사 문항 두 개의 조건 차이를 설명":"비슷한 두 문항의 조건 차이를 말해 보니","교재를 덮고 선택을 바꾼 이유를 말함":"교재를 덮고 답을 바꾼 이유를 말해 보니"}
END={"학생이 최초 오류를 직접 특정":"어느 부분에서 판단이 처음 달라졌는지 스스로 짚을 수 있었습니다.","풀이의 첫 줄이 이전과 달라짐":"이전과 다른 첫 줄로 풀이를 시작했습니다.","전체 계산을 지우지 않고 문제 줄만 고침":"계산 전체가 아니라 문제가 된 줄만 고쳤습니다.","근거 위치를 답보다 먼저 찾음":"답을 고르기 전에 근거가 있는 위치부터 찾았습니다.","끝점과 예외가 후보표에 함께 들어감":"후보표에 끝점과 예외 조건을 함께 적었습니다.","답을 바꾸기 전에 이유를 남김":"답을 바꾸기 전에 그 이유를 한 줄로 남겼습니다.","검산 범위를 좁혀 제한시간 안에 마침":"확인할 범위를 좁혀 정해 둔 시간 안에 마쳤습니다.","맞힌 문제에서도 위험한 줄을 발견":"맞힌 문제에서도 다시 틀릴 수 있는 줄을 찾아냈습니다.","새 조건에 맞춰 다른 식을 세움":"달라진 조건에 맞는 식을 새로 세웠습니다.","오답노트의 기록 기준을 결과에서 과정으로 바꿈":"오답노트에는 결과보다 틀리기 시작한 과정을 남겼습니다.","사용하지 않은 정보를 스스로 찾아냄":"풀이에 쓰지 않은 조건을 스스로 찾아냈습니다.","다음 풀이에서 같은 첫 행동을 반복하지 않음":"다음 풀이에서는 처음과 같은 실수를 되풀이하지 않았습니다.","설명 중 판단이 갈린 지점을 바로 짚음":"설명하면서 판단이 갈린 지점을 바로 찾아냈습니다.","새 문항에서 확인 순서를 끝까지 유지":"새 문제에서도 정한 확인 순서를 끝까지 지켰습니다.","수정 전후 풀이의 차이를 한 문장으로 정리":"고치기 전과 뒤의 차이를 한 문장으로 정리했습니다.","정답 확인 없이도 선택 범위를 좁힘":"정답을 보지 않고도 가능한 선택지를 줄일 수 있었습니다."}

def category(c):
    kind=fix(c["kind"]);subject=fix(c["subject"]);province=fix(c["province"]);grade=fix(c["grade"])
    return kind,subject,province,grade
def bucket(c):
    kind,subject,province,grade=category(c)
    group=("지역" if kind=="region" else "학교")+("일반" if subject not in ("영어","수학") else subject)
    prov="서울" if "서울" in province else "경기"
    high=grade if grade in ("고1","고2","고3") else "기타"
    return group,prov,high
def select(cards):
    awkward=[c for c in cards if "·" in c["subheading"]]
    awkward.sort(key=lambda c:(h(c["canonical"]+str(c["card"])),c["canonical"],c["card"]))
    groups=defaultdict(list)
    for c in awkward:
        if bucket(c)[0] in ("지역일반","지역영어","지역수학","학교영어","학교수학"):groups[bucket(c)].append(c)
    chosen=[];pages=set();wanted=["지역일반","지역영어","지역수학","학교영어","학교수학"]
    for group in wanted:
      for prov in ("서울","경기"):
       for grade in ("고1","고2","고3","기타"):
        pool=groups[(group,prov,grade)]
        take=3 if grade in ("고1","고2") else 2
        for c in pool:
          if c["canonical"] not in pages and len([x for x in chosen if bucket(x)==(group,prov,grade)])<take:
            chosen.append(c);pages.add(c["canonical"])
    # Round-robin fills sparse school/grade combinations while preserving all major strata.
    pools=defaultdict(list)
    for c in awkward:pools[(bucket(c)[0],bucket(c)[1])].append(c)
    while len(chosen)<100:
      moved=False
      for k in sorted(pools):
       while pools[k] and pools[k][0]["canonical"] in pages:pools[k].pop(0)
       if pools[k] and len(chosen)<100:
        c=pools[k].pop(0);chosen.append(c);pages.add(c["canonical"]);moved=True
      if not moved:break
    return chosen[:100]

def rewrite(c,index,used_titles,used_first,used_last):
    p=c["story_plan"];mistake=p["specific_mistake"];options=TITLE.get(mistake,[f"{mistake}를 다시 확인한 이유",f"{mistake}가 드러난 풀이"])
    title=options[h(c["canonical"]+str(c["card"]))%len(options)]
    if norm(title) in used_titles:
        prefix={"영어":"문장을 다시 읽으며 ","수학":"계산을 다시 보며 ","일반":"계획을 다시 세우며 "}.get(fix(c["subject"]),"과정을 다시 보며 ")
        title=(prefix+options[(h(c["canonical"])+1)%len(options)]).replace("  "," ")
    if len(title)>28:title=options[0][:28].rstrip()
    if norm(title) in used_titles:title=(p["scene_type"].replace("할 때","").replace("한 순간","")+" "+options[0])[:28].rstrip()
    if norm(title) in used_titles:raise SystemExit(f"title collision {key(c)}")
    used_titles.add(norm(title))
    missed=p["missed_information"].rstrip(".")+"."
    subject=fix(c["subject"])
    openings={"영어":[f"고른 답과 근거 문장을 나란히 놓고 보니 {missed}",f"선지를 지운 순서부터 다시 따라가 보니 {missed}",f"정답을 가리고 지문을 다시 읽자 {missed}",f"본문에 남은 표시를 차례로 확인해 보니 {missed}"],"수학":[f"계산 줄을 처음부터 다시 따라가 보니 {missed}",f"풀이를 멈춘 지점부터 살펴보니 {missed}",f"정답을 가리고 식을 다시 확인하자 {missed}",f"조건과 계산 결과를 나란히 놓고 보니 {missed}"],"일반":[f"계획표와 실제 사용 시간을 비교해 보니 {missed}",f"완료하지 못한 일을 다시 펼쳐 보니 {missed}",f"공부를 시작한 시각부터 되짚어 보니 {missed}",f"남은 과제와 시험 일정을 함께 적어 보니 {missed}"]}.get(subject,[f"과정을 처음부터 다시 살펴보니 {missed}"])
    opening=openings[h(c["canonical"]+"open"+str(c["card"]))%len(openings)]
    if norm(opening) in used_first:opening=f"{p['scene_type']}의 기록을 펼쳐 보니 {missed}"
    if norm(opening) in used_first:opening=f"{p['first_action']}한 흔적부터 따라가자 {missed}"
    if norm(opening) in used_first:raise SystemExit(f"opening collision {key(c)}")
    used_first.add(norm(opening))
    actions={"영어":["근거가 나온 문장과 고른 선지를 나란히 놓고 판단이 달라진 곳을 표시했습니다.","정답은 가린 채 주절과 조건 표현에 다시 밑줄을 그었습니다.","두 선지의 표현 범위를 비교하고 본문에서 근거 문장을 다시 찾았습니다.","처음 읽은 순서를 적은 뒤 놓친 문장부터 천천히 다시 읽었습니다."],"수학":["계산을 모두 지우지 않고 조건이 빠진 줄부터 다시 써 보았습니다.","가능한 값을 먼저 적고 정의역과 끝점 조건을 하나씩 대입했습니다.","한 줄에 섞여 있던 두 경우를 나누어 부호와 계산 결과를 비교했습니다.","문제에서 구하라는 값에 먼저 동그라미를 치고 식을 다시 세웠습니다."],"일반":["실제로 사용할 수 있는 시간과 남은 일을 다시 적어 하루 분량을 줄였습니다.","마감일과 예상 시간을 따로 표시한 뒤 할 일의 순서를 다시 정했습니다.","끝냈다는 표시 대신 스스로 설명할 수 있는지를 완료 기준으로 삼았습니다.","다음 날로 넘길 일은 그대로 옮기지 않고 필요한 분량부터 다시 나누었습니다."]}.get(subject,[CORRECTION[p["correction_method"]]])
    correction=actions[h(c["canonical"]+"action"+str(c["card"]))%len(actions)]
    ending=VERIFY[p["verification_method"]]+", "+END[p["ending_angle"]]
    if norm(ending) in used_last:ending=p["scene_type"]+"와 비슷한 상황에서 "+ending
    if norm(ending) in used_last:ending=p["specific_mistake"]+"를 고친 뒤 "+ending
    if norm(ending) in used_last:raise SystemExit(f"ending collision {key(c)}")
    used_last.add(norm(ending));body=" ".join((opening,correction,ending))
    return title,body

def render(cards):
 return '<section class="learning-case-section" aria-labelledby="learning-cases"><h2 id="learning-cases">학습 과정에서 확인한 사례</h2><div class="learning-case-grid">'+''.join(f'<article class="learning-case-card"><h3>{html.escape(c["subheading"])}</h3><p>{html.escape(c["body"])}</p><div class="learning-case-meta"><span class="learning-case-stars" aria-label="디자인용 별 아이콘">{c["stars"]}</span></div></article>' for c in cards)+'</div></section>'

def main():
 cards=json.loads(CARDS_IN.read_text(encoding="utf-8"));chosen=select(cards);targets={key(c) for c in chosen}
 used_titles={norm(c["subheading"]) for c in cards if key(c) not in targets};used_first={norm(sent(c["body"])[0]) for c in cards if key(c) not in targets};used_last={norm(sent(c["body"])[-1]) for c in cards if key(c) not in targets}
 changes=[];after=[]
 for i,c in enumerate(cards):
  if key(c) not in targets:after.append(c);continue
  n=json.loads(json.dumps(c,ensure_ascii=False));title,body=rewrite(n,i,used_titles,used_first,used_last);changes.append({"page":c["canonical"],"card":c["card"],"old_title":c["subheading"],"new_title":title,"old_body":c["body"],"new_body":body,"stratum":bucket(c)});n["subheading"]=title;n["body"]=body;n["sentences"]=len(sent(body));n["chars"]=len(body);after.append(n)
 if OUTPUT.exists():shutil.rmtree(OUTPUT)
 shutil.copytree(SOURCE,OUTPUT);bypath=defaultdict(list)
 for c in after:bypath[c["path"]].append(c)
 pattern=re.compile(r'<section class="learning-case-section".*?</section>',re.S)
 for c in chosen:
  target=OUTPUT/c["path"];text=target.read_text(encoding="utf-8");target.write_text(pattern.sub(render(sorted(bypath[c["path"]],key=lambda x:int(x["card"]))),text,count=1),encoding="utf-8")
 CARDS_OUT.write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding="utf-8")
 lines=[]
 for i,x in enumerate(changes,1):lines += [f"[{i}] {x['page']}",f"카드: {x['card']}",f"기존 제목: {x['old_title']}",f"새 제목: {x['new_title']}",f"기존 본문: {x['old_body']}",f"새 본문: {x['new_body']}",""]
 REPORT.write_text("\n".join(lines),encoding="utf-8")
 reps=[]
 for group in ("지역일반","지역영어","지역수학","학교영어","학교수학"):
  reps += [x["page"] for x in changes if x["stratum"][0]==group][:4]
 meta={"cards":100,"pages":len({x['page'] for x in changes}),"strata":[{"group":k[0],"province":k[1],"grade":k[2],"cards":v} for k,v in Counter(tuple(x["stratum"]) for x in changes).items()],"representative_urls":reps,"changes":changes}
 META.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"cards":len(changes),"pages":len({x['page'] for x in changes}),"representative_urls":reps,"output":str(OUTPUT)},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
