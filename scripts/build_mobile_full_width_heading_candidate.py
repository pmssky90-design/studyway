from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_images_mobile_dom_full_bleed"
OUT = ROOT / "candidate_output_images_mobile_dom_full_bleed_heading"
REPORTS = ROOT / "reports" / "images-mobile-dom-full-bleed-heading"

CSS = r'''

/* Mobile heading card aligns edge-for-edge with the full-bleed image sequence. */
@media (max-width: 767px) {
  .content-heading-card {
    position: relative;
    left: 50%;
    width: 100vw;
    max-width: none;
    margin: 0;
    transform: translateX(-50%);
    border-radius: 15px 15px 0 0;
  }
}
'''


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite existing candidate: {OUT}")
    shutil.copytree(SOURCE, OUT)
    REPORTS.mkdir(parents=True, exist_ok=True)
    css = OUT / "static" / "css" / "site.css"
    css.write_text(css.read_text(encoding="utf-8") + CSS, encoding="utf-8")
    for name in ("url-plan.csv", "url-plan.json", "relationship-plan.json"):
        shutil.copy2(ROOT / "reports" / "images-mobile-dom-full-bleed" / name, REPORTS / name)
    summary = {
        "source": str(SOURCE),
        "candidate": str(OUT),
        "changed_files": ["static/css/site.css"],
        "heading_mobile_width": "100vw",
        "h1_internal_padding": "inherited 20px from .content-heading-card",
    }
    (REPORTS / "build-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
