from pathlib import Path
from html.parser import HTMLParser
from html import escape
from collections import Counter
import json

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "candidate_output_search_meta_final"
REPORT = ROOT / "reports" / "search-meta-final"
REPORT.mkdir(parents=True, exist_ok=True)
HOME_IMAGE = "https://studyway.kr/assets/images/home/studyway-main-hero.png"


class HeadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_parts = []
        self.meta = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            self.meta.append(data)
        elif tag == "link":
            self.links.append(data)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)

    def named(self, name):
        return [m.get("content", "") for m in self.meta if m.get("name") == name]

    def property(self, name):
        return [m.get("content", "") for m in self.meta if m.get("property") == name]

    def canonical(self):
        return [x.get("href", "") for x in self.links if x.get("rel") == "canonical"]


def meta_property(name, content):
    return f'<meta property="{name}" content="{escape(content, quote=True)}">'


def meta_name(name, content):
    return f'<meta name="{name}" content="{escape(content, quote=True)}">'


def main():
    pages = sorted(OUTPUT.rglob("index.html"))
    added = Counter()
    changed = already_complete = 0
    for page in pages:
        source = page.read_text(encoding="utf-8")
        parser = HeadParser()
        parser.feed(source)
        title = "".join(parser.title_parts).strip()
        descriptions = parser.named("description")
        canonicals = parser.canonical()
        if not title or len(descriptions) != 1 or len(canonicals) != 1:
            raise RuntimeError(f"invalid source head: {page}")
        description = descriptions[0]
        canonical = canonicals[0]
        is_home = page == OUTPUT / "index.html"
        og_type = "website" if is_home else "article"
        images = parser.property("og:image")
        if len(images) > 1:
            raise RuntimeError(f"duplicate og:image: {page}")
        image = images[0] if images else HOME_IMAGE

        additions = []
        wanted_properties = {
            "og:title": title,
            "og:description": description,
            "og:url": canonical,
            "og:type": og_type,
            "og:image": image,
        }
        for key, value in wanted_properties.items():
            current = parser.property(key)
            if len(current) > 1:
                raise RuntimeError(f"duplicate {key}: {page}")
            if not current:
                additions.append(meta_property(key, value))
                added[key] += 1

        if is_home:
            for key, value in (("og:image:width", "1536"), ("og:image:height", "1024")):
                current = parser.property(key)
                if len(current) > 1:
                    raise RuntimeError(f"duplicate {key}: {page}")
                if not current:
                    additions.append(meta_property(key, value))
                    added[key] += 1

        wanted_names = {
            "twitter:card": "summary_large_image",
            "twitter:title": title,
            "twitter:description": description,
            "twitter:image": image,
        }
        for key, value in wanted_names.items():
            current = parser.named(key)
            if len(current) > 1:
                raise RuntimeError(f"duplicate {key}: {page}")
            if not current:
                additions.append(meta_name(key, value))
                added[key] += 1

        if additions:
            if source.count("</head>") != 1:
                raise RuntimeError(f"unexpected head closing tag: {page}")
            page.write_text(source.replace("</head>", "".join(additions) + "</head>", 1), encoding="utf-8")
            changed += 1
        else:
            already_complete += 1

    result = {"html_pages": len(pages), "changed": changed, "already_complete": already_complete, "added": added}
    (REPORT / "build.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
