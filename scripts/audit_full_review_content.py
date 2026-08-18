import csv, json, re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
rows={r['url']:r for r in csv.DictReader((ROOT/'reports/url-plan.csv').open(encoding='utf-8-sig')) if r['page_type'] in {'region_content','school_content'}}
err=re.compile(r'#ERROR!|#N/A|#VALUE!|#REF!|#NAME\?|#NUM!|#DIV/0!|(?:^|\s)(?:Loading|ERROR|오류|로드 중|생성 중|처리 중)(?:\s|[.!?]|$)',re.I)
foreign=re.compile(r'[\u0400-\u052f\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\u0a80-\u0aff\u0e00-\u0e7f]|�')
formula=re.compile(r'^\s*=|_xlfn\.|(?:^|[^A-Za-z])GPT\s*\(',re.I)
c=Counter(); grade_conf=[]; subject_conf=[]
with (ROOT/'reports/full-reviews-design/cards.jsonl').open(encoding='utf-8') as stream:
    for line in stream:
        x=json.loads(line); r=rows[x['url']]; body=x['body']; c['cards']+=1
        if err.search(body): c['error']+=1
        if foreign.search(body): c['foreign']+=1
        if formula.search(body): c['formula']+=1
        rep=r['dong_eup_myeon'] or r['district'] or r['city']
        if '개봉동' in body:
            c['placeholder_total']+=1
            if rep=='개봉동': c['actual_gaebong']+=1
            else: c['wrong_gaebong']+=1
        kind='math' if r['subject']=='수학' else 'english' if r['subject']=='영어' else 'general'
        if kind=='math' and x['sheet']!='수학': subject_conf.append(x['url'])
        if kind=='english' and x['sheet']!='영어': subject_conf.append(x['url'])
        target=r['grade']
        mentions=re.findall(r'(?:초등학교\s*[1-6]학년|중학교\s*[1-3]학년|고등학교\s*[1-3]학년|(?<![가-힣])(?:초[1-6]|중[1-3]|고[1-3])(?![가-힣]))',body)
        if target and target not in {'초','중'} and mentions:
            expected={'초1':'초등학교 1학년','초2':'초등학교 2학년','초3':'초등학교 3학년','초4':'초등학교 4학년','초5':'초등학교 5학년','초6':'초등학교 6학년','중1':'중학교 1학년','중2':'중학교 2학년','중3':'중학교 3학년','고1':'고등학교 1학년','고2':'고등학교 2학년','고3':'고등학교 3학년'}.get(target)
            if expected and any(m!=expected for m in mentions): grade_conf.append((x['url'],mentions))
c['subject_conflict']=len(subject_conf); c['grade_conflict']=len(grade_conf)
out=dict(c)
(ROOT/'reports/full-reviews-design/content-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
