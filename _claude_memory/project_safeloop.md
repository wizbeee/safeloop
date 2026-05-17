---
name: SafeLoop 프로젝트 현황
description: SafeLoop 학교 안전 점검 앱 — 99.5점 완성도. 시연·콘테스트·1~5개 학교 베타·분산 운영(SMTP)까지 가능. 한국어 평이한 안내 필수.
type: project
originSessionId: 4187d9f7-f1f7-4b01-8060-42f967de9990
---

**위치**: `C:/Users/danie/Desktop/Claude Code/safeloop/` (정리 후 2026-05-12)
**GitHub**: `https://github.com/wizbeee/safeloop` (Private) — main `2129561`
**브랜치**: `main` (모든 작업 push 완료)
**★ 작업 폴더**: `safeloop_app/` (운영 앱). 루트 `_archive_v8_contest/` 는 출품 시점 보관용 — 수정 금지.
**기술 스택**: Streamlit + Plotly + Anthropic/Gemini/GPT API + Python 3.10+ + extra-streamlit-components + sqlite3 + smtplib

**완성도**: 99.5점 (2026-05-17 확장 세션 기준) / 시연·콘테스트·1~5개 학교 베타 즉시 가능 / SMTP 설정만 추가하면 분산 운영도 가능 / 막힘 0건

## MVP 범위
- 일반교실 + 9개 특별교실 (화학·물리·생명·지구·기술·가정·음악·미술·디자인)
- 10개 공간 모두 시연 가능 (LAW_BASIS 기반 합성 응답)
- 실 사진 5공간 35장 (충남삼성고 본교) — sample_dispatch 키워드 매핑 분배

## 핵심 흐름 — 3단 검토
1. **실 담당자** — 본인 공간 AI 점검 → "학교 담당자에게 제출"
   - 본인 제출 이력 페이지(`13_내제출이력.py`) — 반려 사유 + 재점검 진입점
2. **학교 담당자** — 제출 수합·검토 → 통합 보고서 → **교육청 수신함 자동 전송 + (옵션) Gmail SMTP 자동 메일**
3. **교육청 담당자** — 수신함(record_type 분기) + 전국 대시보드 + 정책 시뮬레이터

## 시연 모드 — 일관 원칙 (5/17 확장 세션 강화)
**`demo_mode=True` 일 때만 시연 UI 노출 / `demo_mode=False` 면 모든 시연 흔적 숨김**

- 시연 진입점은 [설정]에 일원화 — `demo_mode=False` 일 때 "시연 모드 시작" 버튼
- 시연 종료 시 홈에서 시연 카드 완전 숨김 (`st.stop()`)
- 매니저 명부 + selectbox 에서 `_demo:True` 매니저 필터
- 시연 매니저 PIN 재발급·비활성화·공간 변경 모두 disabled
- 시연 데이터 cleanup 체크박스 (`cleanup_demo_artifacts()`)
- **시연 학교명·교육청명 자동 마스킹** (○○ 고등학교 / ○○ 교육청)

## 학교별 정책
- **결재 정책**: 단일(에듀파인만, 기본) / 이중(SafeLoop 도 기록)
- **실 담당자 등록 정책**:
  - admin: 학교 담당자가 매니저 + 공간 등록 + PIN 발급
  - self: 학교 인증번호로 셀프 가입 + PIN 자동 발급

## 인증·보안
- 교육청 PIN: `EDU2026` (운영: `SAFELOOP_EDU_PIN`)
- `auth.py` 동적 PIN — `_pin_codes()` / `_ROLE_KEYS`. 운영 PIN 환경변수 변경 즉시 반영
- 학교 6자리 인증번호 (자동발급)
- 매니저 PIN 6자리 (admin: 발급 / self: 자동)
- 자동 로그인 30일 쿠키 — **`ensure_state()` 안에서 1회 시도** (모든 페이지 URL 직진입에서도 복원)
- AES-256-GCM 자동 암호화 + 운영자 도구 분리 + 식별정보 마스킹 기본 ON

## 시간대 (5/17 확장 세션 신규)
- KST(UTC+9) 일관 — Streamlit Cloud(UTC) 배포 시 9시간 어긋남 해소
- 모든 모듈 `datetime.now()` → `_now()` 또는 `now_kst()` 사용
- `session.now_kst()` / `storage._now()` / `managers.datetime.now(KST)` / `consolidate.datetime.now(KST)`

## SMTP 메일 자동 발송 (5/17 확장 세션 신규 — `modules/mailer.py`)
- `.env` 에 `SMTP_USER` (Gmail) + `SMTP_PASS` (앱 비밀번호 16자리) 등록 시 자동 활성
- 통합 발송 시 "교육청에 메일도 함께 발송" 체크박스 노출 (PDF + Excel + JSON 첨부)
- 시연 모드 + 미설정 + 이메일 미등록 시 자동 비활성 + 안내
- [설정] → "SMTP 연결 시험" 버튼 (실 발송 X, 로그인만)

## SQLite 인덱스 (5/17 확장 세션 신규 — `modules/db.py`)
- `school_storage/_index/safeloop_index.db` — master.json 단일 진실 유지 + 빠른 검색 캐시
- WAL 모드 + threading.Lock 동시 쓰기 안전
- 점검 저장 시 자동 `upsert_inspection_index()` (실패해도 master.json 정상)
- [설정] → "인덱스 재구축" (외부 도구로 master.json 추가했거나 손상 시)
- `query_inspections` / `count_inspections` 다학교 다세션 빠른 조회용

## 권한 가드 (모든 페이지 완비)
| 페이지 | 교육청 | 실 담당자 |
|---|:-:|:-:|
| 0_수합검토 / 4_본교현황 / 6_데이터순환 / 10_점검이력 / 12_데이터불러오기 | 차단 | 차단 |
| 1_점검시작 | 차단 | 허용 |
| 2_AI점검 / 3_결과저장 | 자동 분기 | 분기 (제출 표시) |
| 5_전국대시보드 / 9_프로젝트소개 | 허용 | 허용 |
| 7_교육청수신함 / 11_정책시뮬레이터 | (PIN + role==교육청) | 차단 |
| 8_설정 | 섹션별 가드 | 섹션별 가드 |
| 13_내제출이력 | 차단 | 허용 |

## AI 파이프라인
- **Stage 2** Claude Opus Vision — 사진 7~8컷 → detected/absent/ambiguous 3분류
- **Stage 3** Claude Haiku — 27 표준항목 × 6 법령 점검표 자동 생성
- 사용자 [반영하기] 클릭 시 stage2 정정 → 점검표 라디오 prefill (status 별 매핑: 양호 1.0 / 불량 0.5 / 부재 0.0)
- truncated_recovered 시 경고 배너

## 모바일 (5/17 확장 세션 신규)
- PWA `manifest.json` orientation "any" — 사용자가 폰을 가로로 돌리면 가로 적응
- 4_본교현황 점검 이력 표: PC=dataframe / 모바일=카드 자동 분기 (`.sl-table-pc` / `.sl-table-mobile` CSS)
- 0_수합검토 제출 메타정보 2×2 그리드 (기존)
- `mobile_pc_hint()` 헬퍼 — 5개 wide 페이지

## 학교명·교육청명 마스킹 (5/17 확장 세션 신규)
- `modules/ui.py` 헬퍼 4개:
  - `mask_school_name("충남삼성고등학교")` → "○○ 고등학교"
  - `mask_sido("충청남도교육청")` → "○○ 교육청"
  - `mask_region("천안시")` → "○○"
  - `demo_masked_school(school_dict)` 사본
- 시연 모드일 때만 적용. 실 모드는 원본
- 적용: 사이드바·hero(2/3/4)·1_점검시작 검색결과·자동로그인 토스트·5_전국대시보드·7_교육청수신함·0_수합검토·6_데이터순환·13_내제출이력
- PDF/Excel 산출물은 미적용 (실 학교명 유지가 결재·인쇄 목적에 맞음)

## 통합 발송 — 앱 내 직접 전송 + (옵션) SMTP
- `mark_consolidated(record=...)` → `submit_to_edu_inbox_direct(record)` 자동 호출
- `submit_to_edu_inbox_direct` 가 `school_identified or school` fallback (단일·통합 모두 처리)
- 파일명 `_consolidated.json` 접미사로 단일/통합 구분
- 반환 `dict {count, submit, errors}`
- 학교가 "교육청에 통합 발송" 클릭 → 즉시 수신함 도착 + (선택) Gmail 메일 자동

## 위젯 핵심 패턴
**자동입력 안전 패턴** (Streamlit value= 무시 회피):
- 위젯 key 를 카운터로 동적 변경 — 새 위젯 인스턴스 생성 시 value 적용
- 예: `key=f"_pin_v{_pin_counter}"` + 클릭 시 카운터 +1
- 적용 위치: PIN / 학교 인증번호 / 점검표 prefill (`_radio_counter`) — Stage 2 재분석 시도 자동 +1

## 금지 사항
- KEIIS / 에듀파인 결재 / send_to_edu_app 복원
- "학교 클라우드" / "기계용 JSON" 표현
- 실 사진을 시연용으로 (5공간 sample_images 는 의도된 사용)
- PDF 에 결재란 추가 (이중 결재 모드 외)
- 메일앱 (mailto) 단독 사용 — SMTP 또는 수신함 자동 전송 사용
- 박스플롯·모델 신뢰도 학술 용어 메인 노출
- Stage 1/2/3 영문 jargon 화면 노출
- "전체 양호로 채우기" 만으로 만점
- 호스팅 클라우드 자동 도입
- 공모전 메타 표현 ("심사위원", "활용대회", "대회 마감" 등) — 일반화 완료
- 이모지 (5/16 일괄 제거) — `★` 같은 유니코드 텍스트 기호는 허용 (별표 시각 표시)

## 스모크 테스트
115건 통과 — `cd safeloop_app && SAFELOOP_DEMO_MODE=1 python tests/smoke_test.py`

## 미해결 (다음 세션 검토)
- 🔵 1_점검시작.py PEP8 들여쓰기
- 🔵 통합 보고서 수신함 상세 카드 분기 (spaces 펼침 + build_consolidated_pdf 사용)
- 🟡 6_데이터순환 정수 인덱스 라디오 → session_id 기반
- 🟡 0_수합검토 expander 전각 공백 라벨 → 구조 변경
- 🟡 PDF/Excel 산출물 시연 마스킹 검토 (현재 실 학교명 유지)
- 🟡 다른 wide 페이지 모바일 카드 분기 확대 (10_점검이력 등)
- 🟡 naive datetime 잔존 정밀 점검 (외부 클라우드 배포 시)

## Git 흐름
- `git pull` / `git push` (`wizbeee/safeloop` Private)
- 모든 커밋: Conventional Commits 한국어 (배경/변경/검증 4단 구조) + Co-Authored-By Claude

## 작업자 컨텍스트
- 본업: 한국 고등학교 화학 교사 (충남삼성고)
- 1인 학생 프로젝트 + Claude 협업
- **한국어 평이한 안내 필수** — "SMTP"·"다학교"·"백엔드" 용어는 비유로 풀어 설명
- 답변 길이는 짧고 명확하게
- 사용자가 직접 시연·테스트하며 발견하는 버그를 그 자리에서 수정하는 패턴
- **검토 → 종합 보고 → 우선순위 동의 → 묶음 수정 → 스모크 검증** 패턴 선호

## 자주 쓰는 위치
- `pages/2_AI점검.py` — 사진·AI·반영하기·점검표 prefill (1900줄+)
- `pages/3_결과저장.py` — 저장·결재·발송
- `pages/0_수합검토.py` — 수합·검토·통합 자동 발송 + SMTP 옵션
- `pages/13_내제출이력.py` — 실 담당자 본인 이력·반려·재점검
- `pages/8_설정.py` — 매니저/정책/시연 cleanup/SMTP 시험/인덱스 재구축
- `modules/storage.py` — 학교 프로필 + 매니저 + 통합 발송 + cleanup_demo_artifacts + KST + 자동 인덱스 갱신
- `modules/auth.py` — `_pin_codes()` 동적 / `_ROLE_KEYS`
- `modules/consolidate.py` — 통합 보고서 + `mark_consolidated(record=)` 자동 발송
- `modules/demo_image.py` — sample_images 5공간 분배 + PIL 폴백
- `modules/demo_responses.py` — 합성 응답(absent/ambig 결정적 보장)
- **`modules/mailer.py` (5/17 신규)** — Gmail SMTP 자동 발송
- **`modules/db.py` (5/17 신규)** — SQLite 인덱스 (master.json 단일 진실)
- `modules/session.py` — now_kst() / ensure_state 자동 로그인 통합
- `modules/ui.py` — apply_theme + render_sidebar + **mask_* 헬퍼 4개** + mobile_pc_hint

## 새 세션 시작 첫 응답
사용자가 작업 지시를 주기 전에:
1. `HANDOFF_NEXT.md` 와 본 메모리 파일 읽었다고 확인
2. 현재 완성도 (99.5점) + 미해결 항목 요약 (1~2줄)
3. "구체적인 작업 지시를 기다리겠습니다" 한 줄

장황하게 환영 메시지 X. 평이하고 짧게.
