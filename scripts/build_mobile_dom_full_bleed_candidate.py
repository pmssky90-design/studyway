from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate_output_images_mobile_full_bleed_real_chrome"
OUT = ROOT / "candidate_output_images_mobile_dom_full_bleed"
REPORTS = ROOT / "reports" / "images-mobile-dom-full-bleed"

ARTICLE_RE = re.compile(
    r'<article>(?P<h1><h1>.*?</h1>)(?P<images><div class="content-image-sequence".*?</div>)(?P<body>.*?)</article>',
    re.DOTALL,
)

CSS = r'''

/* DOM-separated content shell: desktop retains the original single-card presentation. */
.content-shell {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: clamp(24px,5vw,56px);
  box-shadow: 0 14px 40px rgba(28,54,42,.06);
}
.content-heading-card,
.content-body-card {
  background: transparent;
  border: 0;
  border-radius: 0;
  padding: 0;
  box-shadow: none;
}

@media (max-width: 767px) {
  .content-shell {
    background: transparent;
    border: 0;
    border-radius: 0;
    padding: 0;
    box-shadow: none;
  }
  .content-heading-card,
  .content-body-card {
    width: 100%;
    background: var(--card);
    border: 1px solid var(--line);
    padding: 24px 20px;
    box-shadow: 0 14px 40px rgba(28,54,42,.06);
  }
  .content-heading-card {
    border-radius: 15px 15px 0 0;
    border-bottom: 0;
  }
  .content-heading-card h1 { margin-bottom: 0; }
  .content-body-card {
    border-radius: 0 0 15px 15px;
    border-top: 0;
  }
  .content-image-sequence {
    position: relative;
    left: 50%;
    width: 100vw;
    max-width: none;
    margin: 0;
    padding: 0;
    transform: translateX(-50%);
    overflow: visible;
  }
  .content-image-sequence img {
    display: block;
    width: 100%;
    max-width: none;
    height: auto;
    margin: 0;
    padding: 0;
    object-fit: contain;
  }
}
'''


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite existing candidate: {OUT}")
    shutil.copytree(SOURCE, OUT)
    REPORTS.mkdir(parents=True, exist_ok=True)
    css = OUT / "static" / "css" / "site.css"
    css.write_text(css.read_text(encoding="utf-8") + CSS, encoding="utf-8")

    changed = 0
    body_hashes: dict[str, str] = {}
    for path in OUT.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        match = ARTICLE_RE.search(text)
        if not match:
            continue
        body = match.group("body")
        relative = path.relative_to(OUT).as_posix()
        body_hashes[relative] = digest(body)
        replacement = (
            '<div class="content-shell">'
            '<section class="content-heading-card">' + match.group("h1") + '</section>'
            + match.group("images")
            + '<article class="content-body-card">' + body + '</article>'
            + '</div>'
        )
        updated = text[: match.start()] + replacement + text[match.end() :]
        if updated.count('class="content-image-sequence"') != 1:
            raise RuntimeError(f"Unexpected image sequence count: {relative}")
        path.write_text(updated, encoding="utf-8")
        changed += 1

    for name in ("url-plan.csv", "url-plan.json", "relationship-plan.json"):
        shutil.copy2(ROOT / "reports" / "images-mobile-full-bleed-real-chrome" / name, REPORTS / name)
    summary = {
        "source": str(SOURCE),
        "candidate": str(OUT),
        "html_wrappers_changed": changed,
        "preserved_body_substrings": len(body_hashes),
        "body_substring_hashes": body_hashes,
        "changed_asset": "static/css/site.css",
    }
    (REPORTS / "build-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k:v for k,v in summary.items() if k != "body_substring_hashes"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
