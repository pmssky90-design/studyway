from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_images"
OUT = ROOT / "candidate_output_images_mobile_wide"
REPORTS = ROOT / "reports" / "images-mobile-wide"

MOBILE_CSS = r'''

/* Mobile wide content images — image sequence only */
@media (max-width: 640px) {
  .content-image-sequence {
    width: calc(100vw - 16px);
    max-width: none;
    margin-left: 50%;
    margin-right: 0;
    transform: translateX(-50%);
  }
  .content-image-sequence img {
    width: 100%;
    max-width: none;
    height: auto;
    margin-left: auto;
    margin-right: auto;
    object-fit: contain;
  }
}
'''


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT)
    REPORTS.mkdir(parents=True, exist_ok=True)
    css = OUT / "static" / "css" / "site.css"
    css.write_text(css.read_text(encoding="utf-8") + MOBILE_CSS, encoding="utf-8")
    for name in ("url-plan.csv", "url-plan.json", "relationship-plan.json", "relationship-audit.json", "image-inventory.json", "image-audit.json"):
        shutil.copy2(ROOT / "reports" / "images" / name, REPORTS / name)
    summary = {"candidate": str(OUT), "changed_files": ["static/css/site.css"], "mobile_target_width": "calc(100vw - 16px)"}
    (REPORTS / "build-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
