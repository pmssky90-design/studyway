from pathlib import Path
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "candidate_output_mobile_contact_cta_emphasis"
REPORT = ROOT / "reports" / "mobile-contact-cta-emphasis"
REPORT.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location(
    "base_cta", ROOT / "scripts" / "add_mobile_contact_cta.py"
)
base_cta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base_cta)
OLD_CTA = base_cta.CTA

NEW_CTA = (
    '<nav class="mobile-contact-cta mobile-contact-cta--emphasis" aria-label="전화 및 문자 문의">'
    '<a class="mobile-contact-cta__call" href="tel:01049479030" aria-label="010-4947-9030으로 전화하기">'
    '<span class="mobile-contact-cta__icon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false">'
    '<path d="M6.62 10.79a15.46 15.46 0 0 0 6.59 6.59l2.2-2.2a1 1 0 0 1 1.02-.24 11.36 11.36 0 0 0 3.57.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1 11.36 11.36 0 0 0 .57 3.57 1 1 0 0 1-.25 1.02l-2.2 2.2Z"/></svg></span>'
    '<span class="mobile-contact-cta__copy"><strong>전화하기</strong><small>010-4947-9030</small></span></a>'
    '<a class="mobile-contact-cta__sms" href="sms:01049479030" aria-label="010-4947-9030으로 문자 보내기">'
    '<span class="mobile-contact-cta__icon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false">'
    '<path d="M4 4h16v12H7l-3 3V4Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M7 8h10M7 12h7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></span>'
    '<span class="mobile-contact-cta__copy"><strong>문자하기</strong><small>010-4947-9030</small></span></a></nav>'
)

CSS = r'''

/* Emphasis mobile CTA comparison; CTA-only overrides. */
@media(max-width:767px){
  body{padding-bottom:calc(98px + env(safe-area-inset-bottom,0px))}
  .mobile-contact-cta--emphasis{bottom:max(8px,env(safe-area-inset-bottom,0px));min-height:72px;border:2px solid rgba(255,255,255,.92);border-radius:16px;background:#fff;box-shadow:0 4px 16px rgba(0,0,0,.18)}
  .mobile-contact-cta--emphasis a{gap:9px;min-height:72px;padding:9px 10px;color:#fff;white-space:normal}
  .mobile-contact-cta--emphasis .mobile-contact-cta__call{background:#146bd9;border-right:1px solid rgba(255,255,255,.38)}
  .mobile-contact-cta--emphasis .mobile-contact-cta__sms{background:#16b978}
  .mobile-contact-cta__icon{display:flex;flex:0 0 36px;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,.14)}
  .mobile-contact-cta__icon svg{display:block;width:21px;height:21px;color:#fff;fill:currentColor}
  .mobile-contact-cta__copy{display:flex;min-width:0;flex-direction:column;align-items:flex-start;gap:4px;white-space:nowrap}
  .mobile-contact-cta__copy strong{font-size:1rem;font-weight:800;line-height:1}
  .mobile-contact-cta__copy small{font-size:.78rem;font-weight:650;line-height:1;letter-spacing:-.01em}
}
@media(max-width:330px){
  .mobile-contact-cta--emphasis a{gap:6px;padding:8px 6px}
  .mobile-contact-cta__icon{flex-basis:32px;width:32px;height:32px}
  .mobile-contact-cta__icon svg{width:19px;height:19px}
  .mobile-contact-cta__copy strong{font-size:.94rem}
  .mobile-contact-cta__copy small{font-size:.72rem}
}
'''


def main():
    pages = sorted(OUTPUT.rglob("index.html"))
    changed = already = 0
    for page in pages:
        html = page.read_text(encoding="utf-8")
        if html.count(NEW_CTA) == 1:
            already += 1
            continue
        if html.count(OLD_CTA) != 1:
            raise RuntimeError(f"unexpected CTA count: {page}")
        page.write_text(html.replace(OLD_CTA, NEW_CTA, 1), encoding="utf-8")
        changed += 1
    css_path = OUTPUT / "static" / "css" / "site.css"
    css = css_path.read_text(encoding="utf-8")
    css_added = "Emphasis mobile CTA comparison" not in css
    if css_added:
        css_path.write_text(css + CSS, encoding="utf-8")
    result = {"html_pages": len(pages), "changed": changed, "already": already, "css_added": css_added}
    (REPORT / "build.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
