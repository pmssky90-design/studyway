"""Idempotent region navigation pass over the final static output.

Run after content/design generation. Dry run is the default; --apply writes HTML.
Existing content and navigation are preserved byte-for-byte.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
START = '<!-- REGION_TOPIC_LINKS_START -->'
END = '<!-- REGION_TOPIC_LINKS_END -->'
BLOCK = re.compile(re.escape(START) + r'.*?' + re.escape(END), re.S)
TOPIC = re.compile(r'^(초등|중등|고등|중[123]|고[123])?(수학|영어)?과외$')


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = set()

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        href = dict(attrs).get('href', '')
        parsed = urlsplit(href)
        if parsed.netloc not in ('', 'studyway.kr', 'www.studyway.kr'):
            return
        if parsed.path.startswith('/region/'):
            self.targets.add(unquote(parsed.path).rstrip('/') + '/')


def links(markup):
    parser = Links()
    parser.feed(markup)
    return parser.targets


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(output: Path, apply=False):
    pages = {}
    groups = defaultdict(dict)
    for path in sorted((output / 'region').rglob('index.html')):
        topic = path.parent.name
        if not TOPIC.fullmatch(topic):
            continue
        route = '/' + path.relative_to(output).parent.as_posix() + '/'
        raw = path.read_bytes()
        markup = raw.decode('utf-8')
        clean = BLOCK.sub('', markup)
        if markup.count(START) > 1 or markup.count(START) != markup.count(END):
            raise ValueError(f'Invalid managed markers: {route}')
        heading = re.search(r'<h1\b[^>]*>(.*?)</h1>', clean, re.S)
        if not heading or clean.count('</main>') != 1:
            raise ValueError(f'Missing heading or main boundary: {route}')
        group = path.parent.parent.relative_to(output).as_posix()
        pages[route] = dict(path=path, raw=raw, clean=clean, group=group,
                            topic=topic, label=html.unescape(re.sub('<[^>]*>', '', heading[1])),
                            existing=links(clean))
        groups[group][topic] = route

    desired = {route: set() for route in pages}
    def connect(a, b):
        if a and b and a != b:
            desired[a].add(b)
            desired[b].add(a)

    parent_groups = {}
    for group, topics in groups.items():
        base = topics.get('과외')
        if not base:
            raise ValueError(f'Missing representative: {group}')
        for topic, route in topics.items():
            connect(base, route)
            level, subject = TOPIC.fullmatch(topic).groups()
            level, subject = level or '', subject or ''
            if subject:
                connect(route, topics.get(subject + '과외'))
            if level:
                connect(route, topics.get(level + '과외'))
            if re.fullmatch('[중고][123]', level):
                band = level[0] + '등'
                connect(route, topics.get(band + subject + '과외'))
                for n in (int(level[1]) - 1, int(level[1]) + 1):
                    connect(route, topics.get(level[0] + str(n) + subject + '과외'))

        # Reuse the site's explicit breadcrumb hierarchy, never infer from a name prefix.
        crumb = re.search(r'<nav class="breadcrumbs".*?</nav>', pages[base]['clean'], re.S)
        candidates = []
        if crumb:
            for href in re.findall(r'href="([^"]+)"', crumb[0]):
                parent = unquote(urlsplit(html.unescape(href)).path)
                if parent in pages and pages[parent]['group'] != group and pages[parent]['topic'] == '과외':
                    candidates.append(pages[parent]['group'])
        if candidates:
            parent_group = candidates[-1]
            parent_groups[group] = parent_group
            for topic, route in topics.items():
                connect(route, groups[parent_group].get(topic))

    broken_before = sorted({(route, target) for route, p in pages.items()
                            for target in p['existing']
                            if not (output / target.strip('/') / 'index.html').is_file()})
    if broken_before:
        raise ValueError(f'Existing broken region links: {broken_before[:10]}')
    plans = {}
    added_counts = Counter()
    for route, p in pages.items():
        missing = desired[route] - p['existing']
        sections = defaultdict(list)
        for target in sorted(missing):
            other = pages[target]
            if other['group'] == p['group']:
                section = '같은 지역의 과목·학년별 과외'
            elif parent_groups.get(p['group']) == other['group']:
                section = '상위 지역의 같은 과외 유형'
            else:
                section = '세부 지역의 같은 과외 유형'
            sections[section].append((target, other['label']))
        block = ''
        if sections:
            block = START
            for title, targets in sections.items():
                block += '<section class="related-navigation region-topic-links"><h2>' + title + '</h2><div class="link-grid">'
                block += ''.join('<a href="' + quote(target, safe='/-._~') + '">' + html.escape(label) + '</a>' for target, label in targets)
                block += '</div></section>'
            block += END
        updated = p['clean'].replace('</main>', block + '</main>')
        # Check the rendered HTML, not just the in-memory relationship plan.
        actual = links(updated)
        if not desired[route] <= actual or BLOCK.sub('', updated) != p['clean']:
            raise ValueError(f'Navigation or content preservation failed: {route}')
        plans[route] = updated.encode('utf-8')
        added_counts[route] = len(missing)

    inbound_before = Counter(t for p in pages.values() for t in p['existing'] if t in pages)
    inbound_after = Counter(t for route, p in pages.items() for t in p['existing'] | desired[route] if t in pages)
    summary = dict(region_groups=len(groups), region_pages=len(pages), hierarchy_groups=len(parent_groups),
                   changed_pages=sum(plans[r] != p['raw'] for r, p in pages.items()),
                   added_directed_links=sum(added_counts.values()),
                   max_added_links_per_page=max(added_counts.values(), default=0),
                   max_total_region_links=max(len(p['existing'] | desired[r]) for r, p in pages.items()),
                   required_bidirectional_pairs=sum(map(len, desired.values())) // 2,
                   missing_required_links=0, broken_region_links=0,
                   min_inbound_before=min(inbound_before[r] for r in pages),
                   min_inbound_after=min(inbound_after[r] for r in pages),
                   content_and_head_preserved=True,
                   largest_additions=[dict(url=r, links=n) for r, n in added_counts.most_common(5)])
    if apply:
        # Complete preflight above before touching any page.
        for route, p in pages.items():
            if plans[route] != p['raw']:
                p['path'].write_bytes(plans[route])
        for route, p in pages.items():
            if digest(p['path'].read_bytes()) != digest(plans[route]):
                raise ValueError(f'Write verification failed: {route}')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.apply), ensure_ascii=False, indent=2))
