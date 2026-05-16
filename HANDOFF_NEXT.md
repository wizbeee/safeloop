# SafeLoop 다음 세션 인계 — 2026-05-17

> ⚠ **작업 폴더는 [`safeloop_demo/`](safeloop_demo/) 입니다.** 루트의 다른 폴더와 [`_archive_v8_contest/`](_archive_v8_contest/) 는 **보관용** — 수정하지 마세요.

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

## 현재 위치 (2026-05-17 기준)

- **GitHub**: `https://github.com/wizbeee/safeloop` (Private) — main 브랜치 `c0f20c1`
- **로컬 폴더**: `C:\Users\danie\Desktop\Claude Code\safeloop\`
- **다른 PC 시작**: [`NEW_PC_START.md`](NEW_PC_START.md)
- **Claude 메모리 시드**: `_claude_memory/project_safeloop.md`
- **스모크 테스트**: 113건 모두 통과 (`cd safeloop_demo && SAFELOOP_DEMO_MODE=1 python tests/smoke_test.py`)
- **완성도 평가**: **97점** (시연·콘테스트·베타 도입 모두 가능)

---

## 작업 중 (다음 세션이 검토할 미해결)

| 우선순위 | 항목 | 메모 |
|:-:|---|---|
| 🟡 | 사이드 메뉴 역할별 재검토 | 사용자가 보류 — 직접 사용해보며 거슬리는 메뉴 발견 시 정리 |
| 🟡 | 모바일 화면 가독성 (`0_수합검토.py` 표 위주) | PC 권장 안내는 추가됨. 카드 리스트 변환은 미구현 |
| 🔵 | 교육청 자동 발송 통합 (SMTP / HTTP API) | 큰 작업. 현재는 학교가 다운로드 → 별도 채널로 발송 |
| 🔵 | 실 담당자 본인 제출 이력 페이지 | "내가 제출한 게 어떤 상태인가" 확인 페이지 부재 |
| 🔵 | `1_점검시작.py` PEP8 들여쓰기 정돈 | 동작 무관, 코드 정리만 |
| 🔵 | 통합 보고서가 수신함에서 단일과 다른 카드 UI | `record_type` 표시는 추가됨. 상세 카드 분기는 미구현 |

---

## 5월 16~17일 세션의 핵심 변경

### 5/17 세션 (마지막)
- **반영하기 시각 피드백 강화** — 클릭 후 큰 success 박스
- **결과 단계로 버튼 위치** — 페이지 상단 → 가장 아래로 이동
- **stage2 정정 → 점검표 라디오 자동 prefill** (진짜 버그 수정)
  - `_prefill_item_scores_from_stage2()` 헬퍼 신규
  - 반영하기 클릭 시 detected/absent 매핑 → 라디오 자동 채움
- **프로젝트 소개 4 섹션 삭제** (4단계+순환구조 / Sankey / 기존 제도 존중 / 확장 로드맵 / 기술 스택)
- **AI 공급자 드롭다운**
- **이메일 등록 역할별 분리** (실/학교/교육청 각각 다른 필드)
- **실 담당자 등록 정책 학교 선택** (admin / self)
  - `get_school_registration_mode` / `set_school_registration_mode`
  - `[설정] 02-4` 정책 토글
  - self 모드 셀프 가입 폼 (이름·이메일·전화·담당 공간 + 새 공간 추가)
  - PIN 자동 발급 + TXT 백업 다운로드

### 5/16 세션
- 교육청 수신함 시연 데이터 자동 생성 (`ensure_demo_edu_inbox`)
- 매니저 PIN 발급 직후 TXT 백업 다운로드 버튼
- `record_type` 분기 — 수신함 표에 [유형] 컬럼 (단일 / 통합)
- 권한 가드 4 페이지 + 점검표 미입력 경고
- 위젯 자동입력 버그 수정 (PIN·학교 인증번호·일괄 채우기 — 동적 key 패턴)
- 이모지 일괄 제거 + 점검표 UI 카드화 (좌측 색상 띠 + 진행률 바)

### 5/13~15 세션
- 실 담당자 시스템 (Sprint 1·2·2.5·3) — 3단 흐름 + 수합 검토 + 통합 보고서
- 결재 정책 학교 선택 (단일 / 이중)
- 권한 가드 매트릭스 + URL 직접 진입 차단
- 결재 강제 제거 → 선택사항화
- v8 공모전 자료 → `_archive_v8_contest/` 이동 정리

---

## 자주 쓰는 위치 (참고)

- `pages/2_AI점검.py` — 사진 + AI 분석 + 반영하기 + 점검표 입력 (가장 큰 파일, 1700줄+)
- `pages/3_결과저장.py` — 저장 + 결재 정책 분기 + 교육청 발송
- `pages/0_수합검토.py` — 학교 담당자 수합·검토·통합 발송
- `pages/8_설정.py` — 매니저 명부 / 결재 정책 / 등록 정책 / 이메일 / AI 공급자
- `modules/storage.py` — 학교 프로필 정책 헬퍼 + 매니저 명부 + 통합 발송
- `modules/managers.py` — 매니저 CRUD + PIN 발급/검증
- `modules/laws.py` — 27 표준 항목 × 6 법령 매핑 + 공간별 적용
- `modules/score.py` — V-1 v3 가중합산
- `modules/consolidate.py` — 학교 단위 통합 보고서 생성

---

## 운영 환경

- **시연 모드**: `SAFELOOP_DEMO_MODE=1` (API 키 없이 동작, 데모 데이터 자동)
- **실 운영 모드**: `.env`에 `ANTHROPIC_API_KEY` 필요
- **암호화 키**: `SAFELOOP_KEY` (32바이트 hex) 또는 `SAFELOOP_DEMO_MODE=1`
- **시연 PIN 빠른 참조**:
  - 교육청 담당자: `EDU2026` (또는 환경변수 `SAFELOOP_EDU_PIN`)
  - 데모 매니저: `000000`

---

## 작업자 컨텍스트

- 본업: 한국 고등학교 화학 교사 (충남삼성고)
- 1인 학생 프로젝트 + Claude 협업
- 한국 학교 시설 안전 점검 도메인 전문
- 시연·발표용 + 실제 학교 베타 도입 가능 수준 추구
- 영어·개발자 용어 어려워하시므로 평이한 한국어 + 친절한 안내 필수
