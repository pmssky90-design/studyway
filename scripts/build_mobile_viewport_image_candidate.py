from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_images_mobile_wide"
OUT = ROOT / "candidate_output_images_mobile_viewport"
REPORTS = ROOT / "reports" / "images-mobile-viewport"

MOBILE_CSS = r'''

/* Mobile near-viewport content images: image sequence only */
@media (max-width: 640px) {
  .content-image-sequence {
    position: relative;
    left: 50%;
    width: calc(100vw - 6px);
    max-width: none;
    margin-left: 0;
    margin-right: 0;
    transform: translateX(-50%);
  }
  .content-image-sequence img {
    display: block;
    width: 100%;
    max-width: none;
    height: auto;
    margin-left: 0;
    margin-right: 0;
    object-fit: contain;
  }
}
'''


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite existing candidate: {OUT}")
    shutil.copytree(SOURCE, OUT)
    REPORTS.mkdir(parents=True, exist_ok=True)
    css = OUT / "static" / "css" / "site.css"
    css.write_text(css.read_text(encoding="utf-8") + MOBILE_CSS, encoding="utf-8")
    for name in ("url-plan.csv", "url-plan.json", "relationship-plan.json"):
        shutil.copy2(ROOT / "reports" / "images-mobile-wide" / name, REPORTS / name)
    summary = {
        "source": str(SOURCE),
        "candidate": str(OUT),
        "changed_files": ["static/css/site.css"],
        "mobile_target_width": "calc(100vw - 6px)",
        "target_side_gap_px": 3,
    }
    (REPORTS / "build-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
