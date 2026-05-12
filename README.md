# 세이프루프 (SafeLoop)

> **공공데이터로 시작해, 공공데이터로 돌아옵니다.**
>
> 학교 안전을 한 사이클로 묶는 AI 비전 기반 점검·환원 시스템.

[![Repo](https://img.shields.io/badge/repo-wizbeee%2Fsafeloop-D50000)](https://github.com/wizbeee/safeloop)
[![Branch](https://img.shields.io/badge/branch-main-D50000)](https://github.com/wizbeee/safeloop/tree/main)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![Streamlit](https://img.shields.io/badge/streamlit-1.30%2B-red)]()
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> 🚀 **라이브 데모**: 배포 후 이 자리에 URL 추가 — `https://safeloop.streamlit.app`
>
> 🎥 **시연 영상**: [DEPLOY_TO_STREAMLIT_CLOUD.md](DEPLOY_TO_STREAMLIT_CLOUD.md) 따라 배포 후 추가

> 🆕 **다른 컴퓨터에서 시작?** [`NEW_PC_START.md`](NEW_PC_START.md) → 5단계 / 약 15분

> ★ **작업 폴더는 [`safeloop_demo/`](safeloop_demo/)** — 운영 코드는 모두 여기에 있습니다.
> 루트의 [`_archive_v8_contest/`](_archive_v8_contest/) 는 공모전 출품 시점(2026-04) 보관 자료 — 작업 대상 아닙니다.

제8회 교육 공공데이터 AI 활용대회 출품작 — 마감 2026-05-31

---

## 🎯 한눈에 보는 SafeLoop

```
공공데이터  →  Stage 1 대시보드  →  위험군 526교 식별
                                            ↓
                                    Stage 2 AI 맞춤 점검
                                    (사진 → 공간 식별 → 설비 탐지 → 점검표)
                                            ↓
                                    Stage 3 현장 점검 + 안전 점수
                                            ↓
                              에듀파인 결재 → 교육청 → KEIIS
                                            ↓
                                  공공데이터 환원
                                            ↓
                                Stage 1 더 정교화  ←─── 순환 완성
```

## 🧱 차별점 3가지

1. **공간 맞춤 점검표** — 일률 점검표를 6개 법령 기반 맞춤표로 (단계 3 AI 자동 설계)
2. **데이터 순환** — 점검 결과가 KEIIS·공공데이터포털로 환원되어 대시보드 자체가 진화
3. **기존 제도 존중** — 에듀파인·KEIIS·공공데이터포털을 대체하지 않고 가교 역할만

## ✨ 주요 기능

| 영역 | 기능 |
|---|---|
| **학교 식별** | GPS 자동 · 학교명 검색 · 지역 단계 검색 + 담당자 인증 |
| **AI 비전 (3단계)** | 공간 유형 식별 → 설비 탐지(탐지/부재/모호 3분류) → 맞춤 점검표 |
| **AI 공급자 교체** | Anthropic Claude · OpenAI GPT-4o (설정에서 선택, 교차검증 옵션) |
| **이미지 사전 검사** | 블러·어두움·해상도 자동 검사 + 회전·리사이즈 |
| **현장 점검** | 양호/불량/부재 입력 → 안전점수(A~E) + 카테고리 레이더 |
| **이중 저장** | Human(PDF·Excel·CSV) + Machine(JSON 3종) 자동 생성 |
| **에듀파인 패키지** | 결재용 공문(품의서) + 첨부 ZIP 자동 생성 |
| **교육청 수신함** | 옵션 2 직접 발송 모듈 (KEIIS 입력 지원) |
| **대시보드 A/B** | 본교 실시간 / 전국 공공데이터 분기 갱신 이원화 |
| **점검 이력** | 학교별 누적 + 시계열 + 두 시점 비교 |
| **정책 시뮬레이터** | 위험군에 X억 투입 시 점수·등급 변화 추정 |
| **데이터 순환** | Sankey + 결재 애니메이션 + 정책 시나리오 |
| **다중 채널** | PWA(홈 화면 추가) · iPhone 카메라 직행 · 모바일 우선 |

## 🚀 다른 컴퓨터에서 실행 (3분)

```bash
git clone https://github.com/wizbeee/science-lab-application.git
cd science-lab-application
git checkout feat/safeloop-demo
cd "SafeLoop_데모앱_이관세트/safeloop_demo"
pip install -r requirements.txt
python setup.py unlock        # 암호 입력 → .env 자동 생성
python -m streamlit run app.py
```

암호를 모르거나 본인 키를 직접 사용하려면 [SETUP_ON_NEW_MACHINE.md](SETUP_ON_NEW_MACHINE.md) 참조.

## 📲 모바일 / iPhone

iOS Safari는 HTTPS에서만 카메라·GPS를 허용합니다. 두 가지 방법:

**A. ngrok 즉시 터널링**
```bash
ngrok http 8501
# 출력된 https://xxx.ngrok-free.app 을 iPhone Safari 에서 열기
```

**B. Streamlit Community Cloud 배포** — [DEPLOY_TO_STREAMLIT_CLOUD.md](DEPLOY_TO_STREAMLIT_CLOUD.md)

## 🗂 디렉토리

```
safeloop/
├── README.md                       ← 이 문서
├── README_먼저읽기.md
├── NEW_PC_START.md                 ★ 다른 PC 시작 가이드
├── SETUP_ON_NEW_MACHINE.md
├── HANDOFF_NEXT.md                 다음 세션 인계
├── ARCHITECTURE.md
├── CHANGELOG.md
├── DEPLOY_TO_STREAMLIT_CLOUD.md
├── LICENSE
├── _claude_memory/                  Claude 세션 시드 (자동 인식)
├── safeloop_demo/                   ★ 🚀 운영 앱 (작업 위치)
│   ├── app.py                       홈
│   ├── pages/                       12개 페이지
│   │   ├── 1_점검시작.py
│   │   ├── 2_AI점검.py
│   │   ├── 3_결과저장.py
│   │   ├── 4_본교현황.py
│   │   ├── 5_전국대시보드.py
│   │   ├── 6_데이터순환.py
│   │   ├── 7_교육청수신함.py
│   │   ├── 8_설정.py
│   │   ├── 9_프로젝트소개.py
│   │   ├── 10_점검이력.py
│   │   ├── 11_정책시뮬레이터.py
│   │   └── 12_데이터불러오기.py
│   ├── modules/                     16개 공용 모듈
│   │   ├── auth.py                  PIN 인증 + 자동 로그인
│   │   ├── ai_providers.py          공급자 어댑터
│   │   ├── ai_vision.py             설비 탐지 + 점검표 생성
│   │   ├── image_quality.py         블러/어둠/리사이즈
│   │   ├── data_loader.py
│   │   ├── laws.py                  6개 법령 × 27 표준항목 + 공간 분기
│   │   ├── score.py                 V-1 v3 가중합산
│   │   ├── recommend.py
│   │   ├── storage.py               이중 저장 + 에듀파인 패키지
│   │   ├── crypto.py                AES-256-GCM 자동 암호화
│   │   ├── session.py
│   │   ├── ui.py                    Swiss 테마 + PWA 메타
│   │   ├── prompts.py
│   │   ├── demo_image.py / demo_responses.py / sample_dispatch.py
│   ├── data/                        공공데이터 CSV (앱이 직접 사용)
│   ├── sample_images/               5공간 35장 (화학·물리·음악·미술·디자인)
│   ├── school_storage/              학교별 격리 저장
│   ├── static/                      PWA 매니페스트·아이콘
│   ├── tests/smoke_test.py          73건 통합 스모크
│   ├── setup.py                     AES-256 .env 암·복호화
│   └── requirements.txt
└── _archive_v8_contest/             📦 공모전 시점 보관 (작업 대상 아님)
    ├── README.md                    이 폴더 설명
    ├── code/poc_run.py              옛 PoC 원본
    ├── docs/                        출품 시점 명세서·핵심서사
    ├── data/                        출품 시점 CSV 사본
    ├── sample_images/               출품 시점 13장 (화학·물리)
    ├── reference_pdfs/              참고 점검표·법령
    ├── validation/                  V1 점검표 비교 · V2 예산 시나리오
    ├── env_config/
    ├── CONTEST_CHECKLIST.md
    └── HANDOFF_FIX50.md
```

## 🔐 보안

- API 키는 `.env` 평문 절대 커밋 금지 (`.gitignore`로 차단)
- 대신 AES-256(Fernet) + PBKDF2-SHA256 390k iter 으로 암호화한 `.env.enc` 만 커밋
- 복원 시 `python setup.py unlock` + 암호 입력
- 모든 점검 데이터: 학교별 격리 디렉토리 (`school_storage/{학교코드}/`)
- 공공 환원 시 학교명·코드 SHA-256 해시 익명화

## 🏛 법령·제도 적합성

| 법령 | SafeLoop의 역할 |
|---|---|
| 공공데이터법 | "업무 부산물 개방" 원칙 준수 — 별도 수집 X |
| 교육시설법 제10조 3항 | 자체 점검 결과를 KEIIS에 제출 |
| 학교안전법 제4조 | 학교계획 수립·실적 평가 데이터 보강 |
| 학교보건법 / 산안법 / 소방시설법 / 위험물안전관리법 | 27 표준항목 매핑 |

## 📅 개발 일정

| Phase | 시기 | 내용 |
|---|---|---|
| MVP | 2026-04 (현재) | 11개 페이지 · AI 파이프라인 · 이중 저장 · 에듀파인 시뮬레이터 |
| Phase 2 | 6~12개월 | 교육청 수신 모듈 실제 운영 · KEIIS 연계 협의 |
| Phase 3 | 1~3년 | KEIIS API · 에듀파인 결재 이벤트 · 공공데이터포털 자동 등록 |

## 🤝 라이선스 · 기여

MIT License · Issue/PR 환영 · 문의: [GitHub Issues](https://github.com/wizbeee/science-lab-application/issues)

---
**팀명**: 세이프루프  ·  **제8회 교육 공공데이터 AI 활용대회**  ·  마감 2026-05-31
