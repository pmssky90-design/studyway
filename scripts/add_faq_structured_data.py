from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output"
SCHEMA_CLASS = "studyway-faq-jsonld"
QUESTION_ENDINGS = ("나요", "까요", "인가요", "하나요", "되나요", "좋나요")


class FaqParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[tuple[str, str]] = []
        self._heading_depth = 0
        self._paragraph_depth = 0
        self._heading_parts: list[str] = []
        self._paragraph_parts: list[str] = []
        self._pending_question = ""
        self._blocked = False

    @staticmethod
    def _clean(parts: list[str]) -> str:
        return " ".join("".join(parts).split())

    @staticmethod
    def _is_question(text: str) -> bool:
        return "?" in text or text.endswith(QUESTION_ENDINGS)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h2", "h3", "h4"}:
            self._heading_depth = 1
            self._heading_parts = []
            if self._pending_question:
                self._pending_question = ""
        elif self._heading_depth:
            self._heading_depth += 1
        elif tag == "p" and self._pending_question and not self._blocked:
            self._paragraph_depth = 1
            self._paragraph_parts = []
        elif self._paragraph_depth:
            self._paragraph_depth += 1
        elif self._pending_question and tag not in {"script", "style"}:
            self._blocked = True

    def handle_endtag(self, tag: str) -> None:
        if self._heading_depth:
            self._heading_depth -= 1
            if self._heading_depth == 0:
                text = self._clean(self._heading_parts)
                self._pending_question = text if self._is_question(text) else ""
                self._blocked = False
            return
        if self._paragraph_depth:
            self._paragraph_depth -= 1
            if self._paragraph_depth == 0:
                answer = self._clean(self._paragraph_parts)
                if self._pending_question and answer:
                    self.items.append((self._pending_question, answer))
                self._pending_question = ""
                self._blocked = False

    def handle_data(self, data: str) -> None:
        if self._heading_depth:
            self._heading_parts.append(data)
        elif self._paragraph_depth:
            self._paragraph_parts.append(data)


def parse_items(source: str) -> list[tuple[str, str]]:
    parser = FaqParser()
    parser.feed(source)
    parser.close()
    return parser.items


def schema_for(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
            for question, answer in items
        ],
    }


def markup(schema: dict) -> str:
    payload = json.dumps(schema, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json" class="{SCHEMA_CLASS}">{payload}</script>'


def existing_payloads(source: str) -> list[dict]:
    pattern = re.compile(
        rf'<script\b[^>]*class="[^"]*\b{SCHEMA_CLASS}\b[^"]*"[^>]*>(.*?)</script>',
        re.S,
    )
    return [json.loads(html.unescape(value)) for value in pattern.findall(source)]


def run(output: Path, check: bool) -> dict:
    counts = Counter()
    failures: list[dict] = []
    for page in sorted(output.rglob("index.html")):
        source = page.read_text(encoding="utf-8")
        items = parse_items(source)
        expected = schema_for(items) if items else None
        counts["html"] += 1
        counts["faq_pages" if items else "no_faq_pages"] += 1
        counts["questions"] += len(items)
        if not check:
            if existing_payloads(source):
                raise RuntimeError(f"existing {SCHEMA_CLASS}: {page}")
            if expected:
                if "</head>" not in source:
                    raise RuntimeError(f"missing </head>: {page}")
                source = source.replace("</head>", markup(expected) + "</head>", 1)
                page.write_text(source, encoding="utf-8")
                counts["written"] += 1
        try:
            payloads = existing_payloads(source)
        except json.JSONDecodeError:
            payloads = []
            errors = ["json_parse"]
        else:
            wanted = 1 if expected else 0
            errors = []
            if len(payloads) != wanted:
                errors.append("schema_count")
            if expected and payloads != [expected]:
                errors.append("schema_content")
        if errors and len(failures) < 20:
            failures.append({"path": str(page.relative_to(output)), "errors": errors})
    return {**dict(counts), "failures": failures, "result": "PASS" if not failures else "FAIL"}


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    cli.add_argument("--check", action="store_true")
    args = cli.parse_args()
    print(json.dumps(run(args.output.resolve(), args.check), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
