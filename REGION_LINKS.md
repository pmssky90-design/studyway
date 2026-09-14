# 전체 지역 내부 링크

현재 운영 `output/`에는 원본 생성 이후 적용한 본문·디자인·SEO 개선이 포함되어 있습니다.
링크 작업만 할 때 `build.py`를 다시 실행하지 않습니다. 최종 HTML 생성·후처리 후 아래 공통 단계를 실행합니다.

```powershell
python scripts/strengthen_all_region_links.py
python scripts/strengthen_all_region_links.py --apply
python scripts/strengthen_all_region_links.py
```

첫 실행은 사전 검사, 두 번째는 적용, 마지막은 재실행 시 `changed_pages: 0` 확인입니다.
대표 과외·과목·학년군·개별 학년 및 기존 breadcrumb의 상위 지역 동일 유형을 양방향 연결합니다.
기존 링크·본문·head는 보존하며, 없는 URL·본문 변형은 적용 전에 오류로 처리합니다.
학교 페이지는 변경하지 않습니다. 개별 지역 보강 스크립트 대신 이 공통 단계를 사용합니다.

내부 링크 개선은 검색봇의 발견 경로를 개선하지만 색인 등록이나 수집 재개를 보장하지 않습니다.
