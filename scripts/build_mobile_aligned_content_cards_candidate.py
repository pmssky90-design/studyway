from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_images_mobile_dom_full_bleed_heading"
OUT = ROOT / "candidate_output_images_mobile_dom_full_bleed_aligned_cards"
REPORTS = ROOT / "reports" / "images-mobile-dom-full-bleed-aligned-cards"

CSS = r'''

/* Mobile body card aligns edge-for-edge with the heading card and image sequence. */
@media (max-width: 767px) {
  .content-body-card {
    position: relative;
    left: 50%;
    width: 100vw;
    max-width: none;
    margin: 0;
    transform: translateX(-50%);
    border-radius: 0 0 15px 15px;
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
        shutil.copy2(ROOT / "reports" / "images-mobile-dom-full-bleed-heading" / name, REPORTS / name)
    result = {
        "source": str(SOURCE),
        "candidate": str(OUT),
        "changed_files": ["static/css/site.css"],
        "mobile_outer_width": {
            "heading": "100vw",
            "images": "100vw",
            "body": "100vw",
        },
        "body_internal_padding": "inherited 20px",
    }
    (REPORTS / "build-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
