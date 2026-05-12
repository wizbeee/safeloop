# 📦 v8 교육공공데이터 AI활용대회 — 보관 자료

> **⚠ 이 폴더는 작업 대상이 아닙니다. 운영 코드는 [`../safeloop_demo/`](../safeloop_demo/) 입니다.**

## 이 폴더는?

제8회 교육 공공데이터 AI 활용대회(2026년) **출품 시점의 자료를 그대로 보존**하기 위한 보관소입니다. 운영 코드가 발전하면서 더 이상 직접 참조하지 않게 된 분석 자료·옛 명세서·참고 문서를 한 곳으로 모았습니다.

**모든 파일은 `git mv`로 이동되어 git 히스토리가 보존됩니다.** 삭제된 것은 없습니다.

## 폴더 구성

| 폴더/파일 | 보관 사유 |
|---|---|
| `code/poc_run.py` | Stage 2 PoC 원본 (L1·L2·L3 검증 코드). 운영판은 `safeloop_demo/modules/ai_vision.py`에 통합·발전됨 |
| `docs/SafeLoop_시연앱_프로그램명세서.md` | 출품 시점 명세서 (역사 자료) |
| `docs/SafeLoop_핵심서사_지침_2026-04-23.md` | 출품 시점 핵심 서사 지침 |
| `reference_pdfs/` | 출품 시점 참고 자료 (경기·충남 교육청 안전점검표, 학교안전점검의 날 체크리스트 등) |
| `validation/V1_점검표비교_v3.xlsx` | 27 표준항목 × 6 핵심법령 매핑 근거. `safeloop_demo/modules/laws.py`의 `LAW_BASIS`가 이를 기반으로 만들어짐 |
| `validation/V2_예산시나리오.xlsx` | 예산 시뮬레이션 시나리오 (`pages/11_정책시뮬레이터.py` 설계 근거) |
| `data/` | 출품 시점 분석용 CSV 8종 사본. 운영용 사본은 `safeloop_demo/data/`에 별도로 동일하게 유지됨 |
| `sample_images/` | 출품 시점 샘플 사진 13장 (화학실 6·물리실 7). 운영용 최신본은 `safeloop_demo/sample_images/`에 5공간 35장으로 확장됨 |
| `env_config/.gitignore_template` | 출품 시점 환경 설정 템플릿 |
| `CONTEST_CHECKLIST.md` | 공모전 출품 체크리스트 |
| `HANDOFF_FIX50.md` | 옛 핸드오프 문서 (현재 최신은 `../HANDOFF_NEXT.md`) |

## 운영 코드는 archive를 참조하지 않습니다

2026-05-12 기준 검증 — `safeloop_demo/` 안의 모든 코드는 자기 폴더(`Path(__file__).parent.parent`)만 참조하며, 이 archive 폴더를 import하거나 read하지 않습니다.

유일한 흔적은 `safeloop_demo/modules/laws.py` 의 주석 한 줄(법령 매핑 근거 안내)이고, 이 주석은 archive 이동에 맞춰 경로가 업데이트되어 있습니다.

## 복구 방법

archive에서 어떤 파일을 운영 폴더로 다시 가져와야 한다면:

```bash
git mv _archive_v8_contest/<경로> <원하는 위치>
git commit -m "restore: <파일>을 archive에서 복원"
```

git 히스토리가 보존되어 있어 `git log --follow <파일>`로 모든 변경 내역을 추적할 수 있습니다.
