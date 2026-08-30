from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output"
MAX_DESCRIPTION = 155


def clean_markup(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", value)).split())


def tag_text(source: str, tag: str) -> str:
    match = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", source, re.I | re.S)
    if not match:
        raise ValueError(f"missing {tag}")
    return clean_markup(match.group(1))


def normalized(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value).lower()


def title_for(source: str, relative_path: str) -> str:
    h1 = tag_text(source, "h1")
    old_title = tag_text(source, "title")
    if re.fullmatch(r".+ \| .*(?:지역 맞춤 학습|학교별 학습) \| StudyWay", old_title):
        return old_title
    parts = [part.strip() for part in old_title.split("|")]
    context_parts = [part.strip() for part in parts[1].split("·")] if len(parts) > 1 else []
    context_parts = [
        part
        for part in context_parts
        if part not in {"지역별 과외", "학교별 과외"}
        and normalized(part) not in normalized(h1)
    ]
    if relative_path.startswith("region/"):
        context = f"{' · '.join(context_parts)} 지역 맞춤 학습" if context_parts else "지역 맞춤 학습"
    else:
        context = f"{' · '.join(context_parts)} 학교별 학습" if context_parts else "학교별 학습"
    return f"{h1} | {context} | StudyWay"


def description_for(source: str) -> str:
    h1 = tag_text(source, "h1")
    article = re.search(
        r'<article\b[^>]*class="[^"]*content-body-card[^"]*"[^>]*>(.*?)</article>',
        source,
        re.I | re.S,
    )
    if not article:
        raise ValueError("missing content article")
    paragraphs = [
        clean_markup(value)
        for value in re.findall(r"<p\b[^>]*>(.*?)</p>", article.group(1), re.I | re.S)
    ]
    sentences: list[str] = []
    for paragraph in paragraphs:
        sentences.extend(part.strip() for part in re.split(r"(?<=[.!?])\s+", paragraph) if part.strip())

    result = h1.rstrip(".!?") + ". "
    for sentence in sentences:
        if not re.search(r"[.!?]$", sentence):
            sentence += "."
        separator = "" if result.endswith(" ") else " "
        if len(result) + len(separator) + len(sentence) <= MAX_DESCRIPTION:
            result += separator + sentence
        if len(result) >= 95:
            break
    if result.endswith(" "):
        result += "학생의 현재 학습 흐름과 과목별 공부 방법을 구체적으로 살펴봅니다."
    return result


def replace_title(source: str, value: str) -> str:
    pattern = re.compile(r"(<title>).*?(</title>)", re.I | re.S)
    if len(pattern.findall(source)) != 1:
        raise ValueError("unexpected title count")
    escaped = html.escape(value)
    return pattern.sub(lambda match: match.group(1) + escaped + match.group(2), source, count=1)


def replace_meta(source: str, key: str, name: str, value: str) -> str:
    pattern = re.compile(
        rf'(<meta\b(?=[^>]*\b{key}="{re.escape(name)}")[^>]*\bcontent=")[^"]*(")',
        re.I,
    )
    if len(pattern.findall(source)) != 1:
        raise ValueError(f"unexpected {key}={name} count")
    escaped = html.escape(value, quote=True)
    return pattern.sub(lambda match: match.group(1) + escaped + match.group(2), source, count=1)


def expected_source(source: str, relative_path: str) -> tuple[str, str, str]:
    title = title_for(source, relative_path)
    description = description_for(source)
    updated = replace_title(source, title)
    for key, name, value in (
        ("name", "description", description),
        ("property", "og:title", title),
        ("property", "og:description", description),
        ("name", "twitter:title", title),
        ("name", "twitter:description", description),
    ):
        updated = replace_meta(updated, key, name, value)
    return updated, title, description


def run(output: Path, check: bool) -> dict:
    counts = Counter()
    failures: list[dict] = []
    titles: Counter[str] = Counter()
    descriptions: Counter[str] = Counter()
    for page in sorted(output.rglob("index.html")):
        relative = page.relative_to(output).as_posix()
        source = page.read_text(encoding="utf-8")
        counts["html"] += 1
        if relative == "index.html":
            counts["home_unchanged"] += 1
            continue
        try:
            expected, title, description = expected_source(source, relative)
        except ValueError as error:
            if len(failures) < 20:
                failures.append({"path": relative, "error": str(error)})
            continue
        titles[title] += 1
        descriptions[description] += 1
        counts["title_over_60"] += int(len(title) > 60)
        counts["description_over_155"] += int(len(description) > MAX_DESCRIPTION)
        counts["description_not_complete"] += int(not bool(re.search(r"[.!?]$", description)))
        if source != expected:
            if check:
                if len(failures) < 20:
                    failures.append({"path": relative, "error": "meta_mismatch"})
            else:
                page.write_text(expected, encoding="utf-8")
                counts["written"] += 1
        else:
            counts["unchanged"] += 1

    counts["duplicate_titles"] = sum(value > 1 for value in titles.values())
    counts["duplicate_descriptions"] = sum(value > 1 for value in descriptions.values())
    for key in ("title_over_60", "description_over_155", "description_not_complete", "duplicate_titles", "duplicate_descriptions"):
        if counts[key] and len(failures) < 20:
            failures.append({"error": key, "count": counts[key]})
    return {**dict(counts), "failures": failures, "result": "PASS" if not failures else "FAIL"}


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    cli.add_argument("--check", action="store_true")
    args = cli.parse_args()
    print(json.dumps(run(args.output.resolve(), args.check), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
