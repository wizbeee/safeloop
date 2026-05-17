---
name: SafeLoop 프로젝트 현황
description: SafeLoop 학교 안전 점검 앱 — 98점 완성도. 시연·콘테스트·베타 도입 가능. 한국어 평이한 안내 필수.
type: project
originSessionId: 4187d9f7-f1f7-4b01-8060-42f967de9990
---

**위치**: `C:/Users/danie/Desktop/Claude Code/safeloop/` (정리 후 2026-05-12)
**GitHub**: `https://github.com/wizbeee/safeloop` (Private) — main `859432d`
**브랜치**: `main` (모든 작업 push 완료)
**★ 작업 폴더**: `safeloop_demo/` (운영 앱). 루트 `_archive_v8_contest/` 는 출품 시점 보관용 — 수정 금지.
**기술 스택**: Streamlit + Plotly + Anthropic/Gemini/GPT API + Python 3.10+ + extra-streamlit-components

**완성도**: 98점 (2026-05-17 후반 기준) / P0 9건 + P1 19건 일괄 수정 + 신규 페이지 1개 / 시연·콘테스트·베타 도입 모두 가능 / 막힘 0건

## MVP 범위
- 일반교실 + 9개 특별교실 (화학·물리·생명·지구·기술·가정·음악·미술·디자인)
- 10개 공간 모두 시연 가능 (LAW_BASIS 기반 합성 응답)
- 디자인실: LAB_SPACES 포함 (PPE 자동), 국소배기·장갑·MSDS 추가 (스프레이·본드·커터칼)
- **실 사진 5공간 35장 자동 사용** (충남삼성고 본교 촬영) — sample_dispatch 키워드 매핑으로 의미 분배

## 핵심 흐름 — 3단 검토 (5/12 신규)
1. **실 담당자** (화학실/물리실/디자인실 등 담당 교사) — 본인 공간 AI 점검 → "학교 담당자에게 제출"
   - **본인 제출 이력 페이지** (`13_내제출이력.py`) 신규 — 반려 사유 + 재점검 진입점
2. **학교 담당자** (안전관리 책임자) — 실 담당자 제출 수합·검토 (승인/반려/직접수정) → 통합 보고서 → **교육청 수신함 자동 전송** (앱 내 직접)
3. **교육청 담당자** — 수신함 (단일 점검 + 통합 보고서 record_type 분기) + 전국 대시보드 + 정책 시뮬레이터

## 학교별 정책 (학교 담당자가 [설정]에서 선택)
- **결재 정책 (02-3)**: 단일 결재 (에듀파인만, 기본) / 이중 결재 (SafeLoop도 결재 기록)
- **실 담당자 등록 정책 (02-4)**:
  - **admin (사전 배정, 기본)**: 학교 담당자가 매니저 + 공간 등록 + PIN 발급
  - **self (셀프 가입)**: 학교 인증번호만 알려주면 실 담당자가 본인 정보 + 담당 공간 직접 등록 + PIN 자동 발급

## 인증·보안 (5/17 후반 강화)
- 교육청 PIN: `EDU2026` (운영: `SAFELOOP_EDU_PIN` 환경변수)
- **`auth.py` 동적 PIN**: `_pin_codes()` 함수로 매 호출마다 환경변수 재조회. 정적 `PIN_CODES` 제거 — 운영 PIN 환경변수 사용 시 자동 로그인 영구 실패하던 P0 해결
- 학교 6자리 인증번호 (자동발급, `issue_auth_code`)
- 매니저 PIN 6자리 (admin: 학교 담당자 발급 / self: 자동 발급)
- 자동 로그인 30일 쿠키 (학교 + 매니저 별도)
- AES-256-GCM 자동 암호화 (.safeloop 파일) — `SAFELOOP_KEY` 또는 `SAFELOOP_DEMO_MODE=1`
- 운영자 도구 분리 (`SAFELOOP_ADMIN=1`)
- 식별정보 마스킹 기본 ON
- **인증 우회 차단**: 12_데이터불러오기 업로드만으로 school_auth_verified=True 강제하던 P0 제거
- **role hijack 차단**: 7_교육청수신함·11_정책시뮬레이터 가드 통과 후 role 강제 set 제거

## 권한 가드 (모든 페이지 완비)
| 페이지 | 교육청 | 실 담당자 |
|---|:-:|:-:|
| 0_수합검토 / 4_본교현황 / 6_데이터순환 / 10_점검이력 / 12_데이터불러오기 | 차단 | 차단 |
| 1_점검시작 | 차단 | 허용 |
| 2_AI점검 / 3_결과저장 | 자동 분기 | 분기 (제출 표시) |
| 5_전국대시보드 / 9_프로젝트소개 | 허용 | 허용 |
| 7_교육청수신함 | (PIN + role==교육청) | 차단 |
| 8_설정 | 섹션별 가드 | 섹션별 가드 |
| 11_정책시뮬레이터 | (PIN + role==교육청) | (PIN 안내) |
| 13_내제출이력 (신규) | 차단 | 허용 |

## AI 파이프라인 (Stage 2·3, Stage 1 제거됨)
- **Stage 2** Claude Opus Vision — 사진 7~8컷에서 안전 설비 인식 (탐지/부재/모호)
- **Stage 3** Claude Haiku — 공간 + Stage 2 결과 기반 27 표준항목 × 6 법령 점검표 자동 생성
- **5/17 신규**: 사용자가 [반영하기] 클릭 시 stage2 정정 결과를 점검표 라디오에 자동 prefill (`_prefill_item_scores_from_stage2`)
- **5/17 후반 보강**:
  - `_prefill_item_scores_from_stage2` 가 `status` 필드 반영 (상태불량→0.5). 이전엔 모든 detected 가 1.0 매핑되어 점수 부풀려졌음 (P0)
  - `user_corrections` 항목은 두 번째 [반영하기] 에서도 강제 덮어쓰기 (no-op 해소)
  - 재분석 시 `stage2_user_marks` + `_radio_counter` 초기화
  - `_truncated_recovered` 시 사용자 경고 배너

## 시연 모드 안전 장치 (5/17 후반 강화)
- 시연 합성 응답 명시 (Stage 2 카드 위 노란 배너 + `_synth_demo` 마커)
- **사이드바 DEMO 인디케이터 상시 표시** (모든 페이지)
- 자기보고 vs AI 탐지 불일치 빨간 경고
- 재점검 주기 알림 (60/90/180일)
- 시연 학교에 공간 0개면 데모 화학실 자동 등록 + 1회 안내 info
- **실 사진 5공간(화학·물리·음악·미술·디자인)**: PIL 더미 대신 sample_images 자동 사용
- **합성 응답에 likely_absent 1건 + ambiguous 2건 결정적 보장** — "AI 부재→교사 정정" 시나리오 작동
- 교육청 수신함에 시연 데이터 2건 자동 (단일 + 통합) — `import os` 누락 P0 해결
- 데모 매니저 PIN `000000` (자동 입력 버튼)
- **시연 매니저 보호**: PIN 재발급·비활성화·담당 공간 변경 모두 disabled (실수로 누르면 시연 깨짐 방지)
- **시연 종료 시 cleanup 옵션** (`cleanup_demo_artifacts()`): `_demo` 매니저·`_synth_demo` 수신함·캐시 일괄 삭제

## 통합 발송 — 앱 내 직접 전송 (5/17 후반 신규)
이전엔 "통합 완료 처리" 가 status 만 바꾸고 실제 발송은 안 함 (D-1 P0).
- `mark_consolidated(record=...)` 가 받은 record 를 `submit_to_edu_inbox_direct` 로 mock_edu_receipt 에 즉시 저장
- `submit_to_edu_inbox_direct` 가 `school_identified or school` fallback → 통합본도 처리
- 파일명 `_consolidated.json` 접미사로 단일/통합 구분
- outbox 기록 record_type 분기 (`space_type` vs `통합 N공간`)
- 학교 담당자가 "교육청에 통합 발송" 클릭 시 즉시 교육청 수신함 도착 (별도 메일 발송 불필요)
- 반환 형식: `dict {count, submit, errors}` (이전 `int`)

## 위젯 핵심 패턴 (5/16 수정 — 다시 망가뜨리지 말 것)
**자동입력 안전 패턴 (Streamlit value= 무시 회피)**:
- 위젯 key 를 카운터로 동적 변경 — 새 위젯 인스턴스 생성 시 value 적용
- 예: `key=f"_pin_v{_pin_counter}"` + 버튼 클릭 시 `_pin_counter += 1`
- 적용 위치: PIN 자동입력 / 학교 인증번호 자동입력 / 점검표 일괄 채우기 / 점검표 prefill (`_radio_counter`)
- **5/17 후반**: Stage 2 재분석 시 `_radio_counter += 1` 추가 (재분석 결과 prefill 반영)

## 금지 사항 (사용자 명시 지속)
- KEIIS / 에듀파인 결재 / send_to_edu_app 복원
- "학교 클라우드" / "기계용 JSON" 표현
- 실 사진을 시연용으로 (5공간 sample_images 는 의도된 사용)
- PDF 에 결재란 추가 (이중 결재 모드 외)
- 메일앱 (mailto) 단독 사용
- 박스플롯·모델 신뢰도 학술 용어 메인 노출
- Stage 1/2/3 영문 jargon 화면 노출
- "전체 양호로 채우기" 만으로 만점
- 호스팅 클라우드 자동 도입
- 공모전 메타 표현 ("심사위원", "활용대회", "대회 마감" 등) — 일반화 완료
- 이모지 (5/16 일괄 제거 완료) — `★` 같은 텍스트 기호는 허용 (별표 시각 표시 용)

## 스모크 테스트
115건 통과 — `cd safeloop_demo && SAFELOOP_DEMO_MODE=1 python tests/smoke_test.py`

## 미해결 (다음 세션 검토)
- 🔵 외부 SMTP 통합 — 현재는 같은 인스턴스 내 직접 전송만
- 🔵 1_점검시작.py PEP8 들여쓰기 정돈
- 🔵 통합 보고서 수신함 상세 카드 분기 (spaces 펼침)
- 🟡 6_데이터순환 정수 인덱스 라디오 → session_id 기반
- 🟡 0_수합검토 expander 전각 공백 라벨 → 구조 변경
- 🟡 자동 로그인 페이지별 분산 → app.py 또는 ensure_state 에 통합
- 🟡 naive datetime.now() → 명시 timezone
- 🟡 reset_inspection 의 `_autoplay*` 키 미정리

## Git 흐름
- `git pull` / `git push` (`wizbeee/safeloop` Private)
- 자격증명 캐시되어 있어 추가 인증 불필요
- 모든 커밋: Conventional Commits 한국어 (배경/변경/검증 4단 구조) + Co-Authored-By Claude

## 작업자 컨텍스트
- 본업: 한국 고등학교 화학 교사 (충남삼성고)
- 1인 학생 프로젝트 + Claude 협업
- **한국어 평이한 안내 필수** — "스프린트"·"머지"·"브랜치" 같은 개발 용어 사용 자제
- 답변 길이는 짧고 명확하게 — 사용자가 답답해하면 즉시 정리
- 사용자가 직접 시연·테스트하며 발견하는 버그를 그 자리에서 수정하는 패턴
- **검토 → 종합 보고 → 우선순위 동의 → 묶음 수정 → 스모크 검증** 패턴 선호

## 자주 쓰는 위치
- `pages/2_AI점검.py` — 사진·AI·반영하기·점검표 prefill (1900줄+, 가장 큼)
- `pages/3_결과저장.py` — 저장·결재정책분기·교육청발송
- `pages/0_수합검토.py` — 학교 담당자 수합·검토·통합 자동 발송
- `pages/13_내제출이력.py` — 실 담당자 본인 이력·반려·재점검 (★ 신규)
- `pages/8_설정.py` — 매니저/결재정책/등록정책/이메일/AI공급자/시연 cleanup
- `modules/storage.py` — 학교 프로필 정책 + 매니저 + 통합 발송 + `cleanup_demo_artifacts`
- `modules/auth.py` — `_pin_codes()` 동적 / `_ROLE_KEYS` / `is_authenticated_session`
- `modules/managers.py` — 매니저 CRUD + PIN
- `modules/laws.py` — 27 항목 × 6 법령
- `modules/consolidate.py` — 학교 통합 보고서 + `mark_consolidated(record=)` 자동 발송
- `modules/demo_image.py` — sample_images 5공간 분배 + PIL 폴백
- `modules/demo_responses.py` — 합성 응답(detected/absent/ambig 3분류 + `_synth_demo`)
- `modules/ui.py` — DEMO 인디케이터 + `mobile_pc_hint()` + 사이드바 역할별 메뉴

## 새 세션 시작 첫 응답
사용자가 작업 지시를 주기 전에:
1. `HANDOFF_NEXT.md` 와 본 메모리 파일 읽었다고 확인
2. 현재 완성도 (98점) + 미해결 항목 요약 (1~2줄)
3. "구체적인 작업 지시를 기다리겠습니다" 한 줄

장황하게 환영 메시지 X. 평이하고 짧게.
