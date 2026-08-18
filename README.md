# StudyWay static site generator

최종 Excel을 원본 그대로 읽어 서울·경기 지역 및 고등학교별 정적 HTML을 생성합니다.

```powershell
python build.py
python scripts/validate_site.py
```

- 배포 루트: `output/`
- URL 계획: `reports/url-plan.csv`, `reports/url-plan.json`
- 빌드 요약: `reports/build-report.json`
- 검증 결과: `reports/validation-report.json`

외부 패키지는 필요하지 않습니다. Python 표준 라이브러리만 사용합니다.
