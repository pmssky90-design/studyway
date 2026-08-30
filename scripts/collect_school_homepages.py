from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path


AUTHORITY_BY_REGION = {"서울": "B10", "경기": "J10"}
API = "https://open.neis.go.kr/hub/schoolInfo"


def normalize(value: object) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(value or "")).lower()


def normalize_homepage(value: object) -> tuple[str, bool, str]:
    url = str(value or "").strip()
    if not url:
        return "", False, "missing"
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    try:
        parsed = urllib.parse.urlsplit(url)
        if "." not in parsed.netloc:
            raise ValueError("invalid host")
        normalized = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
        return normalized.rstrip("/"), True, ""
    except ValueError:
        return url, False, "invalid_url"


def school_inventory(url_plan: Path) -> list[dict[str, str]]:
    schools: dict[str, dict[str, str]] = {}
    with url_plan.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("page_type") != "school_content" or row.get("slug") != "과외":
                continue
            match = re.search(r"/school/([^/]+)/과외/", row["url"])
            if not match:
                continue
            key = match.group(1)
            schools[key] = {
                "school_key": key,
                "school_name": row["school_name"].strip(),
                "region": row["region"].strip(),
                "district": row["district"].strip(),
                "dong_eup_myeon": row["dong_eup_myeon"].strip(),
                "root_url": row["url"].strip(),
            }
    return sorted(schools.values(), key=lambda item: item["school_key"])


def query_school(record: dict[str, str]) -> dict[str, object]:
    authority = AUTHORITY_BY_REGION.get(record["region"], "")
    params = urllib.parse.urlencode(
        {
            "Type": "json",
            "pIndex": "1",
            "pSize": "100",
            "SCHUL_NM": record["school_name"],
            "ATPT_OFCDC_SC_CODE": authority,
        }
    )
    source_url = f"{API}?{params}"
    rows: list[dict[str, object]] = []
    error = ""
    for attempt in range(3):
        try:
            request = urllib.request.Request(source_url, headers={"User-Agent": "StudyWay school homepage verifier/1.0"})
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = json.load(response)
            for part in payload.get("schoolInfo", []):
                if isinstance(part, dict) and isinstance(part.get("row"), list):
                    rows = part["row"]
                    break
            break
        except Exception as exc:  # network diagnostics are preserved in the manifest
            error = str(exc)
            time.sleep(0.3 * (attempt + 1))

    exact = [
        item
        for item in rows
        if str(item.get("SCHUL_NM", "")).strip() == record["school_name"]
        and str(item.get("SCHUL_KND_SC_NM", "")).strip() == "고등학교"
    ]
    candidates = exact or [item for item in rows if str(item.get("SCHUL_KND_SC_NM", "")).strip() == "고등학교"]
    district = normalize(record["district"])
    dong = normalize(record["dong_eup_myeon"])

    def score(item: dict[str, object]) -> int:
        address = normalize(f'{item.get("ORG_RDNMA", "")} {item.get("ORG_RDNDA", "")}')
        value = 100 if str(item.get("SCHUL_NM", "")).strip() == record["school_name"] else 0
        if district and district in address:
            value += 30
        if dong and dong in address:
            value += 20
        return value

    ranked = sorted(((score(item), item) for item in candidates), key=lambda pair: pair[0], reverse=True)
    best = ranked[0][1] if ranked else None
    ambiguous = len(ranked) > 1 and ranked[0][0] == ranked[1][0]
    result: dict[str, object] = {**record, "authority_code": authority, "source_url": source_url}
    if not best:
        result.update(
            {
                "match_status": "API_ERROR" if error else "NOT_FOUND",
                "match_error": error,
                "review_required": True,
                "insert_link": False,
            }
        )
        return result

    homepage, homepage_valid, homepage_issue = normalize_homepage(best.get("HMPG_ADRES", ""))
    name_exact = str(best.get("SCHUL_NM", "")).strip() == record["school_name"]
    review_required = not name_exact or ambiguous or not homepage_valid
    result.update(
        {
            "education_office": best.get("ATPT_OFCDC_SC_NM", ""),
            "neis_school_code": best.get("SD_SCHUL_CODE", ""),
            "api_school_name": best.get("SCHUL_NM", ""),
            "api_address": f'{best.get("ORG_RDNMA", "")} {best.get("ORG_RDNDA", "")}'.strip(),
            "homepage_raw": str(best.get("HMPG_ADRES", "")).strip(),
            "homepage": homepage,
            "homepage_valid": homepage_valid,
            "homepage_issue": homepage_issue,
            "candidate_count": len(ranked),
            "match_status": "REVIEW" if review_required else "MATCHED",
            "review_required": review_required,
            "insert_link": not review_required,
        }
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect official school homepages from the NEIS schoolInfo API.")
    parser.add_argument("--url-plan", type=Path, default=Path(__file__).resolve().parents[1] / "reports" / "url-plan.csv")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "studyway_school_homepages.json")
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    inventory = school_inventory(args.url_plan.resolve())
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        records = list(executor.map(query_school, inventory))
    statuses = Counter(str(item["match_status"]) for item in records)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_url_plan": str(args.url_plan.resolve()),
        "source_system": "교육부 나이스 교육정보 개방 포털 학교기본정보 Open API",
        "total": len(records),
        "status_counts": dict(statuses),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "total": len(records), "status_counts": dict(statuses)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
