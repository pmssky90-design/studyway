from __future__ import annotations

import csv, html, json, re, shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_navigation_v4"
OUT = ROOT / "candidate_output_navigation_v4_school_ui"
REPORTS = ROOT / "reports" / "navigation-v4-school-ui"


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT)
    REPORTS.mkdir(parents=True, exist_ok=True)

    with (ROOT / "reports" / "url-plan.csv").open(encoding="utf-8-sig") as f:
        plan = list(csv.DictReader(f))
    bases = [r for r in plan if r["page_type"] == "school_content" and r["source_sheet"] == "(학교)과외"]
    grouped = defaultdict(lambda: defaultdict(list))
    for row in bases:
        province = "서울" if row["region"] == "서울" else "경기"
        area = row["district"].removesuffix("시")
        grouped[province][area].append((row["school_name"], row["url"]))

    blocks = ['<section id="schools" class="school-finder"><h2>학교별 과외</h2>']
    for province in ("서울", "경기"):
        areas = grouped[province]
        blocks.append(f'<section class="school-province" data-school-province="{province}"><h3>{province}</h3>')
        blocks.append('<div class="school-area-tabs" role="tablist" aria-label="학교 지역 선택">')
        for index, area in enumerate(sorted(areas)):
            active = " true" if index == 0 else " false"
            blocks.append(f'<button type="button" role="tab" aria-selected="{active.strip()}" data-school-tab="{html.escape(province)}::{html.escape(area)}">{html.escape(area)}</button>')
        blocks.append('</div><div class="school-area-panels">')
        for index, area in enumerate(sorted(areas)):
            active = " is-active" if index == 0 else ""
            blocks.append(f'<section class="school-area-panel{active}" data-school-panel="{html.escape(province)}::{html.escape(area)}"><h4>{html.escape(area)} 고등학교</h4><div class="school-link-grid">')
            for name, url in sorted(areas[area]):
                blocks.append(f'<a href="{url}">{html.escape(name)}</a>')
            blocks.append('</div></section>')
        blocks.append('</div></section>')
    blocks.append('</section>')
    schools = ''.join(blocks)

    home_path = OUT / "index.html"
    markup = home_path.read_text(encoding="utf-8")
    start = markup.index('<section id="schools">')
    end = markup.index('</article>', start)
    markup = markup[:start] + schools + markup[end:]
    markup = markup.replace('</head>', '<script>document.documentElement.classList.add("js")</script></head>', 1)
    markup = markup.replace('</body>', '<script src="/static/js/school-ui.js" defer></script></body>', 1)
    home_path.write_text(markup, encoding="utf-8")

    css = r'''

/* HOME school selector — navigation-v4 school UI candidate only */
.school-finder { margin-top: 3rem; }
.school-province { margin-top: 2rem; }
.school-area-tabs { display: flex; flex-wrap: wrap; gap: .55rem; margin: 1rem 0 1.25rem; }
.school-area-tabs button { appearance: none; border: 1px solid #d7deea; border-radius: 999px; background: #fff; color: #24324a; padding: .65rem .9rem; font: inherit; font-weight: 700; line-height: 1.2; cursor: pointer; white-space: normal; overflow-wrap: anywhere; }
.school-area-tabs button:hover, .school-area-tabs button:focus-visible { border-color: #3568d4; outline: 2px solid transparent; }
.school-area-tabs button[aria-selected="true"] { background: #2457c5; border-color: #2457c5; color: #fff; }
.school-area-panel { margin-top: 1rem; }
.school-link-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: .7rem; }
.school-link-grid a { min-width: 0; overflow-wrap: anywhere; word-break: keep-all; }
.js .school-area-panel { display: none; }
.js .school-area-panel.is-active { display: block; }
@media (max-width: 900px) { .school-link-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
@media (max-width: 520px) {
  .school-area-tabs { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: .45rem; }
  .school-area-tabs button { width: 100%; padding: .62rem .55rem; }
  .school-link-grid { grid-template-columns: minmax(0,1fr); }
  .school-finder, .school-province, .school-area-tabs, .school-area-panels, .school-area-panel { min-width: 0; max-width: 100%; }
}
'''
    css_path = OUT / "static" / "css" / "site.css"
    css_path.write_text(css_path.read_text(encoding="utf-8") + css, encoding="utf-8")
    js_path = OUT / "static" / "js" / "school-ui.js"
    js_path.parent.mkdir(parents=True, exist_ok=True)
    js_path.write_text(r'''document.addEventListener("DOMContentLoaded",()=>{document.querySelectorAll("[data-school-province]").forEach(region=>{const tabs=[...region.querySelectorAll("[data-school-tab]")];const panels=[...region.querySelectorAll("[data-school-panel]")];tabs.forEach(tab=>tab.addEventListener("click",()=>{const key=tab.dataset.schoolTab;tabs.forEach(item=>item.setAttribute("aria-selected",String(item===tab)));panels.forEach(panel=>panel.classList.toggle("is-active",panel.dataset.schoolPanel===key));}));});});''', encoding="utf-8")

    result = {"candidate": str(OUT), "seoul_areas": len(grouped["서울"]), "gyeonggi_areas": len(grouped["경기"]), "seoul_schools": sum(map(len, grouped["서울"].values())), "gyeonggi_schools": sum(map(len, grouped["경기"].values()))}
    (REPORTS / "build-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
