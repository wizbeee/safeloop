# SafeLoop 다음 세션 인계 — 2026-05-17 (확장 세션)

> ⚠ **작업 폴더는 [`safeloop_app/`](safeloop_app/) 입니다.** 루트의 다른 폴더와 [`_archive_v8_contest/`](_archive_v8_contest/) 는 **보관용** — 수정하지 마세요.

## 새 세션 진입 방법

### 같은 PC
새 Claude 창에 다음을 입력:
```
SafeLoop 작업을 이어받습니다.
safeloop/HANDOFF_NEXT.md 와 safeloop/_claude_memory/project_safeloop.md 를
먼저 읽고 현재 상태를 파악한 뒤 사용자 지시를 기다려주세요.
```

### 다른 PC
1. [`NEW_PC_START.md`](NEW_PC_START.md) 5단계 따라 환경 구축 (~15분)
2. 위와 동일하게 새 Claude 창에 입력

---

## 현재 위치 (2026-05-17 확장 세션 기준)

- **GitHub**: `https://github.com/wizbeee/safeloop` (Private) — main 브랜치 `2129561`
- **로컬 폴더**: `C:\Users\danie\Desktop\Claude Code\safeloop\`
- **다른 PC 시작**: [`NEW_PC_START.md`](NEW_PC_START.md)
- **Claude 메모리 시드**: `_claude_memory/project_safeloop.md`
- **스모크 테스트**: 115건 모두 통과
- **완성도 평가**: **99.5점** (시연·콘테스트·1~5개 학교 베타 도입 즉시. 분산 운영도 SMTP 설정만 추가하면 가능)

---

## 작업 중 (다음 세션이 검토할 미해결)

| 우선 | 항목 | 메모 |
|:-:|---|---|
| 🔵 | 1_점검시작.py PEP8 들여쓰기 | 동작 무관 코드 정리 |
| 🔵 | 통합 보고서 수신함 상세 카드 분기 | 7_교육청수신함 상세 조회 시 spaces 펼침 카드 미구현. 통합본 PDF 변환 시 build_consolidated_pdf 사용으로 분기 필요 |
| 🟡 | 6_데이터순환 정수 인덱스 라디오 | session_id 기반 옵션으로 재설계 |
| 🟡 | 0_수합검토 expander 전각 공백 라벨 | 헤더 카드를 expander 본문에서 라벨로 이동 시 구조 변경 |
| 🟡 | PDF/Excel 산출물 시연 마스킹 검토 | 현재 산출물은 실 학교명 유지. 시연 시 첨부물에도 ○○ 적용할지 |
| 🟡 | 다른 wide 페이지 모바일 카드 분기 | 4_본교현황 점검 이력 표는 이미 적용. 10_점검이력·7_교육청수신함 등도 PWA 가로 회전으로 보완 가능 |
| 🟡 | naive datetime 잔존 정밀 점검 | KST 일괄 치환 완료. 호환성 위해 옛 저장본은 KST 가정. 외부 클라우드 배포 시 확인 권장 |

---

## 5월 17일 확장 세션의 핵심 변경 (커밋 `cf4f947` → `2129561`)

이번 세션은 **4가지 한계 일괄 해결 + 시연 UI 일관성 + 학교명 마스킹** 일괄 처리.
20+ 파일 / +1500 / -270 / 신규 모듈 2개 / 신규 헬퍼 5개.

### [한계 4 — KST + 자동 로그인 일원화] 커밋 `5fa9de6`
- `modules/session.py`: `now_kst()` / `now_kst_iso()` 헬퍼. `ensure_state()` 안에서 학교·매니저 자동 로그인 1회 시도(`_auto_login_attempted` 플래그) — 어느 페이지 URL 직진입해도 컨텍스트 자동 복원
- 4개 모듈(storage·managers·consolidate·session) `datetime.now()` → KST 일괄 치환
- 외부 클라우드 (UTC) 배포 시 9시간 어긋남 해결

### [한계 2 — PWA + 모바일 카드] 커밋 `5fa9de6`
- `static/manifest.json`: orientation "portrait-primary" → "any" (가로 회전 허용)
- `pages/4_본교현황.py`: 점검 이력 표가 PC=dataframe / 모바일=카드 자동 분기 (CSS 미디어쿼리 768px)
- `modules/ui.py`: `.sl-table-pc` / `.sl-table-mobile` 분기 CSS + `.sl-hist-card` 스타일

### [한계 1 — Gmail SMTP] 커밋 `5fa9de6` (신규 모듈)
- **`modules/mailer.py`** 신규: `smtp_configured()` / `test_smtp_connection()` / `send_inspection_email()`. Gmail 앱 비밀번호 발급 안내 docstring
- `pages/0_수합검토.py`: 통합 발송 시 "교육청 이메일에도 함께 발송" 체크박스 자동 노출 (SMTP 설정 + edu_office_email 등록 + 시연 아닐 때)
- `pages/8_설정.py`: SMTP 상태 표시 + "SMTP 연결 시험" 버튼
- `.env` 에 `SMTP_USER` + `SMTP_PASS` 등록 시 자동 활성화

### [한계 3 — SQLite 인덱스] 커밋 `5fa9de6` (신규 모듈)
- **`modules/db.py`** 신규: `school_storage/_index/safeloop_index.db` — master.json 단일 진실 유지 + 빠른 검색 캐시. WAL 모드 + threading.Lock 동시 쓰기 안전
- 점검 저장 시 자동 `upsert_inspection_index()`. 실패해도 master.json 은 정상
- `pages/8_설정.py`: 인덱스 통계 + "인덱스 재구축" 버튼 (외부 도구로 master.json 추가했거나 손상 시)
- `query_inspections` / `count_inspections` 다학교 다세션 빠른 조회

### [시연 UI 일관성] 커밋 `c4ea4be` + `80702bc`
- 사이드바 DEMO 뱃지의 `<a href='/설정'>` 새 창 띄움 버그 → 단순 안내 텍스트
- 시연 종료 후 홈에 시연 카드 잔존 버그 → demo_mode=False 면 시연 관련 UI 전부 숨김 + `st.stop()`
- 8_설정에 "시연 모드 시작 (체험·발표용)" 버튼 추가 — 시연 진입점 일원화
- 8_설정 매니저 명부 + 1_점검시작 selectbox 에서 `_demo:True` 매니저 시연 OFF 시 필터

### [학교명·교육청명 자동 마스킹] 커밋 `2129561`
- **`modules/ui.py`** 마스킹 헬퍼 4개 신규:
  - `mask_school_name("충남삼성고등학교")` → "○○ 고등학교"
  - `mask_sido("충청남도교육청")` → "○○ 교육청"
  - `mask_region("천안시")` → "○○"
  - `demo_masked_school(school_dict)` 사본 반환
- 실 모드(`demo_mode=False`)에선 원본 그대로
- 적용: 사이드바·hero(2/3/4)·1_점검시작 검색결과·자동로그인 토스트·5_전국대시보드·7_교육청수신함·0_수합검토·6_데이터순환·13_내제출이력

---

## 자주 쓰는 위치 (참고)

- `pages/2_AI점검.py` — 사진 + AI + 반영하기 + 점검표 (1900줄+, 가장 큼)
- `pages/3_결과저장.py` — 저장 + 결재 정책 분기 + 교육청 발송 (SMTP 옵션)
- `pages/0_수합검토.py` — 학교 담당자 수합·검토·통합 발송 (수신함 자동 + 메일 자동 옵션)
- `pages/13_내제출이력.py` — 실 담당자 본인 이력·반려·재점검
- `pages/8_설정.py` — 매니저 명부 / 결재·등록 정책 / 시연 cleanup / **SQLite 인덱스 재구축** / **SMTP 연결 시험**
- `modules/storage.py` — 학교 프로필 + 매니저 + 통합 발송 + cleanup_demo_artifacts + KST
- `modules/managers.py` — 매니저 CRUD + PIN + KST
- `modules/laws.py` — 27 표준 항목 × 6 법령 매핑
- `modules/score.py` — V-1 v3 가중합산
- `modules/consolidate.py` — 학교 통합 보고서 + mark_consolidated(record=)
- `modules/auth.py` — `_pin_codes()` 동적 / `_ROLE_KEYS` / `is_authenticated_session`
- `modules/demo_image.py` — sample_images 5공간 분배 + PIL 폴백
- `modules/demo_responses.py` — 합성 응답 3분류
- **`modules/mailer.py` (신규)** — Gmail SMTP 자동 발송
- **`modules/db.py` (신규)** — SQLite 인덱스 (master.json 단일 진실 유지)
- `modules/session.py` — `now_kst()` / `ensure_state` 자동 로그인 통합
- `modules/ui.py` — apply_theme + render_sidebar + mobile_pc_hint + **mask_* 헬퍼 4개**

---

## 운영 환경

- **시연 모드**: 홈 [시연 시작] 또는 [설정] → "시연 모드 시작" 버튼. `SAFELOOP_DEMO_MODE=1` 환경변수도 가능
- **실 운영 모드 (기본)**: `.env` 에 `ANTHROPIC_API_KEY` 필수
- **암호화 키**: `SAFELOOP_KEY` (32바이트 hex) 또는 시연 모드
- **SMTP (선택)**: `.env` 에 `SMTP_USER` (Gmail 주소) + `SMTP_PASS` (Gmail 앱 비밀번호 16자리). 미설정 시 메일 옵션만 비활성
- **시연 PIN 빠른 참조**:
  - 교육청 담당자: `EDU2026` (또는 환경변수 `SAFELOOP_EDU_PIN`)
  - 데모 매니저: `000000` (시연 매니저 보호 — PIN 재발급/비활성/공간 변경 모두 disabled)

---

## 4가지 등급 진입 가능 여부

| 용도 | 가능 | 필요 작업 |
|---|:-:|---|
| 공모전 출품 | ✅ | 즉시 |
| 발표·시연 | ✅ | 즉시 (학교명 자동 ○○ 마스킹) |
| 1~5개 학교 베타 | ✅ | API 키 + (선택) SMTP 설정 |
| 다학교 분산 운영 | ✅ | API 키 + SMTP + 외부 서버 (인덱스·KST 자동 동작) |
| 도교육청 단위 시범 | 🔵 | DB 백엔드 검토 + GPKI/SSO 협의 |

---

## 작업자 컨텍스트

- 본업: 한국 고등학교 화학 교사 (충남삼성고)
- 1인 학생 프로젝트 + Claude 협업
- 한국 학교 시설 안전 점검 도메인 전문
- **한국어 평이한 안내 필수** — "SMTP"·"다학교"·"백엔드" 같은 용어는 비유로 풀어 설명
- **검토 → 종합 보고 → 우선순위 동의 → 묶음 수정 → 스모크 검증** 패턴 선호
- 시연·발표용 + 실제 학교 베타 도입 가능 수준 추구
