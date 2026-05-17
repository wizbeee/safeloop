# 공공 환원 데이터 스키마 정의

> 점검 프로그램(`wizbeee/safeloop`)과 대시보드(`wizbeee/safeloop-dashboard`)
> 가 환원 데이터를 주고받기 위해 공유하는 **단일 진실 규격(SSOT)**.
>
> 양쪽 저장소의 `docs/opendata_schema.md` 는 항상 동일해야 합니다.

---

## 1. 환원 파일 위치

| 항목 | 기본값 | override |
|---|---|---|
| 공유 폴더 (공공 환원 CSV 저장 경로) | `~/Desktop/공공데이터 공모전/03_분석_데이터/점검_환원/` | 환경변수 `SAFELOOP_SHARED_DIR` |
| 활성 환원 CSV | `{공유폴더}/opendata_{YYYYMMDD}_{HHMMSS}.csv` | — |
| 메타 사이드카 | 같은 위치 `opendata_{stamp}.csv.meta.json` | — |
| 롤백된 환원 | `{공유폴더}/_rolled_back/opendata_*.csv` | 대시보드는 무시 |

대시보드는 `{공유폴더}/opendata_*.csv` 글로브로 모든 활성 환원을 자동 합산합니다.
`_rolled_back/` 하위는 합산에서 제외됩니다.

---

## 2. 환원 CSV 컬럼 정의 (한 행 = 한 학교)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `school_anonymous_id` | str | 학교 코드 SHA-256 해시 (식별 불가) |
| `sido` | str | 시도교육청 (예: `충청남도교육청`) |
| `school_level` | str | 학교급 (초·중·고·특수 등) |
| `establishment` | str | 설립구분 (공립·사립·국립) |
| `space_type` | str | 점검 공간 유형 (과학실·체육관·조리실·교실·기타) |
| `safety_score` | float | 안전 점수 0~100 |
| `grade` | str | 안전 등급 A~E |
| `detected_count` | int | AI 탐지된 안전 설비 수 |
| `absent_count` | int | AI 부재 판정된 설비 수 |
| `record_type` | str | `safeloop_edu_submission` (단일) / `safeloop_consolidated_submission` (학교 통합) |
| `released_at` | ISO 8601 | 환원 시각 (KST) |

인코딩: UTF-8 with BOM (Excel 호환).

---

## 3. 메타 사이드카 (.meta.json)

```json
{
  "file_name": "opendata_20260517_193045.csv",
  "exported_at": "2026-05-17T19:30:45+09:00",
  "count": 47,
  "sido_distribution": {
    "충청남도교육청": 30,
    "경기도교육청": 12,
    "강원특별자치도교육청": 5
  },
  "selected_file_names": ["receipt_001.json", "receipt_002.json", "..."]
}
```

대시보드의 환원 이력 표시 시 이 메타를 우선 사용. 메타가 없으면 CSV 행 수로 대체.

---

## 4. 익명화 정책

- 학교 코드 → `data_loader.anonymize_code()` 의 SHA-256 해시 (점검 프로그램 표준)
- 학교명·주소·교육지원청·점검자 식별 정보는 **CSV 에 포함 안 됨**
- 시도교육청·학교급·설립구분은 광역 단위라 식별 위험 낮음 → 노출 허용
- 학생수는 환원 CSV 에 포함하지 않음 (작은 학교 식별 위험 방지)

---

## 5. 환원 흐름

```
[점검 프로그램]
  pages/14_공공데이터환원.py
  ↓ 교육청 담당자가 수신함 항목 선택 + "공공 환원 실행"
  modules/opendata_export.py · export_opendata_csv()
  ↓ 익명화 + 집계 + CSV 저장
{공유폴더}/opendata_{stamp}.csv + .meta.json
  ↓ (같은 PC 또는 동기화된 공유 폴더)
[대시보드]
  app.py · load_returned_data(SHARED_DIR)
  ↓ 활성 CSV 모두 합산 (캐시 TTL 10초)
KPI 영역 아래 "📥 점검 환원 데이터 N건 반영됨" 안내 + 환원 데이터 expander
```

---

## 6. 롤백

- 점검 프로그램: `pages/14_공공데이터환원.py` 섹션 04 에서 "↩ 롤백" 클릭
- 동작: 활성 CSV 와 메타 파일을 `_rolled_back/` 하위로 이동
- 대시보드: `_rolled_back/` 무시 — 다음 새로고침 시 합산에서 제외
- 복원: `modules.opendata_export.restore_export()` 호출 (UI 미노출, 필요 시 추가)

---

## 7. 한계 (현재 MVP)

| 한계 | 영향 | 향후 |
|---|---|---|
| 두 앱이 같은 PC/공유 폴더에서만 자동 연결 | Streamlit Cloud 분리 배포 시 미작동 | 공유 백엔드(S3·Firebase) 도입 |
| `.safeloop` 암호화 파일은 평문 `.json` 짝이 있어야 환원 가능 | 시연용 한계 | 환원 시 자동 복호화 (`storage.decrypt_safeloop`) |
| 환원 시각은 점검 프로그램 시계 기준 | 클라이언트 시계 오차 가능 | 서버 시계 사용 (Phase 2) |
| 실 운영 환원 주체는 교육부·KEIIS | 시연용 단순화 | KEIIS API 연계 (Phase 3) |

---

## 8. 변경 이력

| 일자 | 변경 |
|---|---|
| 2026-05-17 | 초안 작성 — 환원 자동 연결 구조 정의 |
