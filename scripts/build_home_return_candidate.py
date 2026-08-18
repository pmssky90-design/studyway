from __future__ import annotations

import csv, json, re, shutil
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_navigation_v4_school_ui_bidirectional"
OUT = ROOT / "candidate_output_navigation_v4_bidirectional_home_return"
REPORTS = ROOT / "reports" / "navigation-v4-bidirectional-home-return"


def file_for(url: str) -> Path:
    return OUT / unquote(url.strip("/")) / "index.html"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT)
    REPORTS.mkdir(parents=True, exist_ok=True)

    with (ROOT / "reports" / "url-plan.csv").open(encoding="utf-8-sig") as f:
        plan = list(csv.DictReader(f))
    content = [r for r in plan if r["page_type"] in {"region_content", "school_content"}]
    changed = 0
    for row in content:
        path = file_for(row["url"])
        markup = path.read_text(encoding="utf-8")
        block = '<nav class="home-return" aria-label="홈으로 돌아가기"><a href="/">StudyWay 홈으로</a></nav>'
        if block not in markup:
            markup = markup.replace("</main>", block + "</main>", 1)
            path.write_text(markup, encoding="utf-8")
            changed += 1

    source_reports = ROOT / "reports" / "navigation-v4-school-ui-bidirectional"
    for name in ("url-plan.csv", "url-plan.json", "relationship-plan.json", "relationship-audit.json"):
        shutil.copy2(source_reports / name, REPORTS / name)
    summary = {"content_pages": len(content), "home_return_added": changed}
    (REPORTS / "build-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
