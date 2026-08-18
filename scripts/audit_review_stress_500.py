from __future__ import annotations
import hashlib,html,json,math,random,re,statistics
from collections import Counter,defaultdict
from difflib import SequenceMatcher
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports';CARDS=R/'review-stress-500-cards.json'
def norm(s):return re.sub(r'[^0-9A-Za-z가-힣]','',html.unescape(s)).lower()
def ratio(a,b):return SequenceMatcher(None,a,b,autojunk=False).ratio()
def dup(vals):return sum(v-1 for v in Counter(vals).values() if v>1)
def strip_fields(c,fields):
 s=c['body']
 for f in fields:
  v=c.get(f,'')
  if v:s=s.replace(v,'')
 return norm(s)
def sent(s):return [x.strip() for x in re.split(r'(?<=[.!?])\s+',s) if x.strip()]
def minhash(s):
 grams={s[i:i+3] for i in range(max(1,len(s)-2))};return tuple(min(int(hashlib.md5((str(k)+'|'+g).encode()).hexdigest()[:12],16) for g in grams) for k in range(12))
def candidates(texts):
 buckets=defaultdict(list);sigs=[minhash(x) for x in texts]
 for i,sg in enumerate(sigs):
  for b in range(4):buckets[(b,sg[b*3:(b+1)*3])].append(i)
 out=set()
 for ids in buckets.values():
  if len(ids)>1:
   for x in range(len(ids)):
    for y in range(x):out.add((ids[y],ids[x]))
 return out
def sim_report(items,topn=100,sample_n=50000):
 texts=[norm(x['body']) for x in items];sets=[{x[i:i+3] for i in range(max(1,len(x)-2))} for x in texts];pairs=[]
 for i,j in candidates(texts):
  if min(len(texts[i]),len(texts[j]))/max(len(texts[i]),len(texts[j]))<.58:continue
  z=2*len(sets[i]&sets[j])/(len(sets[i])+len(sets[j]))
  if z>=.55:pairs.append((z,i,j))
 pairs.sort(reverse=True);rng=random.Random(20260818);sample=[]
 for _ in range(min(sample_n,len(items)*(len(items)-1)//2)):
  i,j=rng.sample(range(len(items)),2);sample.append(2*len(sets[i]&sets[j])/(len(sets[i])+len(sets[j])))
 return {'method':'12-signature character-trigram LSH candidate search + character-trigram Dice similarity','candidate_pairs':len(pairs),'maximum':round(pairs[0][0],4) if pairs else 0,'sample_mean':round(statistics.mean(sample),4) if sample else 0,'ge_060':sum(x[0]>=.6 for x in pairs),'ge_065':sum(x[0]>=.65 for x in pairs),'ge_070':sum(x[0]>=.7 for x in pairs),'ge_075':sum(x[0]>=.75 for x in pairs),'ge_080':sum(x[0]>=.8 for x in pairs),'top':[{'similarity':round(z,4),'a':items[i],'b':items[j]} for z,i,j in pairs[:topn]],'_pairs':pairs}
def main():
 cards=json.loads(CARDS.read_text(encoding='utf-8'));texts=[x['body'] for x in cards];subs=[x['subheading'] for x in cards];first=[sent(x)[0] for x in texts];last=[sent(x)[-1] for x in texts]
 d={'exact':dup(texts),'normalized':dup(map(norm,texts)),'region_removed':dup(strip_fields(c,['region']) for c in cards),'school_removed':dup(strip_fields(c,['school']) for c in cards),'grade_removed':dup(strip_fields(c,['grade']) for c in cards),'subject_removed':dup(strip_fields(c,['subject']) for c in cards),'all_entity_fields_removed':dup(strip_fields(c,['region','school','grade','subject']) for c in cards),'subheading_exact':dup(subs),'subheading_entity_removed':dup(strip_fields({**c,'body':c['subheading']},['region','school','grade','subject']) for c in cards),'first_exact':dup(first),'first_normalized':dup(map(norm,first)),'last_exact':dup(last),'last_normalized':dup(map(norm,last))}
 grams={}
 for n in (3,4):
  cc=Counter()
  for t in texts:
   w=t.split();cc.update(tuple(w[i:i+n]) for i in range(len(w)-n+1))
  grams[str(n)]={'repeated_unique':sum(v>1 for v in cc.values()),'repeated_excess':sum(v-1 for v in cc.values() if v>1),'top100':[{'text':' '.join(k),'count':v} for k,v in cc.most_common(100) if v>1]}
 phrases=Counter()
 for t in texts:
  s=norm(t);seen=set()
  for n in range(8,16):seen.update(s[i:i+n] for i in range(len(s)-n+1))
  phrases.update(seen)
 card_sim=sim_report(cards)
 bypage=defaultdict(list)
 for c in cards:bypage[c['canonical']].append(c)
 pages=[{**v[0],'body':' '.join(x['body'] for x in v),'cards':len(v)} for v in bypage.values()]
 page_sim=sim_report(pages,50)
 groups={}
 for field in ('subject','grade','kind','province','type'):
  groups[field]={}
  for key in sorted({x[field] for x in cards}):
   z=[x for x in cards if x[field]==key];sr=sim_report(z,5,0);groups[field][key]={'cards':len(z),'maximum':sr['maximum'],'ge_070':sr['ge_070'],'ge_080':sr['ge_080']}
 endings=Counter(re.search(r'([가-힣]+(?:했습니다|았습니다|었습니다))\.?$',x).group(1) if re.search(r'([가-힣]+(?:했습니다|았습니다|었습니다))\.?$',x) else '(기타)' for x in last)
 action_terms=['표시','다시','근거','부호','기록','비교','대입','연결','검산','재독','설명','계산'];abstract=['판단 기준','학습 역량','효율적인 학습','체계적인','실력이 향상'];scene=['선지','문장','식','줄','문제','계획','과제','교점','끝점','오답','시간','문단','단어','계산','교재','공책']
 reality={'no_action_scene':sum(not any(w in x for w in scene) for x in texts),'abstract_centered':sum(sum(w in x for w in abstract)>=2 for x in texts),'action_terms':{w:sum(w in x for x in texts) for w in action_terms},'requested_endings':{w:sum(w in x for x in texts) for w in ['확인했습니다','유지했습니다','적용했습니다','조정했습니다','점검했습니다']},'top_endings':endings.most_common(30)}
 lens=[len(x) for x in texts];sc=Counter(len(sent(x)) for x in texts);stars=Counter(x['stars'] for x in cards)
 audit={'pages':len(pages),'cards':len(cards),'duplicates':d,'ngrams':grams,'phrases_8_15_top100':[{'text':k,'cards':v} for k,v in phrases.most_common(100)],'card_similarity':{k:v for k,v in card_sim.items() if k!='_pairs'},'page_similarity':{k:v for k,v in page_sim.items() if k!='_pairs'},'group_similarity':groups,'reality':reality,'distribution':{'cards_per_page':Counter(x['cards'] for x in pages),'sentence_counts':sc,'characters':{'min':min(lens),'max':max(lens),'mean':round(statistics.mean(lens),2),'median':statistics.median(lens),'short_100_144':sum(100<=x<145 for x in lens),'normal_145_205':sum(145<=x<=205 for x in lens),'long_206_280':sum(205<x<=280 for x in lens)},'stars':stars}}
 # Deterministic stratified sample: round-robin across kind/subject/grade.
 strata=defaultdict(list)
 for c in cards:strata[(c['kind'],c['subject'],c['grade'])].append(c)
 for k in strata:strata[k].sort(key=lambda x:hashlib.sha256((x['canonical']+str(x['card'])).encode()).hexdigest())
 sample=[]
 while len(sample)<100:
  moved=False
  for k in sorted(strata):
   if strata[k] and len(sample)<100:sample.append(strata[k].pop());moved=True
  if not moved:break
 lines=[]
 for i,c in enumerate(sample,1):lines += [f'[{i}] {c["kind"]} / {c["province"]} / {c["subject"]} / {c["grade"]}',f'페이지: {c["canonical"]}',f'title: {c["title"]}',f'카드: {c["card"]}',f'소제목: {c["subheading"]}',f'본문: {c["body"]}',f'별: {c["stars"]}',f'문장 수: {c["sentences"]} / 글자 수: {c["chars"]}','']
 (R/'review-stress-500-sample-100.txt').write_text('\n'.join(lines),encoding='utf-8')
 high=[]
 for z,i,j in card_sim['_pairs']:
  if z<.65:break
  a,b=cards[i],cards[j];high += [f'[유사도 {z:.4f}]',f'A: {a["canonical"]} / 카드 {a["card"]}',a['subheading'],a['body'],f'B: {b["canonical"]} / 카드 {b["card"]}',b['subheading'],b['body'],'']
 (R/'review-stress-500-high-similarity.txt').write_text('\n'.join(high) if high else '0.65 이상 카드 쌍 없음',encoding='utf-8')
 fail=d['exact']>0 or d['last_exact']>0 or card_sim['ge_080']>0 or page_sim['ge_080']>0;review=card_sim['ge_070']>0 or page_sim['ge_070']>0 or phrases.most_common(1)[0][1]>max(20,len(cards)*.02);audit['verdict']='FAIL' if fail else ('REVIEW' if review else 'PASS')
 (R/'review-stress-500-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'pages':audit['pages'],'cards':audit['cards'],'duplicates':d,'card_similarity':{k:v for k,v in card_sim.items() if k not in ('_pairs','top')},'page_similarity':{k:v for k,v in page_sim.items() if k not in ('_pairs','top')},'distribution':audit['distribution'],'verdict':audit['verdict']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
