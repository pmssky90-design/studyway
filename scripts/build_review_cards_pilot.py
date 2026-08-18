from __future__ import annotations

import hashlib, html, json, re, shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'candidate_output_images_mobile_dom_full_bleed_aligned_cards'
OUT=ROOT/'candidate_output_review_cards_pilot'
REPORT=ROOT/'reports'/'review-cards-pilot.json'

TARGETS={
'강남구과외':('학습 과정 사례',['주간 계획과 실제 사용 시간','오답 원인을 남기는 기록','짧은 날의 학습 순서','새 과제에 적용한 기준']),
'관악구과외':('학생 유형별 학습 사례',['과목별 시작 장벽 낮추기','할 일보다 완료 기준 정하기','밀린 과제의 우선순위','다음 날 다시 확인한 계획','시험 뒤 루틴 복구']),
'수원과외':('수업 과정에서 확인한 변화',['이동 시간을 고려한 계획','과목별 최소 학습량','복습과 새 진도의 분리','주말 보완 순서','기록으로 조정한 일정','다음 주 재적용']),
'영통동고2수학과외':('오답 수정과 재적용 사례',['정의역을 먼저 표시한 함수','부호가 바뀌는 구간 점검','조건을 식으로 옮긴 순서','그래프로 확인한 계산','새 조건에서 다시 세운 풀이']),
'신림동고3영어과외':('학습 후기와 수업 사례',['역접 뒤에서 회수한 주장','빈칸 앞뒤의 제한조건','선지 의미범위 비교','지시어가 가리킨 문장','시간 제한 속 직접근거','새 장문에서 바꾼 순서']),
'개봉동고1영어과외':('학습 과정 사례',['주절을 먼저 찾은 문장','관계절 경계 표시','제목 선지의 범위','지시어 연결 확인']),
'청명고등학교과외':('학생별 학습 변화 사례',['시험 일정과 과제량 조정','과목별 오답 분류','짧은 복습 루틴','완료 기준을 남긴 계획','새 단원에 적용한 기록']),
'개포고등학교고2수학과외':('오답 수정과 재적용 사례',['함수 조건의 사용 순서','미분 부호표 확인','극값과 경계값 구분','계산 뒤 원식 대입','그래프가 달라진 새 문제','제한시간 검산 순서']),
'가평고등학교고3영어과외':('수업 과정에서 확인한 변화',['장문의 주장과 사례 분리','순서 문제의 연결어','삽입문의 지시어','선지의 과도한 일반화']),
'용인삼계고등학교고3영어과외':('학생 유형별 학습 사례',['빈칸의 직접근거 회수','마지막 역접 확인','제목 선지 범위 조절','후반부 판단 시간 배분','새 소재 장문 재적용']),
'가평고등학교고3수학과외':('학습 과정 사례',['수열 조건을 표로 정리','로그 정의역 확인','미분 계산의 부호 점검','적분 구간을 나눈 이유','새 수치에서 풀이 재현','답 뒤의 조건 검산']),
'설악고등학교고3영어과외':('오답 수정과 재적용 사례',['주제와 사례의 범위 구분','순서 단서의 재확인','관계절 뒤 핵심문장','제한조건이 붙은 선지']),
}

LABELS=['학습 사례','수업 과정','오답 수정','재적용 사례','학습 변화','판단 점검']

SCENES={
'general':{
'start':['월요일에는 계획표 첫 칸부터 비어 있었습니다. 귀가 뒤 식사와 학교 과제를 마치니 예정한 시작 시각이 이미 한 시간 지나 있었습니다.','주말 오전에 한 과목을 끝내려다 점심 이후 일정까지 밀렸습니다. 남은 과목은 책만 펼친 채 완료 표시를 해두었습니다.','오답노트에는 틀린 번호가 계속 늘었지만 지난주 페이지를 다시 연 흔적은 없었습니다.','수행평가 준비와 내신 복습을 같은 시간대에 적어 둔 날, 학생은 쉬운 과제만 먼저 끝내고 시험 범위는 미뤘습니다.','다음 날 책상에는 전날 세운 시간표가 남아 있었지만 실제 공부한 분량은 절반도 기록되지 않았습니다.','시험이 가까워지자 국어·영어·수학 교재를 한꺼번에 꺼냈고 무엇부터 끝낼지 정하지 못한 채 표지만 넘겼습니다.','맞힌 문제까지 다시 보겠다고 표시했지만 정작 틀린 문제의 첫 풀이를 지워 원인을 찾을 수 없었습니다.','학교에서 늦게 돌아온 날에도 평소와 같은 분량을 적어 두어 자정이 지나도록 마지막 과목이 남았습니다.','공부를 시작한 시각은 빨랐지만 휴대전화 확인 뒤 다시 앉을 때마다 처음 페이지부터 훑었습니다.','과제 제출일을 하루 잘못 적은 탓에 시험 전날 계획했던 복습 시간이 통째로 사라졌습니다.'],
'miss':['완료 여부를 시간으로만 판단해 실제로 무엇을 끝냈는지는 남지 않았습니다.','밀린 분량을 다음 날 칸에 그대로 옮기면서 계획표만 길어졌습니다.','쉬운 과목을 오래 붙잡은 뒤 어려운 단원은 시작도 하지 못했습니다.','틀린 답만 적고 어느 단계에서 멈췄는지는 비워 두었습니다.','예정과 달라진 시간을 실패로 보고 그날 공부를 전부 포기했습니다.','학교 과제와 시험 공부를 구분하지 않아 급한 일과 중요한 일이 섞였습니다.','복습한 페이지 수는 셌지만 책을 덮고 기억나는 내용을 말하지 못했습니다.','휴식 시간을 빼지 않은 계획이라 실제 종료 시각이 매일 달라졌습니다.','한 과목이 밀리면 뒤 과목을 모두 삭제하는 방식으로 대응했습니다.','주말 보충량을 평일과 똑같이 잡아 외출 일정과 계속 충돌했습니다.'],
'action':['귀가·식사·과제 시간을 먼저 적은 뒤 남은 칸에 개념 확인과 재풀이를 나누어 배치했습니다.','완료 칸에는 공부한 시간 대신 끝낸 문제 번호와 다시 볼 한 항목을 적었습니다.','오답 페이지를 사진처럼 옮기지 않고 처음 막힌 행동만 한 줄로 남겼습니다.','25분 안에 끝낼 일과 시간이 더 필요한 일을 서로 다른 색으로 구분했습니다.','밀린 과제를 통째로 옮기지 않고 다음 시험에 직접 필요한 부분만 다시 골랐습니다.','저녁 계획이 늦어지면 새 진도를 빼고 당일 오답 두 문제만 되짚도록 최소선을 정했습니다.','일요일에는 계획표를 새로 만들지 않고 일주일 동안 지키지 못한 칸 세 개만 원인을 적었습니다.','과목을 바꿀 때 책상 위에 다음 교재 한 권만 남겨 시작 행동을 짧게 만들었습니다.','수행평가 마감일과 시험 범위를 한 장에 놓고 겹치는 날의 분량을 미리 줄였습니다.','맞은 문제도 풀이 이유를 말하지 못하면 완료 대신 재확인 표시를 붙였습니다.'],
'reveal':['기록을 대조하자 늦게 시작한 날보다 과제를 예상하지 못한 날에 계획이 더 자주 무너졌습니다.','공부 시간이 짧아서가 아니라 첫 과목을 끝내는 기준이 없다는 점이 드러났습니다.','일주일치 표에서 반복된 공백은 같은 요일의 귀가 일정과 겹쳤습니다.','실패한 계획으로 보였던 날에도 짧은 복습은 끝냈다는 사실을 학생이 직접 찾았습니다.','오답 수보다 다시 보지 않은 기간이 길수록 같은 실수가 반복됐습니다.','완료 표시가 많았던 날에도 설명하지 못한 개념이 남아 있었습니다.']},
'math':{
'start':['답이 보기에 없자 학생은 첫 줄부터 전부 지우고 같은 계산을 다시 시작했습니다.','도함수가 0이 되는 점 두 개의 함수값만 비교한 뒤 답을 골랐습니다.','식의 두 번째 줄에서 음수 부호가 빠졌지만 마지막 숫자가 익숙해 그대로 제출했습니다.','절댓값 기호를 둔 채 한 식으로 미분해 구간이 바뀌는 지점을 건너뛰었습니다.','교점을 하나 찾자 곧바로 적분식을 세웠고 나머지 교점은 그림에만 남았습니다.','정의역을 쓰라는 표시를 보고도 로그 식을 먼저 정리했습니다.','0/0이 나오자 같은 약분을 세 번 반복하며 다른 접근을 시도하지 않았습니다.','문제는 최댓값을 물었는데 학생의 마지막 줄에는 극댓값만 적혀 있었습니다.','시험 종료 10분 전, 검산하려던 두 문제에서 원래 식 대입을 모두 생략했습니다.','수열의 첫 항 조건을 읽었지만 일반항 식에는 공차 조건만 들어갔습니다.'],
'miss':['닫힌 구간의 양 끝점을 후보에 넣지 않았습니다.','부호가 바뀐 줄이 아니라 마지막 산술 계산만 다시 살폈습니다.','그래프 없이 식의 크기만 비교해 교점의 앞뒤 관계가 뒤집혔습니다.','문제에서 요구한 값과 중간에 구한 값을 구분하지 않았습니다.','분모가 0이 되는 값을 답 후보에서 제외하지 않았습니다.','적분 구간을 나누지 않아 넓이가 음수로 남았습니다.','조건을 읽고 밑줄은 그었지만 실제 방정식에는 반영하지 않았습니다.','계산 전체를 지우는 바람에 최초 오류가 시작된 줄을 찾지 못했습니다.','좌우에서 다르게 접근하는 값을 한쪽 계산만으로 결정했습니다.','맞힌 답이었지만 왜 그 구간에서 증가하는지 설명하지 못했습니다.'],
'action':['도함수 영점 옆에 끝점 두 개를 함께 적고 네 함수값을 표 한 줄에서 비교했습니다.','틀린 줄 위에 부호표를 그려 양수와 음수 구간을 눈으로 대조했습니다.','절댓값이 풀리는 지점에 세로선을 긋고 구간마다 식을 새로 썼습니다.','두 교점을 좌표축에 찍은 다음 넓이가 바뀌는 곳에서 적분식을 분리했습니다.','오류가 난 두 번째 줄만 다시 계산하고 앞뒤 식이 연결되는지 화살표로 표시했습니다.','정의역에서 빠지는 값을 식 옆에 적어 계산 결과와 답 후보를 마지막에 대조했습니다.','로피탈을 반복하기 전에 인수분해와 치환 중 어느 방법이 짧은지 한 줄씩 시험했습니다.','문제의 질문에 동그라미를 치고 마지막 줄의 값이 그 질문에 답하는지 단위를 붙였습니다.','검산 시간이 부족할 때는 원식 대입 한 가지를 남기고 전체 재계산은 하지 않았습니다.','수열 조건을 표로 옮겨 첫 항·공차·항 번호가 어느 식에 쓰였는지 칸별로 적었습니다.'],
'reveal':['채점표를 가리고 다시 보니 답이 아니라 후보를 만드는 단계가 빠졌다는 것을 스스로 설명했습니다.','이전 풀이와 나란히 놓자 처음 달라진 곳은 계산값이 아니라 식을 나눈 위치였습니다.','숫자를 바꾼 유사 문제에서는 기존 식을 복사할 수 없어 조건부터 다시 세워야 했습니다.','정답이 맞은 문제에도 위험한 줄 하나가 남아 있었고 학생은 그 줄에만 재확인 표시를 붙였습니다.','두 풀이를 비교한 끝에 시간이 짧을 때도 부호를 눈으로 볼 수 있는 방법을 선택했습니다.','다음 날 빈 종이에서는 정답보다 후보 목록을 먼저 완성했습니다.']},
'english':{
'start':['첫 문단의 반복어가 2번 선지에도 보이자 학생은 지문을 끝까지 읽기 전에 답 표시를 해두었습니다.','빈칸 앞 한 문장만 두 번 읽고 뒤 문단은 사례라고 넘겼습니다.','however 뒤 문장을 읽었는데도 처음 고른 답을 지우지 않았습니다.','관계절 안의 동사를 주절 동사로 읽어 문장의 주체를 바꾸어 해석했습니다.','this가 바로 앞 명사를 가리킨다고 선을 그었지만 실제 대상은 앞 문장 전체였습니다.','접속사 하나만 보고 두 문단의 순서를 정한 뒤 대명사 연결은 살피지 않았습니다.','익숙한 환경 소재가 나오자 본문보다 상식에 맞는 선지를 골랐습니다.','시험 후반에 모르는 단어 하나에서 오래 멈춘 뒤 남은 지문을 처음부터 급하게 재독했습니다.','정답은 맞혔지만 근거 문장을 찾아보라는 질문에는 첫 문단만 가리켰습니다.','두 선지 사이에서 답을 세 번 바꾸는 동안 각 선택의 이유는 적지 않았습니다.'],
'miss':['마지막 문단이 앞의 사례를 제한한다는 점을 놓쳤습니다.','선지의 all을 본문의 some과 같은 범위로 읽었습니다.','역접 앞 설명만 기억해 글쓴이의 최종 주장과 반대로 골랐습니다.','삽입문 첫 단어가 가리키는 대상을 찾지 않은 채 분위기로 위치를 정했습니다.','주절이 끝나는 지점을 잘못 잡아 원인과 결과를 뒤집었습니다.','제목 선지가 본문 한 사례만 말하는데도 반복어가 많다는 이유로 유지했습니다.','모르는 단어의 뜻을 추측하느라 이미 읽은 문장까지 여러 번 되돌아갔습니다.','답을 바꾸기 전 근거가 사라졌는지 확인하지 않아 마지막 선택이 더 약해졌습니다.','순서 문제에서 첫 문장끼리만 비교하고 각 문단의 마지막 연결은 보지 않았습니다.','직접 근거가 아니라 익숙한 표현의 개수로 두 선지를 비교했습니다.'],
'action':['2번 옆에 적은 첫 근거를 지우지 않고 마지막 문단의 반대 근거를 바로 아래에 덧붙였습니다.','빈칸 앞뒤 한 문장씩만 괄호로 묶어 두 선택지가 모두 설명되는지 읽었습니다.','however 뒤 문장을 한국어 한 줄로 줄인 다음 처음 답의 범위와 맞대어 보았습니다.','주절의 주어와 동사에 밑줄을 긋고 관계절은 괄호로 닫아 다시 해석했습니다.','this와 실제 대상 문장을 선으로 연결하고 중간 명사는 후보에서 제외했습니다.','각 문단 끝의 대명사와 반복 명사를 표에 적은 뒤 이어지는 순서를 다시 정했습니다.','상식으로 고른 선지 옆에 물음표를 남기고 본문에서 같은 뜻의 문장을 찾을 때까지 확정하지 않았습니다.','모르는 단어는 표시만 남긴 채 주절을 먼저 읽고, 마지막에 문맥으로 뜻을 좁혔습니다.','맞힌 문제도 근거 문장 번호를 쓰고 그 문장이 다른 선지를 왜 막는지 말했습니다.','답을 바꾸기 직전 이유를 한 줄 적어 이전 선택보다 근거가 강한 경우에만 수정했습니다.'],
'reveal':['처음 답을 고른 이유와 바꾼 이유를 나란히 읽자 어느 쪽이 본문 전체를 설명하는지 드러났습니다.','전체 지문을 다시 읽지 않고 필요한 문단 두 곳만 회수해 시간을 남겼습니다.','새 소재의 장문에서는 아는 배경지식이 없어도 마지막 주장 문장으로 제목을 좁혔습니다.','다음 날 무표시 지문에서 학생은 선지보다 지시어의 대상을 먼저 찾았습니다.','정답 여부와 별개로 근거를 찾지 못한 문제 한 개를 복습 목록에 남겼습니다.','처음 표시한 선지가 맞았지만 범위를 넓혀 읽은 위험한 이유는 오답노트에 따로 적었습니다.']}}

def build_body(kind,topic,g,sentence_count):
    bank=SCENES[kind];q=g//10
    start=f'“{topic}” 기록을 펼친 날, '+bank['start'][g%10]
    miss=bank['miss'][(g*3+q+1)%10];action=bank['action'][(g*7+q*3+2)%10];reveal=bank['reveal'][(g*5+q+3)%6]
    ending_options=[f'{topic}을 다시 다룰 때는 학생이 첫 선택의 이유를 말한 뒤 답을 확정했습니다.',f'풀이가 끝난 뒤 {topic}에서 처음 어긋난 행동만 공책 여백에 남겼습니다.',f'학생은 {topic}의 이전 풀이와 새 풀이를 펼쳐 놓고 첫 차이를 직접 찾았습니다.',f'제한시간을 다시 걸었을 때도 {topic}에 필요한 마지막 확인 한 가지는 빼지 않았습니다.',f'{topic}과 닮은 과제에서는 정답을 보기 전에 자신이 바꾼 순서를 설명했습니다.',f'다음 날에는 표시가 없는 상태로 {topic}을 시작해 같은 실수가 어디서 멈췄는지 보여주었습니다.',f'{topic}의 답은 맞았지만 근거가 약했던 줄만 별도 복습 대상으로 남았습니다.',f'조건이 달라진 문제에서는 {topic}의 기존 답을 지우고 첫 식부터 새로 세웠습니다.',f'{topic}을 마친 뒤 학생이 교사에게 오류가 시작된 순간을 한 문장으로 설명했습니다.',f'마지막에는 {topic}에서 사용하지 않은 정보가 무엇인지 역으로 찾아냈습니다.']
    end=ending_options[(g*9+q*3)%10]
    collapse=lambda s:re.sub(r'\.\s+',', ',s).rstrip('.')
    if sentence_count==2:
        body=f'{collapse(start)}. {end}'
        return body if len(body)>=100 else body.replace('. ','. 학생은 그날의 표시를 그대로 남겼습니다. ',1)
    if sentence_count==3:return f'{collapse(start)} {miss} {action} {end}'
    if sentence_count==4:return f'{collapse(start)}. {miss} {action} {end}'
    return f'{start} {miss} {reveal} {action} {end}'

def norm(s:str)->str:return re.sub(r'\s+','',html.unescape(re.sub('<[^>]+>','',s)))
def meta(text,name):
    m=re.search(rf'<meta (?:property|name)="{re.escape(name)}" content="([^"]*)"',text);return html.unescape(m.group(1)) if m else ''
def digest(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()

def main():
    if OUT.exists(): shutil.rmtree(OUT)
    shutil.copytree(SRC,OUT)
    found={}
    for p in OUT.rglob('index.html'):
        t=p.read_text(encoding='utf-8')
        m=re.search(r'<h1>(.*?)</h1>',t,re.S)
        if m and norm(m.group(1)) in TARGETS: found[norm(m.group(1))]=(p,t)
        rel=p.relative_to(OUT).as_posix()
        if rel=='region/관악구-신림동/고3영어과외/index.html': found['신림동고3영어과외']=(p,t)
    missing=sorted(set(TARGETS)-set(found))
    if missing: raise SystemExit(f'missing targets: {missing}')
    css='''\n/* Review-card pilot: only pages containing the new section are affected. */
.learning-case-section{margin:24px 0 0;padding:24px;background:#f7faf8;border:1px solid #dce7e0;border-radius:18px}.learning-case-section>h2{margin:0 0 16px}.learning-case-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.learning-case-card{display:flex;flex-direction:column;min-width:0;padding:18px;background:#fff;border:1px solid #dbe5df;border-radius:14px}.learning-case-card h3{margin:0 0 10px;font-size:1.05rem}.learning-case-card p{margin:0;overflow-wrap:anywhere}.learning-case-meta{margin-top:auto;padding-top:14px;display:flex;justify-content:flex-end;align-items:center}.learning-case-stars{color:#d89b12;letter-spacing:1px;white-space:nowrap}@media(max-width:767px){.learning-case-section{margin-top:0;border-left:0;border-right:0;border-radius:0;padding:22px 20px}.learning-case-grid{grid-template-columns:1fr}.learning-case-card{padding:17px}}\n'''
    css_path=OUT/'static'/'css'/'site.css';css_path.write_text(css_path.read_text(encoding='utf-8')+css,encoding='utf-8')
    rows=[];all_cards=[]
    global_i=0
    for page_i,(key,(heading,topics)) in enumerate(TARGETS.items()):
        p,t=found[key]; old=t
        cards=[]
        for i,topic in enumerate(topics):
            g=global_i; global_i+=1
            kind='math' if '수학' in key else ('english' if '영어' in key else 'general')
            count=2 if g<14 else (3 if g<32 else (4 if g<52 else 5))
            body=build_body(kind,topic,g,count)
            cards.append((topic,body,'★★★★★' if (page_i+i)%3 else '★★★★☆'))
            all_cards.append(body)
        section='<section class="learning-case-section" aria-labelledby="learning-cases"><h2 id="learning-cases">'+heading+'</h2><div class="learning-case-grid">'+''.join(f'<article class="learning-case-card"><h3>{html.escape(a)}</h3><p>{html.escape(b)}</p><div class="learning-case-meta"><span class="learning-case-stars" aria-label="디자인용 별 아이콘">{c}</span></div></article>' for a,b,c in cards)+'</div></section>'
        marker='</article></div><section class="related-navigation'
        if t.count(marker)!=1: raise SystemExit(f'bad insertion marker: {p}')
        t=t.replace(marker,'</article>'+section+'</div><section class="related-navigation',1)
        p.write_text(t,encoding='utf-8')
        before_article=re.search(r'<article class="content-body-card">.*?</article>',old,re.S).group(0)
        after_article=re.search(r'<article class="content-body-card">.*?</article>',t,re.S).group(0)
        rows.append({'h1':key,'url':meta(t,'og:url') or re.search(r'<link rel="canonical" href="([^"]+)',t).group(1),'path':str(p.relative_to(OUT)),'cards':len(cards),'body_chars':[len(x[1]) for x in cards],'article_same':digest(before_article)==digest(after_article),'title_same':re.search(r'<title>.*?</title>',old).group(0)==re.search(r'<title>.*?</title>',t).group(0),'canonical_same':re.search(r'<link rel="canonical"[^>]+>',old).group(0)==re.search(r'<link rel="canonical"[^>]+>',t).group(0),'links_same':re.findall(r'<a\b[^>]*>.*?</a>',old,re.S)==re.findall(r'<a\b[^>]*>.*?</a>',t,re.S)})
    normalized=[re.sub(r'(강남구|관악구|수원|영통동|신림동|개봉동|청명고등학교|개포고등학교|가평고등학교|용인삼계고등학교|설악고등학교)','{대상}',x) for x in all_cards]
    report={'source':str(SRC),'output':str(OUT),'pages':rows,'total_cards':len(all_cards),'exact_duplicate_cards':len(all_cards)-len(set(all_cards)),'name_only_duplicate_cards':len(normalized)-len(set(normalized)),'stars':{'★★★★★':sum((p+i)%3!=0 for p,(_,v) in enumerate(TARGETS.items()) for i in range(len(v[1]))),'★★★★☆':sum((p+i)%3==0 for p,(_,v) in enumerate(TARGETS.items()) for i in range(len(v[1])))}}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
