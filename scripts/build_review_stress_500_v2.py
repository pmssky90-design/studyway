from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_images_mobile_dom_full_bleed_aligned_cards"
OUTPUT = ROOT / "candidate_output_review_stress_500_v2"
REPORTS = ROOT / "reports"
PAGES_CSV = REPORTS / "review-stress-500-pages.csv"
PLANS_CSV = REPORTS / "review-stress-500-v2-story-plans.csv"
CARDS_JSON = REPORTS / "review-stress-500-v2-cards.json"

SCENES = [
    "시험지를 받은 직후", "첫 페이지를 넘긴 때", "시험 중반의 선택", "종료 18분 전",
    "종료 7분 전", "숙제를 펴자마자", "숙제 마지막 문항", "오답노트를 쓰던 저녁",
    "오답노트를 덮기 전", "다음 날 무표시 재풀이", "모의세트 두 번째 장",
    "시간 제한 없는 풀이", "시간을 재고 푼 세트", "맞힌 답을 설명할 때",
    "틀린 답을 다시 볼 때", "새 문항의 첫 시도", "교과서 예제를 바꾼 문제",
    "변형 문항을 받은 순간", "서술형 답안을 적을 때", "표와 그래프를 대조할 때",
    "두 선택지만 남은 순간", "계산값이 보기에 없을 때", "풀이가 한 쪽을 넘긴 때",
    "조건을 두 번째 읽을 때", "채점표를 확인한 직후", "주말 복습을 시작할 때",
    "수업 끝 10분 전", "풀이를 친구에게 설명할 때", "정답을 가리고 복기할 때",
    "유사 문항을 이어 풀 때", "단원 점검을 마친 뒤", "시험 범위를 나누던 날",
]

TIMINGS = [
    "처음 판단 전", "첫 표시 직후", "풀이 두 줄째", "중간 검산에서", "답 확정 직전",
    "채점 직후", "해설을 보기 전", "해설을 덮은 뒤", "다음 학습 시작 때",
]

FIRST = {
    "영어": ["반복어에 먼저 표시", "조건어에 밑줄", "빈칸 뒤부터 재독", "첫 문단만 요약", "선지 강도를 비교", "지시어에 화살표", "주절 동사를 표시", "연결어만 동그라미", "답부터 잠정 선택", "근거 문장을 검색", "마지막 문단을 먼저 확인", "선지 두 개를 나란히 기록", "부정어를 네모로 표시", "문단별 핵심어를 메모", "보기의 범위어를 분류", "제목 후보를 한 줄로 축약"],
    "수학": ["조건에 밑줄", "식부터 작성", "그래프를 먼저 그림", "정의역 표시를 생략", "공식을 먼저 적음", "교점을 계산", "부호표 없이 진행", "끝점 대입을 미룸", "보기 수를 역대입", "첫 계산을 전부 삭제", "좌우 식을 한 줄에 기록", "후보값부터 나열", "문제 요구값에 동그라미", "단위를 먼저 통일", "도함수의 영점을 표시", "두 풀이를 나란히 배치"],
    "일반": ["주간 계획표부터 작성", "마감일에 표시", "쉬운 과제부터 시작", "남은 시간을 계산", "오답 번호만 기록", "과목별 분량을 나열", "귀가 시간을 제외", "복습 칸을 먼저 배치", "완료 표시부터 확인", "시험 범위를 날짜별 분할", "미완료 과제를 이월", "수행평가 일정을 겹쳐 기록", "어려운 단원을 마지막에 배치", "공부 시간을 과목별 합산", "다음 날 할 일을 한 줄로 기록", "실제 소요시간을 옆에 표기"],
}

MISTAKES = {
    "영어": [("역접 뒤 주장 누락", "앞부분 설명을 결론으로 받아들였다"), ("지시 대상 오인", "지시어를 바로 앞 명사에만 연결했다"), ("주절과 관계절 혼동", "수식절의 동사를 문장의 중심으로 읽었다"), ("사례를 주장으로 확대", "한 사례의 특징을 글 전체의 주장으로 넓혔다"), ("선지 강도 과장", "some을 all과 같은 범위로 판단했다"), ("부분 소재를 제목으로 선택", "반복된 소재 하나를 글의 제목으로 확정했다"), ("빈칸 뒤 근거 누락", "빈칸 앞 문장만으로 답을 골랐다"), ("연결어 하나에 의존", "문단 간 대명사 연결을 확인하지 않았다"), ("배경지식 개입", "본문보다 익숙한 상식에 맞는 답을 택했다"), ("주체 변경 누락", "행위자가 바뀐 문장을 같은 주체로 읽었다"), ("부정 표현 누락", "not until의 제한을 긍정 진술로 바꿔 읽었다"), ("범위 제한 삭제", "only가 제한하는 대상을 선지 비교에서 빼버렸다"), ("인과 방향 반전", "결과 문장을 원인으로 연결했다"), ("대조 대상 혼선", "두 집단의 특성을 서로 바꾸어 적었다"), ("예외 문장 생략", "마지막의 예외 조건을 일반 규칙에 포함하지 않았다"), ("대명사 수 불일치 누락", "복수 대상을 단수 명사에 연결했다")],
    "수학": [("끝점 누락", "열린 구간만 조사하고 경계값을 후보에서 뺐다"), ("정의역 누락", "식이 성립하지 않는 값을 계산에 포함했다"), ("부호 반전", "이항 뒤 부등호 방향을 그대로 두었다"), ("교점 하나 누락", "한쪽 가지에서 생기는 해를 목록에 적지 않았다"), ("절댓값 처리 누락", "부호가 바뀌는 지점을 나누지 않고 미분했다"), ("합성 순서 반대", "바깥 함수와 안쪽 함수의 적용 순서를 바꿨다"), ("부분합을 일반항으로 사용", "두 식의 차를 구해야 하는 위치를 건너뛰었다"), ("로그 진수 조건 누락", "양수 조건을 해집합과 교집합하지 않았다"), ("좌우극한 합침", "두 방향의 접근값을 한 계산으로 처리했다"), ("도함수 0을 바로 극값으로 판단", "부호 변화 없이 후보를 확정했다"), ("속도와 거리 혼동", "부호가 있는 값을 그대로 이동거리로 더했다"), ("필요충분 방향 반대", "명제의 역을 원래 조건처럼 사용했다"), ("중복근 횟수 오인", "그래프의 접점을 두 교점으로 세었다"), ("매개변수 범위 누락", "해의 개수만 보고 계수 범위를 적지 않았다"), ("공차와 항 번호 혼선", "첫째항을 0번째 항처럼 대입했다"), ("확률 표본공간 누락", "순서를 구분하는 경우와 구분하지 않는 경우를 섞었다")],
    "일반": [("계획 시간 과다", "이동과 휴식 시간을 제외한 채 학습량을 배치했다"), ("귀가시간 미반영", "실제로 책상에 앉는 시각보다 앞에 과제를 넣었다"), ("오답 재풀이 없음", "채점 표시만 남기고 틀린 이유를 확인하지 않았다"), ("과제 우선순위 충돌", "마감일과 소요시간을 구분하지 않고 순서를 정했다"), ("한 과목 과몰입", "막힌 한 문항에 전체 복습 시간을 사용했다"), ("시험범위 배분 실패", "분량이 큰 단원을 마지막 날에 몰았다"), ("수행평가 일정 충돌", "제출 준비와 시험 복습을 같은 시간대에 배치했다"), ("복습 시점 지연", "처음 학습한 뒤 일주일 동안 다시 확인하지 않았다"), ("완료 기준 불명확", "읽기만 마친 과제를 이해 완료로 표시했다"), ("이월 분량 누적", "못한 일을 줄이지 않고 다음 날 칸에 그대로 옮겼다"), ("기록 없는 반복", "같은 문제를 다시 풀면서 달라진 행동을 남기지 않았다"), ("난도 순서 고정", "집중도가 낮은 시간에도 어려운 과제를 먼저 뒀다"), ("교재 전환 과다", "한 단원을 끝내기 전에 자료를 여러 번 바꿨다"), ("검산 시간 미확보", "풀이 분량만 계산하고 확인 시간을 남기지 않았다"), ("목표 단위 과대", "한 번에 끝내기 어려운 범위를 한 칸에 적었다"), ("맞힌 문제 복기 생략", "근거가 약한 정답을 복습 목록에서 제외했다")],
}

CORRECTIONS = [
    "최초 오류가 난 줄만 다시 계산", "이전 풀이와 수정 풀이를 나란히 비교", "조건별 체크칸을 만들어 누락을 확인",
    "판단의 전후 관계를 표로 분리", "좌우 또는 앞뒤 계산을 두 칸으로 분리", "가능한 후보를 먼저 표에 기록",
    "선택 근거가 있는 문장 번호를 옆에 기록", "지시 표현과 실제 대상을 선으로 연결", "중심이 되는 식이나 주절만 다시 작성",
    "답을 고른 이유를 한 줄로 제한", "결과 대신 처음 어긋난 행동을 오답란에 기록", "문제가 요구한 값을 별도 칸에 표시",
    "첫 풀이와 다른 시간 제한으로 재시도", "핵심 조건 일부를 가린 채 순서를 복원", "수치 또는 소재 하나만 바꾸어 즉시 재풀이",
    "다음 날 표시 없는 원문으로 재풀이", "사용하지 않은 조건을 역으로 점검", "교사 설명 없이 학생이 오류 위치를 말로 재현",
    "마지막 판단부터 거꾸로 근거를 추적", "정답을 가리고 풀이의 위험한 한 줄만 찾기",
]

VERIFY = [
    "같은 문제를 표시 없이 다시 풂", "숫자만 달라진 문항에 적용", "조건 하나를 삭제한 경우와 비교", "제한 조건을 하나 추가해 다시 판단",
    "선지나 보기 순서를 바꾸어 재확인", "소재가 달라진 새 지문에 적용", "처음보다 짧은 시간 안에 풀이", "답 없이 풀이 과정만 설명",
    "완성된 풀이에서 최초 오류만 탐색", "정답을 가린 채 근거만 설명", "두 가지 풀이의 첫 차이를 비교", "결론에서 조건을 역으로 복원",
    "그래프만 보고 식의 변화 예상", "식만 보고 그래프의 모양 설명", "다음 날 빈 종이에 핵심 순서 재현", "맞힌 문제에서도 위험한 단계를 표시",
    "유사 문항 두 개의 조건 차이를 설명", "교재를 덮고 선택을 바꾼 이유를 말함",
]

ENDINGS = [
    "학생이 최초 오류를 직접 특정", "풀이의 첫 줄이 이전과 달라짐", "전체 계산을 지우지 않고 문제 줄만 고침", "근거 위치를 답보다 먼저 찾음",
    "끝점과 예외가 후보표에 함께 들어감", "답을 바꾸기 전에 이유를 남김", "검산 범위를 좁혀 제한시간 안에 마침", "맞힌 문제에서도 위험한 줄을 발견",
    "새 조건에 맞춰 다른 식을 세움", "오답노트의 기록 기준을 결과에서 과정으로 바꿈", "사용하지 않은 정보를 스스로 찾아냄", "다음 풀이에서 같은 첫 행동을 반복하지 않음",
    "설명 중 판단이 갈린 지점을 바로 짚음", "새 문항에서 확인 순서를 끝까지 유지", "수정 전후 풀이의 차이를 한 문장으로 정리", "정답 확인 없이도 선택 범위를 좁힘",
]

STYLE_NAMES = ["장면 서술형", "풀이 추적형", "비교형", "문제 해결형", "재풀이 관찰형", "시간 흐름형", "오답 추적형", "선택 근거형"]

HEAD_PATTERNS = [
    "{scene}의 {focus}", "{mistake}를 찾은 {timing}", "{action} 뒤 달라진 첫 줄", "왜 {focus}에서 멈췄을까",
    "{timing}, {correction}", "{scene}에 남은 한 가지 오류", "{focus}를 다시 확인한 과정", "답보다 먼저 바꾼 {action}",
]

BODY_PATTERNS = [
    "{opening}. {mistake_sentence}. 그래서 {correction_sentence}. {verification_sentence}; 끝에는 {ending_sentence}.",
    "{opening}. 처음에는 {mistake_sentence}. {reaction_sentence}. {correction_sentence}, 이어서 {verification_sentence}. 그 결과 {ending_sentence}.",
    "{opening}. {trigger_sentence}. 문제는 {mistake_sentence}는 데 있었다. 이후 {correction_sentence}. 확인 단계에서는 {verification_sentence}; {ending_sentence}.",
    "{opening}. {reaction_sentence}. 원인을 따라가니 {mistake_sentence}. {correction_sentence}. 마지막 확인으로 {verification_sentence}, 결국 {ending_sentence}.",
    "{opening}. {mistake_sentence}. 정답 여부보다 먼저 {correction_sentence}. 다음에는 {verification_sentence}. 이 과정에서 {ending_sentence}.",
    "{opening}; {trigger_sentence}. {mistake_sentence}. 이를 고치려고 {correction_sentence}, 검증할 때는 {verification_sentence}. 이후 {ending_sentence}.",
    "{opening}. 풀이를 비교한 결과 {mistake_sentence}. {reaction_sentence}. 곧바로 {correction_sentence}. {verification_sentence}는 방식으로 확인해 {ending_sentence}.",
    "{opening}. 첫 판단의 갈림점은 {mistake_sentence}는 순간이었다. {correction_sentence}. 이어 {verification_sentence}; 전과 달리 {ending_sentence}.",
]

REACTIONS = ["학생은 답보다 판단 순서를 먼저 되짚었다", "멈춘 위치를 표시한 뒤 앞 단계와 비교했다", "맞힌 답에서도 설명이 비는 지점을 발견했다", "해설을 바로 읽지 않고 자신의 첫 선택을 남겼다", "어느 조건을 사용하지 않았는지 소리 내어 확인했다", "정답 표시를 가리고 두 판단의 차이를 적었다", "계산량보다 최초 선택의 이유를 먼저 말했다", "풀이 전체를 버리지 않고 어긋난 부분만 남겼다"]


def sha(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


def plain(raw: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def topic_for(row: dict) -> str:
    return "영어" if row["subject"] == "영어" else "수학" if row["subject"] == "수학" else "일반"


def entity(row: dict) -> str:
    if row["school"]:
        return row["school"]
    value = row["region"].split("-")[-1]
    return value.replace("all", "") or row["region"]


def extract_source(row: dict) -> tuple[str, str]:
    text = (SOURCE / row["path"]).read_text(encoding="utf-8")
    article = re.search(r'<article class="content-body-card">(.*?)</article>', text, re.S)
    source_text = plain(article.group(1)) if article else ""
    cues = []
    keywords = ["빈칸", "선지", "지시어", "관계절", "주절", "그래프", "정의역", "부호", "끝점", "오답", "시간", "계획", "조건", "검산"]
    for key in keywords:
        if key in source_text:
            cues.append(key)
    return source_text, ", ".join(cues[:5]) or row["type"]


def make_plans(rows: list[dict]) -> list[dict]:
    plans = []
    global_index = 0
    used_seven = set()
    for page_index, row in enumerate(rows, 1):
        count = 4 + (sha(row["canonical"]) % 3)
        source_text, cues = extract_source(row)
        subject = topic_for(row)
        page_events = set(); page_corrections = set(); page_endings = set()
        for card_id in range(1, count + 1):
            # Each page/card receives an independent URL-hash draw. A salt is advanced
            # only when a global tuple or a same-page event/action/ending collides.
            for salt in range(10000):
                x = sha(f"{row['canonical']}|{card_id}|{salt}|story-v2")
                scene_i = x % len(SCENES)
                first_i = (x // 37) % len(FIRST[subject])
                mistake_i = (x // 101) % len(MISTAKES[subject])
                correction_i = (x // 211) % len(CORRECTIONS)
                verify_i = (x // 431) % len(VERIFY)
                ending_i = (x // 863) % len(ENDINGS)
                timing_i = (x // 1741) % len(TIMINGS)
                style_i = (x // 3469) % len(STYLE_NAMES)
                seven_key = (SCENES[scene_i], f'{cues} 관련 판단에서 두 근거가 맞지 않음', FIRST[subject][first_i], MISTAKES[subject][mistake_i][0], CORRECTIONS[correction_i], VERIFY[verify_i], ENDINGS[ending_i])
                event_key = (SCENES[scene_i], MISTAKES[subject][mistake_i][0])
                if seven_key not in used_seven and event_key not in page_events and CORRECTIONS[correction_i] not in page_corrections and ENDINGS[ending_i] not in page_endings:
                    used_seven.add(seven_key); page_events.add(event_key); page_corrections.add(CORRECTIONS[correction_i]); page_endings.add(ENDINGS[ending_i])
                    break
            else:
                raise SystemExit(f"unable to allocate story plan: {row['canonical']} #{card_id}")
            mistake, missed = MISTAKES[subject][mistake_i]
            plan = {
                "page_id": page_index, "card_id": card_id, "content_type": row["kind"],
                "region_or_school": entity(row), "grade": row["grade"], "subject": row["subject"],
                "page_topic": row["type"], "scene_type": SCENES[scene_i], "scene_timing": TIMINGS[timing_i],
                "starting_state": f'{FIRST[subject][first_i]}한 상태',
                "trigger": f'{cues} 관련 판단에서 두 근거가 맞지 않음', "first_action": FIRST[subject][first_i],
                "specific_mistake": mistake, "missed_information": missed,
                "student_reaction": REACTIONS[(x + page_index + card_id) % len(REACTIONS)],
                "teacher_or_training_action": f'{mistake}가 시작된 위치만 질문하고 답은 제시하지 않음',
                "correction_method": CORRECTIONS[correction_i], "verification_method": VERIFY[verify_i],
                "ending_state": ENDINGS[ending_i], "headline_angle": HEAD_PATTERNS[(x + style_i) % len(HEAD_PATTERNS)],
                "opening_angle": STYLE_NAMES[style_i], "ending_angle": ENDINGS[ending_i],
                "source_cues": cues, "source_excerpt": source_text[:240], "canonical": row["canonical"], "path": row["path"],
                "title": row["title"], "kind": row["kind"], "province": row["province"], "type": row["type"],
                "region": row["region"], "school": row["school"],
            }
            plans.append(plan)
            global_index += 1

    seven = [(p["scene_type"], p["trigger"], p["first_action"], p["specific_mistake"], p["correction_method"], p["verification_method"], p["ending_angle"]) for p in plans]
    if len(seven) != len(set(seven)):
        raise SystemExit(f"STORY PLAN 7-field duplicate: {len(seven)-len(set(seven))}")
    by_page = defaultdict(list)
    for p in plans:
        by_page[p["page_id"]].append((p["scene_type"], p["specific_mistake"], p["correction_method"], p["ending_angle"]))
    page_dup = sum(len(v) - len(set(v)) for v in by_page.values())
    if page_dup:
        raise SystemExit(f"same-page story duplicate: {page_dup}")
    return plans


def headline(p: dict) -> str:
    focus = p["specific_mistake"].replace(" 누락", "").replace(" 오인", "")
    short_correction = p["correction_method"].replace("다시 ", "").replace("하여 ", "")
    value = p["headline_angle"].format(scene=p["scene_type"], focus=focus, mistake=p["specific_mistake"], timing=p["scene_timing"], action=p["first_action"], correction=short_correction)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:30]


def opening(p: dict, index: int) -> str:
    e = p["region_or_school"]
    scene = p["scene_type"]
    first = p["first_action"]
    variants = [
        f"{scene}, {e} {p['page_topic']} 학습에서는 {first}부터 시작했다",
        f"{e}의 {p['grade']} 학습 장면은 {scene}에 갈렸다; 첫 행동은 {first}였다",
        f"{scene}에 남은 풀이를 보니 {first}한 흔적이 가장 먼저 보였다",
        f"{first}한 직후, {e} 학습의 판단이 {scene}부터 어긋났다",
        f"{scene}의 답안에는 {first}한 위치와 멈춘 위치가 함께 남아 있었다",
        f"{e} {p['subject']} 과정에서 {scene}에 선택이 좁혀졌고, 학생은 {first}했다",
        f"채점 전 {scene}을 되짚자 {first}한 순서가 확인됐다",
        f"{scene}, 정답보다 먼저 확인한 것은 {first}한 이유였다",
    ]
    return variants[index % len(variants)]


def render_body(p: dict, index: int) -> str:
    mistake_sentence = p["missed_information"]
    correction_sentence = p["correction_method"]
    verification_sentence = p["verification_method"]
    ending_sentence = p["ending_state"]
    trigger_sentence = p["trigger"].replace(" 관련 판단에서", "을 판단하는 과정에서")
    reaction_sentence = p["student_reaction"]
    e = p['region_or_school']; topic = p['page_topic']; first = p['first_action']; scene = p['scene_type']
    mode = sha(p["canonical"] + "|syntax|" + str(p["card_id"])) % 12
    first_forms = [
        f"{opening(p,index)}; {mistake_sentence}, 그래서 {correction_sentence}.",
        f"{opening(p,index)}. {mistake_sentence}는 사실을 확인하고 {correction_sentence}.",
        f"{mistake_sentence}. 이 오류는 {opening(p,index)}는 과정에서 드러나 {correction_sentence}.",
        f"{opening(p,index)}. 처음 어긋난 대목은 '{mistake_sentence}'였고 {correction_sentence}.",
        f"{scene}의 선택을 추적하니 {mistake_sentence}; {correction_sentence}으로 순서를 고쳤다.",
        f"{first}한 답안을 다시 보자 {mistake_sentence}. {e} {topic}에서는 {correction_sentence}.",
        f"{opening(p,index)}. 답이 갈린 원인은 {mistake_sentence}는 데 있어 {correction_sentence}.",
        f"{scene}, {first}한 직후 {mistake_sentence}. 수정은 {correction_sentence}으로 시작했다.",
        f"{e}의 {topic} 풀이에서 {mistake_sentence}. {scene}으로 돌아가 {correction_sentence}.",
        f"{opening(p,index)}; 해설보다 먼저 {mistake_sentence}는 점을 찾아 {correction_sentence}.",
        f"{scene}에 남은 첫 흔적은 {first}한 것이었다. 이어 {mistake_sentence}, 곧 {correction_sentence}.",
        f"{mistake_sentence}는 순간부터 답이 달라졌다. {opening(p,index)}고 {correction_sentence}.",
    ]
    reaction_forms = [
        reaction_sentence + ".", f"이때 {reaction_sentence}.", f"학생 반응은 분명했다; {reaction_sentence}.",
        f"정답을 확인하기 전 {reaction_sentence}.", f"풀이를 멈춘 학생은 {reaction_sentence}.",
        f"그 자리에서 {reaction_sentence}.", f"비교가 끝나자 {reaction_sentence}.", f"이유를 묻자 {reaction_sentence}.",
        f"남은 답안 앞에서 {reaction_sentence}.", f"이전 기록과 대조하며 {reaction_sentence}.",
        f"교사의 답을 기다리는 대신 {reaction_sentence}.", f"다음 단계로 가기 전 {reaction_sentence}.",
    ]
    guide_forms = [
        f"{e} {topic} 지도에서는 {first}의 이유만 질문했다.", f"지도자는 답을 말하지 않고 {p['specific_mistake']}의 시작점만 물었다.",
        f"수정 중에는 {p['teacher_or_training_action']}.", f"교정 질문은 {first}과 {p['specific_mistake']} 사이에 집중됐다.",
        f"설명은 줄이고 {e} 학생이 오류 위치를 직접 고르게 했다.", f"{topic} 지도 과정은 결과 대신 {first}의 이유를 되묻는 데서 출발했다.",
        f"교사는 {correction_sentence}한 부분만 가리킨 채 판단 근거를 요청했다.", f"해설을 보여주기 전 {p['specific_mistake']}가 생긴 줄을 학생이 찾게 했다.",
        f"{e}에서는 정답 대신 {p['missed_information']}는 지점을 질문으로 남겼다.", f"지도 단계에서 비교한 것은 {first} 전후의 풀이였다.",
        f"학생에게는 {correction_sentence}한 이유를 말로 설명하게 했다.", f"교사는 {scene}의 첫 선택만 되짚고 나머지 계산은 학생에게 맡겼다.",
    ]
    verify_forms = [
        f"검증에는 '{verification_sentence}' 방법을 사용했다.", f"확인은 {verification_sentence}는 과제로 이어졌다.",
        f"이후 {verification_sentence}며 수정 순서를 점검했다.", f"재적용 단계에서는 {verification_sentence}.",
        f"새 확인 조건은 '{verification_sentence}'였다.", f"같은 답을 외웠는지는 {verification_sentence}며 구분했다.",
        f"마지막에는 {verification_sentence}는 방식으로 근거를 되짚었다.", f"검산 대신 {verification_sentence}는 절차를 택했다.",
        f"다음 학습에서는 {verification_sentence}며 행동 변화를 살폈다.", f"재확인은 정답보다 {verification_sentence}는 데 초점을 뒀다.",
        f"바뀐 판단은 {verification_sentence}며 시험했다.", f"확인 문제에서는 {verification_sentence}도록 조건을 바꿨다.",
    ]
    last_forms = [
        f"{scene} 이후 {ending_sentence}; {first} 뒤 {correction_sentence}으로 {p['specific_mistake']}를 재확인했다.",
        f"결국 {ending_sentence}. {p['specific_mistake']}는 {correction_sentence}한 기록에서 다시 발견됐다.",
        f"{verification_sentence}는 동안 {ending_sentence}; 출발점은 {first}과 {p['specific_mistake']}의 관계였다.",
        f"마지막 변화는 {ending_sentence}는 것이었다. {scene}의 오류는 {correction_sentence}으로 구분했다.",
        f"{e}의 다음 풀이에서는 {ending_sentence}. 그 기준으로 {p['specific_mistake']}와 {first}을 함께 확인했다.",
        f"{correction_sentence}한 결과 {ending_sentence}; {verification_sentence}며 같은 오류가 없는지 살폈다.",
        f"{p['specific_mistake']}를 다시 묻자 {ending_sentence}. {first}했던 처음과 달리 {correction_sentence}을 유지했다.",
        f"{scene}을 마칠 때는 {ending_sentence}. 확인표에는 {first}, {correction_sentence} 순서가 남았다.",
        f"새 과제에서도 {ending_sentence}; {verification_sentence}며 {p['specific_mistake']} 여부를 판단했다.",
        f"끝에는 {ending_sentence}. {e} 학생은 {correction_sentence}으로 {first}의 결과를 검토했다.",
        f"전과 달리 {ending_sentence}; {scene}에서 쓴 {correction_sentence}을 다음 문제에도 적용했다.",
        f"{first}한 이유를 다시 말한 뒤 {ending_sentence}. {p['specific_mistake']}는 {verification_sentence}며 걸러냈다.",
    ]
    first_chunk = first_forms[mode]
    reaction_chunk = reaction_forms[(mode*5+index)%12]
    guide_chunk = guide_forms[(mode*7+index)%12]
    verify_chunk = verify_forms[(mode*11+index)%12]
    last_chunk = last_forms[(mode*3+index)%12]
    complexity = sha(p["canonical"] + "|complexity|" + str(p["card_id"])) % 20
    chunks = [first_chunk, verify_chunk, last_chunk]
    if complexity == 18:
        chunks.insert(1, reaction_chunk if mode % 2 == 0 else guide_chunk)
    elif complexity == 19:  # a small genuinely complex tail retains both observations
        chunks[1:1] = [reaction_chunk, guide_chunk]
    # A form may contain an explanatory stop; keep it as an internal clause so the
    # final 2–5 sentence count reflects story complexity, not template punctuation.
    chunks = [re.sub(r"\.\s+", "; ", value).rstrip(".") + "." for value in chunks]
    if len(chunks) == 5:
        body = " ".join(chunks)
    elif len(chunks) == 4:
        body = " ".join(chunks)
    else:
        target = 2 + (sha(p["canonical"] + "|sentences|" + str(p["card_id"])) % 2)
        if target == 2:
            body = chunks[0][:-1] + " " + chunks[1] + " " + chunks[2]
        else:
            body = " ".join(chunks)
    return body.replace("..", ".").replace("  ", " ")


def main() -> None:
    with PAGES_CSV.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 500:
        raise SystemExit(f"expected 500 pages, got {len(rows)}")

    plans = make_plans(rows)
    plan_fields = [
        "page_id", "card_id", "content_type", "region_or_school", "grade", "subject", "page_topic",
        "scene_type", "scene_timing", "starting_state", "trigger", "first_action", "specific_mistake",
        "missed_information", "student_reaction", "teacher_or_training_action", "correction_method",
        "verification_method", "ending_state", "headline_angle", "opening_angle", "ending_angle",
        "source_cues", "source_excerpt", "canonical", "path",
    ]
    with PLANS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=plan_fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(plans)

    # Only after the plan checks and CSV write have succeeded do we create prose/output.
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(SOURCE, OUTPUT)
    base_css = (SOURCE / "static/css/site.css").read_text(encoding="utf-8")
    pilot_css = (ROOT / "candidate_output_review_cards_pilot/static/css/site.css").read_text(encoding="utf-8")
    (OUTPUT / "static/css/site.css").write_text(base_css + pilot_css[len(base_css):], encoding="utf-8")

    grouped = defaultdict(list)
    cards = []
    used_headlines = set()
    used_last_sentences = set()
    for index, p in enumerate(plans):
        sub = headline(p)
        if sub in used_headlines:
            # Every fallback draws another semantic axis from the plan. No counter or
            # hidden identifier is exposed merely to force uniqueness.
            candidates = [
                f"{p['specific_mistake'][:10]} 뒤 {p['correction_method'][:14]}",
                f"{p['scene_timing']}, {p['verification_method'][:17]}",
                f"{p['first_action'][:11]}에서 찾은 {p['specific_mistake'][:10]}",
                f"{p['scene_type'][:10]} · {p['ending_angle'][:15]}",
                f"{p['scene_type'][:6]}·{p['specific_mistake'][:6]}·{p['correction_method'][:6]}·{p['verification_method'][:6]}",
            ]
            sub = next((x[:30] for x in candidates if x[:30] not in used_headlines), "")
        if not sub or sub in used_headlines:
            raise SystemExit(f"headline collision unresolved: {p['canonical']} #{p['card_id']}")
        used_headlines.add(sub)
        body = render_body(p, index)
        ending = re.split(r"(?<=[.!?])\s+", body)[-1]
        if ending in used_last_sentences:
            body = body[:-1] + f"; {p['region_or_school']} {p['page_topic']} 재확인."
            ending = re.split(r"(?<=[.!?])\s+", body)[-1]
        if ending in used_last_sentences:
            raise SystemExit(f"ending collision unresolved: {p['canonical']} #{p['card_id']}")
        used_last_sentences.add(ending)
        stars = "★★★★☆" if sha(p["canonical"] + f"#{p['card_id']}") % 5 in (0, 3) else "★★★★★"
        sentences = len([x for x in re.split(r"(?<=[.!?])\s+", body) if x])
        card = {**{k: p[k] for k in ("kind", "province", "type", "region", "school", "grade", "subject", "title", "canonical", "path")},
                "page_index": p["page_id"], "card": p["card_id"], "subheading": sub, "body": body,
                "stars": stars, "sentences": sentences, "chars": len(body),
                "story_plan": {k: p[k] for k in plan_fields if k not in ("source_excerpt", "canonical", "path")}}
        cards.append(card); grouped[p["path"]].append(card)

    for path, page_cards in grouped.items():
        target = OUTPUT / path
        text = target.read_text(encoding="utf-8")
        section = '<section class="learning-case-section" aria-labelledby="learning-cases"><h2 id="learning-cases">학습 과정에서 확인한 사례</h2><div class="learning-case-grid">' + ''.join(
            f'<article class="learning-case-card"><h3>{html.escape(c["subheading"])}</h3><p>{html.escape(c["body"])}</p><div class="learning-case-meta"><span class="learning-case-stars" aria-label="디자인용 별 아이콘">{c["stars"]}</span></div></article>'
            for c in page_cards) + '</div></section>'
        marker = '</article></div><section class="related-navigation'
        if text.count(marker) != 1:
            raise SystemExit(f"bad insertion marker: {path}")
        target.write_text(text.replace(marker, '</article>' + section + '</div><section class="related-navigation', 1), encoding="utf-8")

    CARDS_JSON.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
    triple = Counter((p["specific_mistake"], p["correction_method"], p["ending_angle"]) for p in plans)
    print(json.dumps({"pages": len(grouped), "plans": len(plans), "cards": len(cards),
                      "seven_field_duplicates": 0, "same_page_story_duplicates": 0,
                      "max_three_field_frequency": max(triple.values()), "output": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
