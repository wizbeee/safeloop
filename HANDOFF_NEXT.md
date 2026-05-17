# SafeLoop 다음 세션 인계 — 2026-05-17 (후반)

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

## 현재 위치 (2026-05-17 후반 기준)

- **GitHub**: `https://github.com/wizbeee/safeloop` (Private) — main 브랜치 `859432d`
- **로컬 폴더**: `C:\Users\danie\Desktop\Claude Code\safeloop\`
- **다른 PC 시작**: [`NEW_PC_START.md`](NEW_PC_START.md)
- **Claude 메모리 시드**: `_claude_memory/project_safeloop.md`
- **스모크 테스트**: 115건 모두 통과 (`cd safeloop_demo && SAFELOOP_DEMO_MODE=1 python tests/smoke_test.py`)
- **완성도 평가**: **98점** (시연·콘테스트·베타 도입 모두 가능. P0급 결함 9건 + P1 19건 일괄 수정 + 신규 페이지 1개)

---

## 작업 중 (다음 세션이 검토할 미해결)

| 우선 | 항목 | 메모 |
|:-:|---|---|
| 🔵 | 외부 SMTP 통합 | 현재는 같은 SafeLoop 인스턴스 내 직접 전송(submit_to_edu_inbox_direct)만 지원. 분산 환경에서 실 메일 발송 필요 시 SMTP/HTTP API 통합 필요 |
| 🔵 | 1_점검시작.py PEP8 들여쓰기 | 동작 무관, 코드 정리만 |
| 🔵 | 통합 보고서 수신함 상세 카드 분기 | record_type 표시·파일명 접미사·sort 는 처리됨. 상세 조회 시 spaces 펼침 카드는 미구현 |
| 🟡 | 6_데이터순환 정수 인덱스 라디오 | session_id 기반 옵션으로 재설계 권장 (현재 동작은 정상) |
| 🟡 | 0_수합검토 expander 전각 공백 라벨 | 접근성 — 헤더 카드를 expander 본문에서 라벨로 옮기는 큰 구조 변경 필요 |
| 🟡 | 자동 로그인 페이지별 분산 | 학교·매니저 자동 로그인이 1_점검시작.py 에서만 시도됨. 다른 페이지 URL 직진입 시 학교 컨텍스트 없으면 막힘 |
| 🟡 | naive datetime.now() 타임존 | Streamlit Cloud(UTC) 배포 시 KST 와 9시간 어긋남 |
| 🟡 | reset_inspection 의 _autoplay* 키 미정리 | 시연 후 일반 점검 진입 시 잔존 가능 |

---

## 5월 17일 후반 세션의 핵심 변경 (커밋 `859432d`)

이번 세션은 **4영역 전수 검토 + 버튼 정적 분석 + 권장 작업 4건** 일괄 처리.
20 파일 / +1034 / -180 라인 / 신규 페이지 1개.

### [시연 안정성]
- **`ensure_demo_edu_inbox` 의 `os` import 누락 버그**: 환경변수 분기 자체 제거, 호출자 책임. 시연 inbox 가 영영 안 만들어지던 P0
- **실 사진 5공간(화학·물리·음악·미술·디자인) 35장**: `sample_dispatch` 키워드 매핑으로 의미 분배. 자동 흐름이 더 이상 PIL 더미로 덮어쓰지 않음
- **합성 응답 보강**: `likely_absent` 1건 + `ambiguous` 2건 결정적 보장. summary 의 "시뮬레이션" 표현 제거 (PDF 흘러갈 위험)
- **사이드바 DEMO 인디케이터**: 빨강 뱃지 상시 표시
- **`cleanup_demo_artifacts()` 신규**: `_demo` 매니저·`_synth_demo` 수신함·캐시 일괄 삭제. 시연 종료 시 체크박스로 노출
- **시연 매니저 보호**: PIN 재발급·비활성화·담당 공간 변경 모두 `disabled=_is_demo`

### [보안·인증]
- **12_데이터불러오기 인증 우회 차단**: 업로드만으로 `school_auth_verified=True` 강제하던 P0. False 로 + 인증 안내
- **auth.py PIN_CODES 동적화**: 정적 `PIN_CODES` 제거, `_pin_codes()`/`_ROLE_KEYS` 일원화. 운영 PIN 환경변수 사용 시 자동 로그인 영구 실패하던 P0
- **role hijack 차단**: 7_교육청수신함·11_정책시뮬레이터 가드 통과 후 `role="교육청"` 강제 set 제거. role 다르면 [설정]에서 명시 전환 안내

### [점수 정확성]
- **`_prefill_item_scores_from_stage2` 가 `status` 반영**: "상태불량"→0.5. 이전엔 모든 detected 가 1.0(양호) 매핑되어 안전 점수 부풀려졌음
- **직접 수정 점수 키 매핑**: `find_std_match(title)` 로 STANDARD_ITEMS 표준명 키 저장 — 매핑 누락 시 점수 0점 폭락하던 P1
- **30 항목 컷오프 제거**: 화학실 35+ 항목도 모두 수정 가능
- **score vs recommend 정책 통일**: 미점검 항목 추천 제외. "S=100점·추천 19건" 모순 해소
- **truncated_recovered 경고 UI**: Stage 3 응답 잘릴 때 사용자에게 명시
- **Stage 2 재분석 시 stage2_user_marks 초기화**: 항목 수 변할 때 옛 체크 잘못 매핑 방지

### [통합 발송 — 앱 내 직접 전송]
- **`submit_to_edu_inbox_direct` 통합본 지원**: `school_identified` 또는 `school` fallback. `_consolidated.json` 접미사. outbox 기록 record_type 분기
- **`mark_consolidated(record=...)`**: record 인자 받으면 실제 mock_edu_receipt 전송. 반환 `int`→`dict {count, submit, errors}`
- **"통합 완료 처리" 실제 발송 동작**: 이전엔 status 만 변경하고 파일은 안 보내던 P0. 이제 교육청 수신함에 즉시 도착
- **안내 카피 정리**: "교육청 수신함으로 자동 전송"

### [신규 페이지 `pages/13_내제출이력.py`]
실 담당자가 본인 제출 이력·반려 사유·재점검 진입점 확인.
- 본인 매니저 ID 로 필터링 + 상태별 KPI(반려/대기/승인/통합)
- 반려 카드 우선 노출 + 사유 expander 기본 펼침
- "다시 점검" 버튼: reset_inspection + active_space 복원 → 1_점검시작
- 사이드바 "내 이력 → 제출 이력 (반려 N)" 배지

### [흐름·UX]
- **실 담당자 반려 알림**: 1_점검시작 진입 시 본인 반려 점검 N건 + 공간명 알림
- **"다른 학교 선택" 정리**: `active_space`/`space_manager` 도 함께 비워 옛 학교 컨텍스트 잔존 방지
- **보완 사진 재분석 버튼**: supplement 단계에서 ai_run 으로 명시 이동 — 트리거 미소비되던 P0
- **데모 공간 자동 등록 후 1회 안내**

### [버튼 정적 분석 — 동작 안 하던 P0]
- **별표 시각 표시 누락**: 7_교육청수신함 컬럼 셀·헤더 카드 모두 빈 문자열/None 출력. `★`/`""` 로
- **정렬 elif 중복**: "오래된순"/"낮은순" 도달 불가 (startswith prefix 같음). `in` 매칭 + endswith 구별
- **라벨 가변 위젯에 명시 key 5건**: `demo_all_good`, `demo_random`, `calc_safety_score`, `goto_next_space`, `goto_save` 등
- **trailing space 라벨 정리**: "AI 분석 단계로 " → "AI 분석 단계로" 등

### [모바일 가독성]
- `modules/ui.py:mobile_pc_hint()` 신규 — 모바일(≤768px)에서만 PC 권장 안내 박스
- 0_수합검토/4_본교현황/6_데이터순환/7_교육청수신함/10_점검이력 5개 wide 페이지에 일관 적용
- 0_수합검토 제출 메타정보 모바일 2×2 그리드 (sl-sub-* CSS)

### [기타 정리]
- 시연 종료 데이터 cleanup 체크박스
- `_dispatch_confirm` 닫기 시 pop
- 반려/수정 취소 시 widget state pop (이전 사유·라디오 잔존 방지)
- 4_본교현황 plotly 중복 import 제거
- 토스트 `icon=""` → `None` 일관성

---

## 자주 쓰는 위치 (참고)

- `pages/2_AI점검.py` — 사진 + AI + 반영하기 + 점검표 (1900줄+, 가장 큼)
- `pages/3_결과저장.py` — 저장 + 결재 정책 분기 + 교육청 발송
- `pages/0_수합검토.py` — 학교 담당자 수합·검토·통합 발송 (자동 전송)
- `pages/13_내제출이력.py` — 실 담당자 본인 이력·반려·재점검 (★ 신규)
- `pages/8_설정.py` — 매니저 명부 / 결재 정책 / 등록 정책 / 시연 cleanup / AI 공급자
- `modules/storage.py` — 학교 프로필 정책 + 매니저 + 통합 발송 + cleanup_demo_artifacts
- `modules/managers.py` — 매니저 CRUD + PIN 발급/검증
- `modules/laws.py` — 27 표준 항목 × 6 법령 매핑 + 공간별 적용
- `modules/score.py` — V-1 v3 가중합산
- `modules/consolidate.py` — 학교 단위 통합 보고서 + mark_consolidated(record=)
- `modules/auth.py` — `_pin_codes()` 동적 / `_ROLE_KEYS` / `is_authenticated_session`
- `modules/demo_image.py` — sample_images 5공간 분배 + PIL 폴백
- `modules/demo_responses.py` — 합성 응답(detected/absent/ambig 3분류)
- `modules/ui.py` — apply_theme + render_sidebar + mobile_pc_hint + DEMO 인디케이터

---

## 운영 환경

- **시연 모드**: `SAFELOOP_DEMO_MODE=1` 또는 홈에서 "시연 시작" (session_state)
- **실 운영 모드**: `.env` 에 `ANTHROPIC_API_KEY` 필요
- **암호화 키**: `SAFELOOP_KEY` (32바이트 hex) 또는 시연 모드
- **시연 PIN 빠른 참조**:
  - 교육청 담당자: `EDU2026` (또는 환경변수 `SAFELOOP_EDU_PIN`)
  - 데모 매니저: `000000` (시연 매니저 보호 적용 — PIN 재발급/비활성/공간 변경 disabled)

---

## 작업자 컨텍스트

- 본업: 한국 고등학교 화학 교사 (충남삼성고)
- 1인 학생 프로젝트 + Claude 협업
- 한국 학교 시설 안전 점검 도메인 전문
- 시연·발표용 + 실제 학교 베타 도입 가능 수준 추구
- 영어·개발자 용어 어려워하시므로 평이한 한국어 + 친절한 안내 필수
