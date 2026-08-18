from __future__ import annotations
import html,json,re,statistics
from collections import Counter,defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'candidate_output_review_cards_pilot'; BASE=ROOT/'reports'/'review-cards-pilot.json'
JSON_OUT=ROOT/'reports'/'review-pilot-diversity-audit.json'; MD_OUT=ROOT/'reports'/'review-pilot-diversity-audit.md'
REGIONS=['강남구','관악구','수원','영통구','영통동','신림동','개봉동','구로구','가평','용인','개포동']
SCHOOLS=['청명고등학교','개포고등학교','가평고등학교','용인삼계고등학교','설악고등학교']
GRADE_SUBJECT=['초등','중등','고등','고1','고2','고3','영어','수학','과외']
def clean(s): return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>','',s))).strip()
def normalized(s): return re.sub(r'[^0-9A-Za-z가-힣]','',s).lower()
def strip_terms(s,terms):
    for x in sorted(terms,key=len,reverse=True): s=s.replace(x,'')
    return normalized(s)
def dup_count(vals): return sum(n-1 for n in Counter(vals).values() if n>1)
def ratio(a,b): return SequenceMatcher(None,a,b).ratio()
def pair_stats(items,scope):
    pairs=[]
    for i in range(len(items)):
        for j in range(i): pairs.append((ratio(items[i][1],items[j][1]),items[j][0],items[i][0]))
    pairs.sort(reverse=True)
    return {'scope':scope,'pairs':len(pairs),'max':round(pairs[0][0],4) if pairs else 0,'mean':round(statistics.mean(x[0] for x in pairs),4) if pairs else 0,'ge_080':sum(x[0]>=.8 for x in pairs),'ge_070':sum(x[0]>=.7 for x in pairs),'top10':[{'score':round(s,4),'a':a,'b':b} for s,a,b in pairs[:10]]}
def hist(vals,bins):
    return {f'{a}-{b}':sum(a<=x<=b for x in vals) for a,b in bins}
def main():
    base=json.loads(BASE.read_text(encoding='utf-8')); cards=[];pages=[]
    for pi,row in enumerate(base['pages']):
        t=(OUT/row['path']).read_text(encoding='utf-8');sec=re.search(r'<section class="learning-case-section".*?</section>',t,re.S).group(0)
        heading=clean(re.search(r'<h2[^>]*>(.*?)</h2>',sec,re.S).group(1)); page_cards=[]
        for ci,m in enumerate(re.finditer(r'<article class="learning-case-card"><h3>(.*?)</h3><p>(.*?)</p><div class="learning-case-meta"><span class="learning-case-stars"[^>]*>(.*?)</span>',sec,re.S)):
            sub,body,stars=map(clean,m.groups());label='';sentences=[x.strip() for x in re.split(r'(?<=[.!?])\s+',body) if x.strip()]
            grade=next((x for x in ['고1','고2','고3','초등','중등','고등'] if x in row['h1']),'기본');subject=next((x for x in ['영어','수학'] if x in row['h1']),'일반')
            item={'id':f'{pi+1:02d}-{ci+1:02d}','page':row['h1'],'subheading':sub,'body':body,'label':label,'stars':stars,'sentences':sentences,'grade':grade,'subject':subject};cards.append(item);page_cards.append(item)
        pages.append((row['h1'],normalized(' '.join(x['body'] for x in page_cards))))
    bodies=[x['body'] for x in cards]; ids=[x['id'] for x in cards]
    first=[x['sentences'][0] for x in cards];last=[x['sentences'][-1] for x in cards]
    def patterns(lines):
        vals=[re.sub(r'^(처음에는|풀이를 시작할 수는 있었으나|기본 내용은 이해하고 있었지만|시간을 재면|해설을 본 직후에는|앞 단계까지는).*?에서','<도입>',x) for x in lines]
        return {'exact_duplicates':dup_count(lines),'normalized_duplicates':dup_count([normalized(x) for x in lines]),'top':Counter(vals).most_common(10)}
    grams={}
    for n in (3,4):
        c=Counter()
        for b in bodies:
            w=b.split();c.update(tuple(w[i:i+n]) for i in range(len(w)-n+1))
        grams[str(n)]={'repeated_unique':sum(v>1 for v in c.values()),'repeated_total':sum(v-1 for v in c.values() if v>1),'top20':[{'text':' '.join(k),'count':v} for k,v in c.most_common(20) if v>1]}
    phrases=Counter()
    for b in bodies:
        s=normalized(b);seen=set()
        for n in range(8,16): seen.update(s[i:i+n] for i in range(len(s)-n+1))
        phrases.update(seen)
    frequent=[{'text':k,'cards':v} for k,v in phrases.most_common(40) if v>=3]
    grouped={}
    for field in ('subject','grade'):
        grouped[field]={}
        for k in sorted(set(x[field] for x in cards)):
            z=[(x['id'],normalized(x['body'])) for x in cards if x[field]==k];grouped[field][k]=pair_stats(z,k)
    adjacent=[{'a':cards[i-1]['id'],'b':cards[i]['id'],'score':round(ratio(normalized(cards[i-1]['body']),normalized(cards[i]['body'])),4)} for i in range(1,len(cards))]
    audit={
      'cards':len(cards),'pages':len(pages),
      'duplicates':{'exact':dup_count(bodies),'normalized':dup_count([normalized(x) for x in bodies]),'after_region_removed':dup_count([strip_terms(x,REGIONS) for x in bodies]),'after_school_removed':dup_count([strip_terms(x,SCHOOLS) for x in bodies]),'after_grade_subject_removed':dup_count([strip_terms(x,GRADE_SUBJECT) for x in bodies])},
      'sentence_patterns':{'first':patterns(first),'last':patterns(last)},'ngrams':grams,'frequent_phrases_8_15':frequent,
      'similarity':{'cards':pair_stats(list(zip(ids,[normalized(x) for x in bodies])),'cards'),'pages':pair_stats(pages,'pages'),'same_subject':grouped['subject'],'same_grade':grouped['grade'],'adjacent':{'max':max(x['score'] for x in adjacent),'mean':round(statistics.mean(x['score'] for x in adjacent),4),'ge_080':sum(x['score']>=.8 for x in adjacent),'top10':sorted(adjacent,key=lambda x:x['score'],reverse=True)[:10]}},
      'distributions':{'subheadings':Counter(x['subheading'] for x in cards),'labels':Counter(x['label'] for x in cards),'sentence_counts':Counter(len(x['sentences']) for x in cards),'character_counts':{'min':min(map(len,bodies)),'max':max(map(len,bodies)),'mean':round(statistics.mean(map(len,bodies)),2),'histogram':hist(list(map(len,bodies)),[(120,139),(140,159),(160,179),(180,199),(200,250)])},'stars':Counter(x['stars'] for x in cards)}
    }
    JSON_OUT.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    d=audit['duplicates'];c=audit['similarity']['cards'];p=audit['similarity']['pages'];dist=audit['distributions']
    md=f'''# StudyWay 후기 카드 파일럿 다양성 감사\n\n- 카드: {audit['cards']}\n- 페이지: {audit['pages']}\n- 완전/정규화/지역 제거/학교 제거/학년·과목 제거 중복: {d['exact']} / {d['normalized']} / {d['after_region_removed']} / {d['after_school_removed']} / {d['after_grade_subject_removed']}\n- 카드 유사도: 최대 {c['max']}, 평균 {c['mean']}, 0.80 이상 {c['ge_080']}\n- 페이지 후기영역 유사도: 최대 {p['max']}, 평균 {p['mean']}, 0.80 이상 {p['ge_080']}\n- 인접 카드 유사도: 최대 {audit['similarity']['adjacent']['max']}, 평균 {audit['similarity']['adjacent']['mean']}, 0.80 이상 {audit['similarity']['adjacent']['ge_080']}\n- 소제목 중복: {dup_count([x['subheading'] for x in cards])}\n- 라벨 분포: {dict(dist['labels'])}\n- 문장 수 분포: {dict(dist['sentence_counts'])}\n- 글자 수: {dist['character_counts']}\n- 별 패턴: {dict(dist['stars'])}\n\n세부 상위 유사쌍과 반복 n-gram/구문은 JSON 보고서를 참조하십시오.\n'''
    MD_OUT.write_text(md,encoding='utf-8');print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
