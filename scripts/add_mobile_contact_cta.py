from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "candidate_output_mobile_contact_cta"
REPORT = ROOT / "reports" / "mobile-contact-cta"
REPORT.mkdir(parents=True, exist_ok=True)

CTA = (
    '<nav class="mobile-contact-cta" aria-label="전화 및 문자 문의">'
    '<a class="mobile-contact-cta__call" href="tel:01049479030" '
    'aria-label="010-4947-9030으로 전화하기"><span aria-hidden="true">☎</span>'
    '<span>전화하기</span></a>'
    '<a class="mobile-contact-cta__sms" href="sms:01049479030" '
    'aria-label="010-4947-9030으로 문자 보내기"><span aria-hidden="true">✉</span>'
    '<span>문자하기</span></a></nav>'
)

CSS = r'''

/* Mobile contact CTA; hidden at 768px and above. */
.mobile-contact-cta{display:none}
@media(max-width:767px){
  body{padding-bottom:calc(80px + env(safe-area-inset-bottom,0px))}
  .mobile-contact-cta{position:fixed;z-index:90;left:12px;right:12px;bottom:calc(10px + env(safe-area-inset-bottom,0px));display:grid;grid-template-columns:repeat(2,minmax(0,1fr));min-height:56px;overflow:hidden;border:1px solid #bfd1cb;border-radius:15px;background:#fff;box-shadow:0 8px 24px rgba(23,63,51,.18)}
  .mobile-contact-cta a{display:flex;align-items:center;justify-content:center;gap:8px;min-width:0;min-height:56px;padding:10px 12px;color:#203d35;font-size:1rem;font-weight:750;line-height:1;text-align:center;text-decoration:none;white-space:nowrap}
  .mobile-contact-cta__call{background:#e4eef9;border-right:1px solid #bfd1dc}
  .mobile-contact-cta__sms{background:#e4f2eb}
  .mobile-contact-cta a:active{filter:brightness(.97)}
}
'''


def main():
    pages = sorted(OUTPUT.rglob("index.html"))
    changed = 0
    already = 0
    for page in pages:
        html = page.read_text(encoding="utf-8")
        if 'class="mobile-contact-cta"' in html:
            already += 1
            continue
        if html.count("</body>") != 1:
            raise RuntimeError(f"unexpected body closing tag count: {page}")
        page.write_text(html.replace("</body>", CTA + "</body>", 1), encoding="utf-8")
        changed += 1

    css_path = OUTPUT / "static" / "css" / "site.css"
    css = css_path.read_text(encoding="utf-8")
    css_added = "Mobile contact CTA; hidden" not in css
    if css_added:
        css_path.write_text(css + CSS, encoding="utf-8")

    result = {
        "html_pages": len(pages),
        "changed": changed,
        "already_present": already,
        "css_added": css_added,
    }
    (REPORT / "build.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
