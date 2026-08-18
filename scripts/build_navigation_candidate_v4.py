from __future__ import annotations

import csv, html, json, re, shutil, sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import build
SOURCE=ROOT/'output';OUT=ROOT/'candidate_output_navigation_v4';REPORTS=ROOT/'reports'/'navigation-v4';BASE='https://studyway.kr'
GROUPS=('기본','초등','중등','고등','고1','고2','고3')

def file_for(url):return OUT/'index.html' if url=='/' else OUT/unquote(url.strip('/'))/'index.html'
def group(sheet):
 n=sheet.removeprefix('(학교)')
 for x in ('고1','고2','고3'): 
  if n.startswith(x):return x
 if n.startswith('초등'):return '초등'
 if n.startswith(('중등','중1','중2','중3')):return '중등'
 if n.startswith('고등'):return '고등'
 return '기본'
def link_sections(rows,skip_base=True):
 d=defaultdict(list)
 for r in rows:
  if skip_base and r['source_sheet'].removeprefix('(학교)')=='과외':continue
  d[group(r['source_sheet'])].append((r['source_sheet'].removeprefix('(학교)'),r['url']))
 return ''.join(f'<section class="content-link-group"><h3>{g}</h3><div class="link-grid">'+''.join(f'<a href="{u}">{html.escape(t)}</a>' for t,u in d[g])+'</div></section>' for g in GROUPS if d[g])
def nav_section(title,body):return f'<section class="related-navigation"><h2>{html.escape(title)}</h2>{body}</section>'
def crumbs(items):
 visible='<nav class="breadcrumbs" aria-label="현재 위치"><ol>'+''.join(f'<li><a href="{u}">{html.escape(n)}</a></li>' if i<len(items)-1 else f'<li>{html.escape(n)}</li>' for i,(n,u) in enumerate(items))+'</ol></nav>'
 data={'@context':'https://schema.org','@type':'BreadcrumbList','itemListElement':[{'@type':'ListItem','position':i+1,'name':n,'item':BASE+u} for i,(n,u) in enumerate(items)]}
 return visible,'<script type="application/ld+json">'+json.dumps(data,ensure_ascii=False)+'</script>'
def alter(url,append='',breadcrumb=None):
 p=file_for(url);s=p.read_text(encoding='utf-8');s=s.replace('href="/region/"','href="/#regions"').replace('href="/school/"','href="/#schools"')
 s=re.sub(r'<aside class="related">.*?</aside>','',s,count=1,flags=re.S)
 if breadcrumb:
  vis,js=crumbs(breadcrumb);s=re.sub(r'<script type="application/ld\+json">.*?</script>',js,s,count=1,flags=re.S);s=re.sub(r'<nav class="breadcrumbs".*?</nav>',vis,s,count=1,flags=re.S)
 if append:s=s.replace('</article>',f'</article>{append}',1)
 p.write_text(s,encoding='utf-8')
class Meta(HTMLParser):
 def __init__(self):super().__init__();self.canon='';self.title='';self._t=False
 def handle_starttag(self,t,a):
  d=dict(a)
  if t=='link' and d.get('rel')=='canonical':self.canon=d.get('href','')
  if t=='title':self._t=True
 def handle_endtag(self,t):
  if t=='title':self._t=False
 def handle_data(self,d):
  if self._t:self.title+=d

def main():
 if OUT.exists():shutil.rmtree(OUT)
 shutil.copytree(SOURCE,OUT);REPORTS.mkdir(parents=True,exist_ok=True)
 with (ROOT/'reports/url-plan.csv').open(encoding='utf-8-sig') as f:plan=list(csv.DictReader(f))
 rc=[r for r in plan if r['page_type']=='region_content'];sc=[r for r in plan if r['page_type']=='school_content']
 rh=[r for r in plan if r['page_type']=='region_entity_hub'];sh=[r for r in plan if r['page_type']=='school_hub']
 by_r=defaultdict(list);by_s=defaultdict(list)
 for r in rc:by_r[r['hub_url']].append(r)
 for r in sc:by_s[r['parent_url']].append(r)
 rbase={h:next(x for x in rows if x['source_sheet']=='과외') for h,rows in by_r.items()}
 sbase={h:next(x for x in rows if x['source_sheet']=='(학교)과외') for h,rows in by_s.items()}

 book=build.Workbook(build.SOURCE);top_for={};grp_for={};top_prov={};top_names=set()
 hierarchy=[]
 for _,row in book.rows('구조'):
  prov,top,grp,local=[row.get(i,'').strip() for i in range(1,5)]
  if not grp:continue
  actual=top or grp;top_names.add(actual);top_prov[actual]=prov;hierarchy.append((prov,actual,grp,local))
  if local:top_for[(grp,local)]=actual;grp_for[(grp,local)]=grp
 for _,row in build.table_rows(book,'추가지역허브'):
  n=row.get('필요시군구허브','');
  if n:top_names.add(n);top_prov[n]=row.get('시도','경기도')
 base_by_entity={(r['district'],r['dong_eup_myeon']):r for r in rc if r['source_sheet']=='과외'}
 top_base={t:base_by_entity.get((t,'')) for t in top_names}
 local_base={(r['district'],r['dong_eup_myeon']):r for r in rc if r['source_sheet']=='과외' and r['dong_eup_myeon']}

 # Exact Excel-backed school-to-region relation.
 connect={r.get('KEDI코드',''):r for _,r in build.table_rows(book,'학교지역연결')}
 school_hub_by_code={h['slug'].split('-',1)[0]:h for h in sh};schools_for_region=defaultdict(list);school_region={}
 for code,h in school_hub_by_code.items():
  rel=connect[code];name=rel.get('최종연결지역명','');target=None
  local=rel.get('Luna동읍면','') or rel.get('주소상동읍면','')
  district=rel.get('Luna구시허브','')
  if local:target=local_base.get((district,local))
  if not target:
   top=rel.get('Luna중간권역','') or rel.get('공식시군구','').removesuffix('시')
   target=top_base.get(top) or base_by_entity.get((district,''))
  if not target:continue
  school_region[h['url']]=target['url'];schools_for_region[target['url']].append((h['school_name'],sbase[h['url']]['url']))

 # Content pages become the only public navigation nodes.
 for r in rc:
  entity=r['dong_eup_myeon'] or r['district'];base=rbase[r['hub_url']];top=top_for.get((r['district'],r['dong_eup_myeon']),r['district']);tb=top_base.get(top) or base
  items=[('홈','/'),(top+'과외',tb['url'])]
  if base['url']!=tb['url']:items.append((entity+'과외',base['url']))
  if r['url']!=base['url']:items.append((entity+r['source_sheet'],r['url']))
  append=''
  if r['url']==base['url']:
   append+=nav_section(entity+' 관련 학습',link_sections(by_r[r['hub_url']]))
   if not r['dong_eup_myeon']:
    grouped=defaultdict(list)
    district_content=[]
    for (dist,local),lr in local_base.items():
     if top_for.get((dist,local),dist)==top:grouped[dist].append((local,lr['url']))
    for dist in sorted({dist for dist,local in local_base if top_for.get((dist,local),dist)==top and dist!=top}):
     dr=base_by_entity.get((dist,''))
     if dr:district_content.append((dist+'과외',dr['url']))
    if district_content:append+=nav_section(entity+' 권역 학습','<div class="link-grid">'+''.join(f'<a href="{u}">{html.escape(n)}</a>' for n,u in district_content)+'</div>')
    if grouped:append+=nav_section(entity+' 세부 지역',''.join(f'<section><h3>{html.escape(g)}</h3><div class="link-grid">'+''.join(f'<a href="{u}">{html.escape(n)}</a>' for n,u in sorted(v))+'</div></section>' for g,v in sorted(grouped.items())))
   schools=schools_for_region.get(r['url'],[])
   if schools:append+=nav_section('이 지역과 연결된 고등학교','<div class="link-grid">'+''.join(f'<a href="{u}">{html.escape(n)}</a>' for n,u in sorted(schools))+'</div>')
  alter(r['url'],append,items)
 for r in sc:
  base=sbase[r['parent_url']];name=r['school_name'];items=[('홈','/'),(name+'과외',base['url'])]
  if r['url']!=base['url']:items.append((name+r['source_sheet'].removeprefix('(학교)'),r['url']))
  append=''
  if r['url']==base['url']:
   append+=nav_section(name+' 관련 학습',link_sections(by_s[r['parent_url']]))
   ru=school_region.get(r['parent_url'])
   if ru:
    region_name=next(x['dong_eup_myeon'] or x['district'] for x in rc if x['url']==ru)
    append+=nav_section('연결 지역',f'<div class="link-grid"><a href="{ru}">{html.escape(region_name)}</a></div>')
  alter(r['url'],append,items)

 # Delete only navigation-only HTML files, retaining content descendants.
 for r in plan:
  if r['page_type'] not in ('home','region_content','school_content'):
   p=file_for(r['url']);
   if p.exists():p.unlink()
 for d in sorted([x for x in OUT.rglob('*') if x.is_dir()],key=lambda x:len(x.parts),reverse=True):
  if not any(d.iterdir()):d.rmdir()

 # HOME directly links top region base content and all 662 school base pages.
 reg=defaultdict(list)
 for top,row in sorted(top_base.items()):
  if row:reg['서울' if '서울' in top_prov.get(top,'') else '경기'].append((top,row['url']))
 smeta={r['KEDI코드']:r for _,r in build.table_rows(book,'학교페이지대상')};sch=defaultdict(lambda:defaultdict(list))
 for code,h in school_hub_by_code.items():
  m=smeta[code];prov='서울' if m.get('시도')=='서울' else '경기';area=m.get('시군구','').removesuffix('시');sch[prov][area].append((h['school_name'],sbase[h['url']]['url']))
 region_html=''.join(f'<section><h3>{p}</h3><div class="link-grid">'+''.join(f'<a href="{u}">{html.escape(n)}</a>' for n,u in v)+'</div></section>' for p,v in reg.items())
 school_html=''.join(f'<section><h3>{p}</h3>'+''.join(f'<div class="school-area-card"><h4>{html.escape(a)}</h4><div class="link-grid">'+''.join(f'<a href="{u}">{html.escape(n)}</a>' for n,u in sorted(v))+'</div></div>' for a,v in sorted(areas.items()))+'</section>' for p,areas in sch.items())
 body=f'<section id="regions"><h2>지역별 과외</h2>{region_html}</section><section id="schools"><h2>학교별 과외</h2>{school_html}</section>'
 file_for('/').write_text(build.layout('StudyWay | 서울·경기 과외 학습정보','서울·경기 과외 학습정보',BASE+'/',[('홈','/')],body).replace('href="/region/"','href="/#regions"').replace('href="/school/"','href="/#schools"'),encoding='utf-8')

 # Sitemaps contain HOME plus unchanged content URLs only.
 for p in OUT.glob('sitemap*.xml'):p.unlink()
 urls=['/']+[r['url'] for r in rc+sc];xml='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{BASE+u}</loc></url>' for u in urls)+'</urlset>'
 (OUT/'sitemap-content.xml').write_text(xml,encoding='utf-8');(OUT/'sitemap-index.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://studyway.kr/sitemap-content.xml</loc></sitemap></sitemapindex>',encoding='utf-8')
 pages=[]
 for u in urls:
  m=Meta();m.feed(file_for(u).read_text(encoding='utf-8'));pages.append({'url':u,'canonical':m.canon,'slug':u.rstrip('/').split('/')[-1] if u!='/' else '','page_type':'home' if u=='/' else ('region_content' if u in {x['url'] for x in rc} else 'school_content')})
 with (REPORTS/'url-plan.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=pages[0]);w.writeheader();w.writerows(pages)
 (REPORTS/'url-plan.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding='utf-8')
 (REPORTS/'relation-map.json').write_text(json.dumps({'school_region':school_region,'schools_for_region':schools_for_region},ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'pages':len(pages),'regions':len(rc),'schools':len(sc),'unique_schools':len(school_hub_by_code),'mapped':len(school_region),'relations':len(school_region)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
