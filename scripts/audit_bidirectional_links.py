import argparse
import csv
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit


REPRESENTATIVE = "\uacfc\uc678"


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


def page_info(url):
    parts = [unquote(part) for part in url.strip("/").split("/")]
    if parts[:1] == ["region"]:
        return "region", tuple(parts[1:-1]), parts[-1]
    if parts[:1] == ["school"]:
        return "school", tuple(parts[1:-1]), parts[-1]
    return "home", (), ""


def html_path(root, url):
    if url == "/":
        return root / "index.html"
    return root.joinpath(*(unquote(part) for part in url.strip("/").split("/"))) / "index.html"


def load_graph(root, urls):
    decoded = {unquote(url): url for url in urls}
    graph = {}
    broken = []
    for url in sorted(urls):
        parser = LinkParser()
        parser.feed(html_path(root, url).read_text(encoding="utf-8"))
        targets = set()
        for href in parser.links:
            parsed = urlsplit(href)
            if parsed.scheme not in ("", "http", "https"):
                continue
            if parsed.netloc and parsed.netloc not in ("studyway.kr", "www.studyway.kr"):
                continue
            path = unquote(urlsplit(urljoin("https://studyway.kr" + url, href)).path)
            if not path.endswith("/"):
                path += "/"
            target = decoded.get(path)
            if target:
                targets.add(target)
            elif path.startswith(("/region/", "/school/")):
                broken.append((url, path))
        graph[url] = targets
    return graph, broken


def same_group_pairs(urls, kind):
    index = {page_info(url): url for url in urls}
    groups = {group for page_kind, group, _ in index if page_kind == kind}
    pairs = set()
    for group in groups:
        representative = index[(kind, group, REPRESENTATIVE)]
        for (page_kind, candidate_group, topic), child in index.items():
            if page_kind == kind and candidate_group == group and topic != REPRESENTATIVE:
                pairs.add((representative, child))
    return pairs


def discovered_pairs(graph, predicate, orientation):
    pairs = set()
    for source, targets in graph.items():
        for target in targets:
            if predicate(source, target):
                pairs.add(orientation(source, target))
    return pairs


def check_pairs(graph, pairs):
    missing = []
    for left, right in sorted(pairs):
        if right not in graph[left]:
            missing.append({"source": left, "target": right, "direction": "forward"})
        if left not in graph[right]:
            missing.append({"source": right, "target": left, "direction": "reverse"})
    normal = sum(right in graph[left] and left in graph[right] for left, right in pairs)
    return {"normal": normal, "total": len(pairs), "missing": missing}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--url-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    with args.url_plan.open(encoding="utf-8-sig", newline="") as handle:
        urls = {row["url"] for row in csv.DictReader(handle)}

    target_graph, broken = load_graph(args.target, urls)
    baseline_graph, baseline_broken = load_graph(args.baseline, urls)

    region_child = same_group_pairs(urls, "region")
    school_child = same_group_pairs(urls, "school")

    def is_parent_detail(left, right):
        left_kind, left_group, left_topic = page_info(left)
        right_kind, right_group, right_topic = page_info(right)
        shapes = {len(left_group), len(right_group)}
        return (
            left_kind == right_kind == "region"
            and left_topic == right_topic == REPRESENTATIVE
            and shapes == {1, 2}
            and (left_group[-1:] == ("all",) or right_group[-1:] == ("all",))
        )

    def parent_first(left, right):
        return (left, right) if len(page_info(left)[1]) == 2 else (right, left)

    parent_detail = discovered_pairs(baseline_graph, is_parent_detail, parent_first)

    def is_region_school(left, right):
        return {page_info(left)[0], page_info(right)[0]} == {"region", "school"}

    def region_first(left, right):
        return (left, right) if page_info(left)[0] == "region" else (right, left)

    region_school = discovered_pairs(baseline_graph, is_region_school, region_first)

    checks = {
        "region_representative_child": check_pairs(target_graph, region_child),
        "parent_region_detail_region": check_pairs(target_graph, parent_detail),
        "school_representative_child": check_pairs(target_graph, school_child),
        "region_school": check_pairs(target_graph, region_school),
    }
    baseline_checks = {
        "parent_region_detail_region": check_pairs(baseline_graph, parent_detail),
        "region_school": check_pairs(baseline_graph, region_school),
    }
    missing = [item for check in checks.values() for item in check["missing"]]
    report = {
        "target": str(args.target.resolve()),
        "baseline": str(args.baseline.resolve()),
        "page_count": len(urls),
        "checks": checks,
        "baseline_relation_checks": baseline_checks,
        "normal_relationships": sum(check["normal"] for check in checks.values()),
        "total_relationships": sum(check["total"] for check in checks.values()),
        "missing_relationship_directions": len(missing),
        "wrong_reverse_links": 0 if not missing else len(missing),
        "broken_internal_links": len(broken),
        "baseline_broken_internal_links": len(baseline_broken),
    }
    report["pass"] = (
        not missing
        and not broken
        and all(not check["missing"] for check in baseline_checks.values())
        and checks["region_school"]["total"] == 619
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "bidirectional-links.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (args.output / "bidirectional-missing.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source", "target", "direction"])
        writer.writeheader()
        writer.writerows(missing)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
