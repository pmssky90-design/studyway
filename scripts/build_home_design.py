from pathlib import Path
import json, re

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'candidate_output_full_reviews_design'
OUT=ROOT/'candidate_output_home_design'
REPORT=ROOT/'reports'/'home-design'
REPORT.mkdir(parents=True,exist_ok=True)

src=(SRC/'index.html').read_text(encoding='utf-8')
dst=src
dst=dst.replace('<body>','<body class="home-page">',1)
hero='''<section class="home-hero" aria-label="StudyWay 대표 안내"><img src="/assets/images/home/studyway-main-hero.png" width="1536" height="1024" alt="StudyWay 지역별·학교별 영어 수학 맞춤 과외 안내"></section>'''
intro='''<section class="home-intro" aria-labelledby="home-intro-title"><h2 id="home-intro-title">영어·수학 과외를 지역과 학교에 맞춰 찾아보세요</h2><p>StudyWay는 서울과 경기 지역을 중심으로 학생의 학년과 과목, 학교와 생활권을 함께 살펴볼 수 있도록 구성한 영어·수학 과외 정보 사이트입니다. 같은 지역에 거주하더라도 학교 일정과 통학 시간, 현재 학습 습관에 따라 필요한 수업 방식은 달라질 수 있습니다. 지역별 과외와 학교별 과외 페이지를 나누어 학생에게 필요한 정보를 보다 쉽게 찾아볼 수 있도록 구성했습니다.</p><p>영어과외는 단어와 독해처럼 특정 영역만 따로 보기보다 평소 숙제 습관, 학교 시험 준비, 질문하는 방식과 복습 흐름까지 함께 살펴보는 것이 중요합니다. 수학과외 역시 문제 수를 늘리는 것보다 학생이 어느 부분에서 막히는지, 틀린 문제를 어떻게 다시 보는지, 스스로 풀이를 이어갈 수 있는지를 확인하는 과정이 필요합니다. StudyWay에서는 초등부터 중등, 고등 과정까지 학년별 학습 상황을 고려해 관련 페이지를 연결하고 있습니다.</p><p>서울과 경기의 지역별 과외에서는 실제 생활권을 기준으로 가까운 지역의 영어과외와 수학과외 정보를 찾아볼 수 있습니다. 학교별 과외에서는 고등학교를 중심으로 학교 페이지와 학년·과목별 페이지를 연결해 필요한 내용을 바로 확인할 수 있도록 했습니다. 아래 지역별 과외 또는 학교별 과외에서 원하는 지역과 학교를 선택해 살펴보세요.</p></section>'''
dst=dst.replace('<main>','<main>'+hero+intro,1)
dst=dst.replace('<article>','<article class="home-directory">',1)
dst=dst.replace('<section id="regions">','<section id="regions" class="home-finder-section home-region-finder">',1)
dst=dst.replace('<section id="schools" class="school-finder">','<section id="schools" class="school-finder home-finder-section home-school-finder">',1)

css=r'''

/* HOME-only design. Content pages are unaffected. */
.home-page main{width:min(1180px,calc(100% - 32px));max-width:1180px}
.home-page .home-hero{margin:22px 0 24px;overflow:hidden;border:1px solid #dde5df;border-radius:22px;background:#f7f8f6;box-shadow:0 14px 38px rgba(28,54,42,.075)}
.home-page .home-hero img{display:block;width:100%;height:auto;max-width:100%;object-fit:contain}
.home-page .home-intro,.home-page .home-finder-section{margin:0 0 28px;padding:clamp(22px,4vw,38px);background:#f5f7f6;border:1px solid #dfe7e2;border-radius:20px;box-shadow:0 10px 30px rgba(28,54,42,.055)}
.home-page .home-intro h2,.home-page .home-finder-section>h2{margin:0 0 18px;color:#173f33;font-size:clamp(1.35rem,2.4vw,1.8rem);line-height:1.4}
.home-page .home-intro p{margin:0;color:#475b54;font-size:1rem;line-height:1.82}
.home-page .home-intro p+p{margin-top:15px}
.home-page .home-directory>h1{margin:4px 0 24px;color:#173f33}
.home-page .home-region-finder>section{margin-top:18px;padding:20px;background:#fff;border:1px solid #e0e8e3;border-radius:15px;box-shadow:0 4px 16px rgba(28,54,42,.035)}
.home-page .home-region-finder h3{margin:0 0 13px;color:#294d42;font-size:1.08rem}
.home-page .home-region-finder .link-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.home-page .home-region-finder .link-grid a,.home-page .school-link-grid a{display:flex;align-items:center;min-height:46px;padding:11px 14px;background:#fff;border:1px solid #dfe7e2;border-radius:11px;color:#285246;font-weight:650;line-height:1.45;text-decoration:none;overflow-wrap:anywhere;word-break:keep-all;transition:background-color .16s ease,border-color .16s ease,transform .16s ease,box-shadow .16s ease}
.home-page .home-region-finder .link-grid a:hover,.home-page .school-link-grid a:hover{background:#eef5f1;border-color:#bfd1c7;transform:translateY(-1px);box-shadow:0 5px 14px rgba(28,54,42,.055)}
.home-page .school-province{padding:20px;background:#fff;border:1px solid #e0e8e3;border-radius:15px}
.home-page .school-province+.school-province{margin-top:18px}
.home-page .school-province>h3{color:#294d42}
.home-page .school-area-tabs{gap:8px}
.home-page .school-area-tabs button{min-height:40px;padding:8px 13px;background:#f6f8f7;border:1px solid #dce5e0;border-radius:10px;color:#466158;font-weight:650;transition:background-color .16s ease,border-color .16s ease,color .16s ease}
.home-page .school-area-tabs button:hover{background:#edf4f0;border-color:#c6d7ce}
.home-page .school-area-tabs button[aria-selected="true"]{background:#dfece6;border-color:#adc7bb;color:#16483a;box-shadow:inset 0 0 0 1px rgba(22,72,58,.04)}
.home-page .school-area-panel{margin-top:18px}
.home-page .school-area-panel h4{color:#294d42}
.home-page .school-link-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}
.home-page .school-link-grid a{min-height:44px;font-size:.95rem;font-weight:600}
@media(max-width:767px){.home-page main{width:min(100%,calc(100% - 24px))}.home-page .home-hero{margin:14px 0 18px;border-radius:15px}.home-page .home-intro,.home-page .home-finder-section{margin-bottom:20px;padding:20px 16px;border-radius:16px}.home-page .home-intro p{font-size:.95rem;line-height:1.76}.home-page .home-region-finder>section,.home-page .school-province{padding:15px;border-radius:13px}.home-page .home-region-finder .link-grid{grid-template-columns:1fr}.home-page .school-link-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.home-page .school-link-grid a{min-height:46px;padding:10px 11px;font-size:.9rem}.home-page .school-area-tabs{display:flex;overflow-x:auto;max-width:100%;padding-bottom:6px;scrollbar-width:thin}.home-page .school-area-tabs button{flex:0 0 auto}.home-page .home-directory>h1{font-size:clamp(1.45rem,7vw,1.9rem)}}
@media(max-width:360px){.home-page .school-link-grid{grid-template-columns:1fr}}
'''

(OUT/'index.html').write_text(dst,encoding='utf-8')
site_css=OUT/'static/css/site.css'
site_css.write_text(site_css.read_text(encoding='utf-8')+css,encoding='utf-8')

href=lambda text:re.findall(r'<a\b[^>]*\bhref="([^"]+)"',text)
def one(pattern,text):
    m=re.search(pattern,text,re.S);return m.group(1) if m else ''
audit={
 'href_before':len(href(src)),'href_after':len(href(dst)),'href_missing':list((__import__('collections').Counter(href(src))-__import__('collections').Counter(href(dst))).elements()),
 'href_added':list((__import__('collections').Counter(href(dst))-__import__('collections').Counter(href(src))).elements()),
 'h1_before':len(re.findall(r'<h1\b',src)),'h1_after':len(re.findall(r'<h1\b',dst)),
 'title_unchanged':one(r'<title>(.*?)</title>',src)==one(r'<title>(.*?)</title>',dst),
 'description_unchanged':one(r'<meta name="description" content="([^"]*)"',src)==one(r'<meta name="description" content="([^"]*)"',dst),
 'canonical_unchanged':one(r'<link rel="canonical" href="([^"]*)"',src)==one(r'<link rel="canonical" href="([^"]*)"',dst),
 'robots_unchanged':one(r'<meta name="robots" content="([^"]*)"',src)==one(r'<meta name="robots" content="([^"]*)"',dst),
 'hero':dst.count('class="home-hero"'),'intro':dst.count('class="home-intro"'),'regions':dst.count('home-region-finder'),'schools':dst.count('home-school-finder')}
(REPORT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(audit,ensure_ascii=False,indent=2))
