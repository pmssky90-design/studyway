from __future__ import annotations
import csv,hashlib,html,json,re,shutil
from collections import defaultdict,deque
from pathlib import Path
from urllib.parse import unquote,urlsplit
from build_review_cards_pilot import SCENES,build_body
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'candidate_output_images_mobile_dom_full_bleed_aligned_cards';OUT=ROOT/'candidate_output_review_stress_500';REPORTS=ROOT/'reports'
SEOUL=('강남구','강동구','강북구','강서구','관악구','광진구','구로구','금천구','노원구','도봉구','동대문','동작구','마포구','서대문','서초구','성동구','성북구','송파구','양천구','영등포','용산구','은평구','종로구','중구','중랑구')
ROLES=['시험 중 처음 고른 답','과제에서 멈춘 계산','다음 날 무표시 재풀이','맞힌 문제의 근거 설명','종료 직전 시간 배분','오답노트에 남긴 첫 실수','두 풀이를 나란히 본 장면','요구값을 다시 읽은 순간','조건을 식에 넣은 위치','새 수치로 바꾼 확인','교재를 덮고 설명한 과정','마지막 검산 한 항목']
def clean(s):return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>','',s))).strip()
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def classify(p,t,h1,canonical):
    rel=p.relative_to(SRC).as_posix();kind='school' if rel.startswith('school/') else 'region';parts=rel.split('/');entity=unquote(parts[1]);leaf=unquote(parts[-2]);province='서울' if (entity.startswith('11') if kind=='school' else entity.startswith(SEOUL)) else '경기'
    grade=next((x for x in ('고1','고2','고3','초등','중등','고등') if x in leaf),'기본');subject='영어' if '영어' in leaf else ('수학' if '수학' in leaf else '일반');ptype=f'{grade}-{subject}'
    region='' if kind=='school' else entity;school=entity.split('-',1)[1] if kind=='school' and '-' in entity else ''
    return {'kind':kind,'province':province,'type':ptype,'region':region,'school':school,'grade':grade,'subject':subject,'leaf':leaf,'entity':entity,'path':rel,'title':clean(re.search(r'<title>(.*?)</title>',t,re.S).group(1)),'h1':h1,'canonical':canonical}
def main():
    pool=[]
    for p in SRC.rglob('index.html'):
        t=p.read_text(encoding='utf-8')
        if 'class="content-image-sequence"' not in t:continue
        h=clean(re.search(r'<h1>(.*?)</h1>',t,re.S).group(1));c=html.unescape(re.search(r'<link rel="canonical" href="([^"]+)',t).group(1));pool.append(classify(p,t,h,c))
    groups=defaultdict(list)
    for r in pool:groups[(r['kind'],r['province'],r['type'])].append(r)
    for v in groups.values():v.sort(key=lambda r:sha(r['canonical']))
    qs=deque((k,deque(v)) for k,v in sorted(groups.items()));selected=[]
    while len(selected)<500:
        k,q=qs.popleft()
        if q:selected.append(q.popleft())
        if q:qs.append((k,q))
    if OUT.exists():shutil.rmtree(OUT)
    shutil.copytree(SRC,OUT)
    # Reuse only the isolated review CSS from the accepted 12-page pilot.
    pilot_css=(ROOT/'candidate_output_review_cards_pilot'/'static/css/site.css').read_text(encoding='utf-8');base_css=(SRC/'static/css/site.css').read_text(encoding='utf-8');(OUT/'static/css/site.css').write_text(base_css+pilot_css[len(base_css):],encoding='utf-8')
    cards=[]
    for pi,r in enumerate(selected):
        p=OUT/r['path'];t=p.read_text(encoding='utf-8');count=4+(int(sha(r['canonical'])[:2],16)%3);kind='math' if r['subject']=='수학' else ('english' if r['subject']=='영어' else 'general');page_cards=[]
        for ci in range(count):
            seed=int(sha(r['canonical']+f'#{ci}')[:12],16);role=ROLES[(seed+ci)%len(ROLES)];topic=f"{r['h1']}의 {role}";sentences=(2,3,4,5)[(pi+ci*3)%4];body=build_body(kind,topic,seed%60000,sentences);stars='★★★★☆' if seed%7 in (0,3) else '★★★★★';sub=f'{role} · {r["leaf"]}'
            item={**{k:r[k] for k in ('kind','province','type','region','school','grade','subject','title','canonical')},'page_index':pi+1,'card':ci+1,'subheading':sub,'body':body,'stars':stars,'sentences':len([x for x in re.split(r'(?<=[.!?])\s+',body) if x]),'chars':len(body)};cards.append(item);page_cards.append(item)
        section='<section class="learning-case-section" aria-labelledby="learning-cases"><h2 id="learning-cases">학생 유형별 학습 사례</h2><div class="learning-case-grid">'+''.join(f'<article class="learning-case-card"><h3>{html.escape(x["subheading"])}</h3><p>{html.escape(x["body"])}</p><div class="learning-case-meta"><span class="learning-case-stars" aria-label="디자인용 별 아이콘">{x["stars"]}</span></div></article>' for x in page_cards)+'</div></section>'
        marker='</article></div><section class="related-navigation';assert t.count(marker)==1;t=t.replace(marker,'</article>'+section+'</div><section class="related-navigation',1);p.write_text(t,encoding='utf-8')
    fields=['kind','province','type','region','school','grade','subject','title','canonical','path']
    with (REPORTS/'review-stress-500-pages.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k] for k in fields} for r in selected)
    (REPORTS/'review-stress-500-cards.json').write_text(json.dumps(cards,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pages':len(selected),'cards':len(cards),'groups':{str(k):sum(1 for r in selected if (r['kind'],r['province'],r['type'])==k) for k in groups},'output':str(OUT)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
