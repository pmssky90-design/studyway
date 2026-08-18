from __future__ import annotations

import csv, html, json, re, shutil
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_navigation_v4_school_ui"
OUT = ROOT / "candidate_output_navigation_v4_school_ui_bidirectional"
REPORTS = ROOT / "reports" / "navigation-v4-school-ui-bidirectional"


def file_for(url: str) -> Path:
    return OUT / unquote(url.strip("/")) / "index.html"


def append_navigation(url: str, title: str, links: list[tuple[str, str]]) -> None:
    seen = set()
    unique = []
    for label, href in links:
        if href != url and href not in seen:
            seen.add(href); unique.append((label, href))
    if not unique:
        return
    block = f'<section class="related-navigation bidirectional-links"><h2>{html.escape(title)}</h2><div class="link-grid">' + ''.join(f'<a href="{href}">{html.escape(label)}</a>' for label, href in unique) + '</div></section>'
    path = file_for(url); markup = path.read_text(encoding="utf-8")
    markup = markup.replace('</article>', '</article>' + block, 1)
    path.write_text(markup, encoding="utf-8")


def semantic_links(row: dict, rows: list[dict]) -> list[tuple[str, str]]:
    by_kind = {r["source_sheet"].removeprefix("(학교)"): r for r in rows}
    kind = row["source_sheet"].removeprefix("(학교)")
    entity = row["school_name"] or row["dong_eup_myeon"] or row["district"]
    links = [(entity + "과외", by_kind["과외"]["url"])]
    subject = "수학" if "수학" in kind else "영어" if "영어" in kind else ""
    grade = next((g for g in ("고1", "고2", "고3", "중1", "중2", "중3") if kind.startswith(g)), "")
    if subject and subject + "과외" in by_kind:
        links.append((entity + subject + "과외", by_kind[subject + "과외"]["url"]))
    if grade and grade + "과외" in by_kind:
        links.append((entity + grade + "과외", by_kind[grade + "과외"]["url"]))
    if subject and grade and grade[0] in "고중":
        number = int(grade[1])
        for sibling_number in (number - 1, number + 1):
            sibling = grade[0] + str(sibling_number) + subject + "과외"
            if sibling in by_kind:
                links.append((entity + sibling, by_kind[sibling]["url"]))
    return links


def main() -> None:
    if OUT.exists(): shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT)
    REPORTS.mkdir(parents=True, exist_ok=True)
    with (ROOT / "reports" / "url-plan.csv").open(encoding="utf-8-sig") as f:
        plan = list(csv.DictReader(f))
    region = [r for r in plan if r["page_type"] == "region_content"]
    school = [r for r in plan if r["page_type"] == "school_content"]
    by_region = defaultdict(list); by_school = defaultdict(list)
    for r in region: by_region[r["hub_url"]].append(r)
    for r in school: by_school[r["parent_url"]].append(r)

    region_relations = []
    for rows in by_region.values():
        base = next(r for r in rows if r["source_sheet"] == "과외")
        for row in rows:
            if row is base: continue
            region_relations.append((base["url"], row["url"]))
            append_navigation(row["url"], "이 지역의 관련 학습", semantic_links(row, rows))

    school_relations = []
    for rows in by_school.values():
        base = next(r for r in rows if r["source_sheet"] == "(학교)과외")
        for row in rows:
            if row is base: continue
            school_relations.append((base["url"], row["url"]))
            append_navigation(row["url"], "이 학교의 관련 학습", semantic_links(row, rows))

    # Existing breadcrumbs identify the actual top-region content parent without introducing hubs.
    hierarchy = []
    content_urls = {r["url"] for r in region + school}
    for row in region:
        if row["source_sheet"] != "과외" or not row["dong_eup_myeon"]: continue
        markup = file_for(row["url"]).read_text(encoding="utf-8")
        crumb = re.search(r'<nav class="breadcrumbs".*?</nav>', markup, re.S)
        hrefs = re.findall(r'href="([^"]+)"', crumb.group()) if crumb else []
        parent = next((href for href in hrefs if href != "/" and href != row["url"] and href in content_urls), None)
        if parent:
            hierarchy.append((parent, row["url"]))
            parent_name = next((r["dong_eup_myeon"] or r["district"] for r in region if r["url"] == parent), "상위 지역")
            append_navigation(row["url"], "상위 지역", [(parent_name + "과외", parent)])

    summary = {
        "region_representative_children": len(region_relations),
        "school_representative_children": len(school_relations),
        "region_hierarchy": len(hierarchy),
        "region_relations": region_relations,
        "school_relations": school_relations,
        "hierarchy_relations": hierarchy,
    }
    (REPORTS / "relationship-plan.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(ROOT / "reports" / "navigation-v4-school-ui" / "url-plan.csv", REPORTS / "url-plan.csv")
    shutil.copy2(ROOT / "reports" / "navigation-v4-school-ui" / "url-plan.json", REPORTS / "url-plan.json")
    print(json.dumps({k: v for k, v in summary.items() if not isinstance(v, list)}, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
