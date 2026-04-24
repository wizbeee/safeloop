# SafeLoop — 변경 이력

## [unreleased / 2026-04-24]

### Added — 완성도 일괄 향상
- **신규 페이지**
  - `pages/10_점검이력.py` — 학교별 누적 점검 + 시계열 추이 + 두 시점 비교
  - `pages/11_정책시뮬레이터.py` — 예산 → 점수·등급 변화 추정 + 카테고리 우선순위
- **신규 모듈**
  - `modules/image_quality.py` — 블러·어둠·해상도 사전 검사 + EXIF 회전 + 자동 리사이즈 (실측 86% 용량 절감)
- **AI 기능 강화**
  - `ai_vision.run_stage1_cross_check()` — Anthropic × OpenAI 합의 검증
  - 모든 단계 입력 자동 최적화 통합 (회전·리사이즈·압축)
  - `ai_providers` Streamlit Cloud Secrets fallback (.env 없이도 동작)
- **UI/UX**
  - 첫 방문 온보딩 안내 (3단계, "다시 보지 않기")
  - 시연 자동재생 모드 (임의 학교 선택 + 인증 자동 통과 → 시연 페이지)
  - 에듀파인 결재 단계별 시각화 (담당자→부장→교감→교장→교육청)
  - 출처 사진 매핑 표시 (탐지 설비 → 어느 사진에서 봤는지)
  - 교차검증 합의/불일치 알림
  - 사용자 수정 내역 → AI 재학습 데이터 자동 누적
- **PWA**
  - `static/manifest.json` + 192·512 아이콘
  - PWA 메타 태그 자동 주입 (`apple-mobile-web-app-capable`, `theme-color`)
  - iPhone "홈 화면에 추가" 가능
- **문서**
  - `README.md` (저장소 루트) — 한눈 정리 + 차별점 + 기능 + 실행
  - `ARCHITECTURE.md` — 시스템 컨텍스트·컴포넌트·데이터 흐름·확장
  - `DEPLOY_TO_STREAMLIT_CLOUD.md` — 5분 배포 가이드 + Secrets 설정
  - `LICENSE` — MIT
  - `CHANGELOG.md` — 본 문서
  - `.env.example` — 키 입력 예시
- **인프라**
  - `packages.txt` — Streamlit Cloud 한글 폰트(나눔·노토) 자동 설치

### Changed
- `pages/8_설정` — AI 공급자 섹션 + 교차검증·품질검사 토글 추가
- `pages/3_결과저장` — 결재 시뮬레이터 통합
- `app.py` — 온보딩·자동재생 영역 추가
- `modules/session.py` — 신규 상태 키 추가 (`cross_check`, `image_quality_check`, `_auth_prefill`, `_seen_onboarding`)

---

## [v1.1 / 2026-04-24 06:35]

### Added — 보안·이전성 강화
- `setup.py` — AES-256(Fernet) + PBKDF2-SHA256 390k iter `.env` ↔ `.env.enc` 양방향 도구
- `.env.enc` — 암호화 커밋 (다른 컴퓨터에서 unlock으로 복원)
- 누락 CSV 4개 (`master_school_data`, `high_risk_schools`, `school_code_mapping`, `risk_analysis_result`) 추가
- `requirements.txt` — `cryptography>=42.0.0`
- `SETUP_ON_NEW_MACHINE.md` 갱신 — unlock 절차

---

## [v1.0.5 / 2026-04-24 16:54] — 다른 컴퓨터 작업분
- 위저드 UI (한 구도씩 한 화면, 클래식 모드 토글)
- 사용자 동선 기반 촬영 가이드 (정면→우측→좌측), 과학실 전용 용어 제거
- 근접 촬영 → AI 인식 실패 시 보완 스텝
- `st.camera_input` → `st.file_uploader(capture=environment)` (모바일 네이티브 카메라)
- 검정 배경 글자 투명 문제 수정 (CSS `color !important`)
- AI 분석 완료 시 위저드 자동 진행

---

## [v1.0 / 2026-04-24 01:22]

### Added — 초기 출시
- 9개 페이지 (홈, 점검시작, AI점검, 결과저장, 본교현황, 전국대시보드, 데이터순환, 교육청수신함, 설정, 프로젝트소개)
- 10개 공용 모듈 (prompts, ai_vision, data_loader, score, recommend, laws, storage, session, ui)
- 공공데이터 CSV 8개 (11,929개교 분석 결과)
- 시연 사진 13장 (화학실 6 + 물리실 7)
- AI 3단계 파이프라인 (공간 인식 → 설비 탐지 → 맞춤 점검표)
- Anthropic Claude (Opus 4.5 · Haiku 4.5)
- 학교 검색 3방식 (GPS · 학교명 · 지역 단계)
- 인증 (학교코드 + 6자리 인증번호)
- 공간 등록·이어 점검
- Human-readable + Machine-readable 이중 저장
- 에듀파인 ZIP 패키지 + 앱 직접 발송 이중 채널
- 대시보드 A(본교 실시간) + B(공공데이터 BEFORE/AFTER) 이원화
- Sankey + 여정 타임라인 + 정책 시나리오
- Swiss International 디자인 (`modules/ui.py`)
