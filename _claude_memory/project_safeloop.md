---
name: SafeLoop 프로젝트 현황
description: SafeLoop 학교 안전 점검 앱 — 88점 완성도, 콘테스트·베타 도입 가능
type: project
originSessionId: 4187d9f7-f1f7-4b01-8060-42f967de9990
---

**위치**: `C:/Users/danie/Desktop/Claude Code/safeloop/` (정리 후 2026-05-12)
**GitHub**: `https://github.com/wizbeee/safeloop` (Private 레포)
**브랜치**: `main` + 정리 작업용 `chore/repo-cleanup-archive-v8-contest`
**★ 작업 폴더**: `safeloop_demo/` (운영 앱). 루트 `_archive_v8_contest/` 는 출품 시점 보관용 — 수정 금지.
**기술 스택**: Streamlit + Plotly + Anthropic/Gemini/GPT API + Python 3.10+ + extra-streamlit-components

**완성도**: 88점 종합 / 콘테스트 97점 / 베타 95점 / 시연 흐름 막힘 없음

**MVP 범위**:
- 일반교실 + 9개 특별교실 (화학·물리·생명·지구·기술·가정·음악·미술·디자인)
- 10개 공간 모두 시연 가능 (LAW_BASIS 기반 합성 응답 자동 주입)
- 디자인실: LAB_SPACES 포함 (PPE 자동 적용). 국소배기·장갑·MSDS 추가 (스프레이·본드·커터칼 위험)
- 음악실·미술실·디자인실 사진: 충남삼성고 본교 촬영 (총 5공간 35장)

**핵심 흐름 — 학교 → 교육청 발송 2가지**:
1. **🚀 앱 다이렉트 발송 (권장)** — 1클릭, 수신 확인 자동 추적. 단일 PC / 공유 NAS / 같은 클라우드 환경.
2. **📤 다운로드 후 직접 발송** — PDF + .safeloop 다운 → Gmail/Naver/Daum 웹 + 카톡 + Outlook (한국 사용자 친화). 분산 환경에서도 가능.

**핵심 흐름 — 교육청 수신함 (이메일 클라이언트 패턴)**:
- KPI 7개: 총 수신·미열람·별표·오늘·이번주·학교 수·평균 점수
- 빠른 토글: 미열람만 / 별표만
- 시간 그룹화: 오늘 / 이번주 / 이번달 / 이전
- 정렬: 미열람·별표 우선 (기본) / 수신일시 / 점수 / 학교명
- 일괄 액션: 읽음 처리 / 별표 토글 / 삭제
- 사이드바 미열람 배지 ●N
- 체크박스 = 자동 상세 조회 (드롭다운 X) → 첫 열람 시 read marker 저장

**보안·인증**:
- 교육청 PIN: `EDU2026` (운영: `SAFELOOP_EDU_PIN` 환경변수)
- 학교 6자리 인증번호 (4단계 발급 절차 안내: 학교→교육청 신청 / 발급 / 전달 / 재발급)
- AES-256-GCM 자동 암호화 (`SAFELOOP_KEY` 환경변수, 시연 시 `SAFELOOP_DEMO_MODE=1`)
- 운영자 도구 분리 (`SAFELOOP_ADMIN=1`)

**시연 모드 안전 장치**:
- 시연 합성 응답 명시 (Stage 2 카드 위 노란 배너 + `_synth_demo` 마커)
- 자기보고 vs AI 탐지 불일치 빨간 경고 (양호 처리한 부재 설비)
- 재점검 주기 알림 (60/90/180일 단계별 강조)

**금지 사항** (사용자 명시):
- ❌ KEIIS / 에듀파인 결재 / send_to_edu_app 복원
- ❌ "학교 클라우드" / "기계용 JSON" 표현 사용
- ❌ 실 사진을 시연용으로 (PIL 더미 + LAW_BASIS 합성만)
- ❌ PDF 에 결재란 추가
- ❌ 메일앱 (mailto) 단독 사용 — Gmail·Naver·Daum 웹 + 카톡 함께 제공
- ❌ 박스플롯·모델 신뢰도 학술 용어를 메인 화면에 노출
- ❌ Stage 1/2/3 영문 jargon 화면 노출 (① 안전 설비 탐지 / ② 맞춤 점검표)
- ❌ "전체 양호로 채우기" 만으로 만점 (자기보고 검증 우회 금지)
- ❌ 호스팅 클라우드 자동 도입 (사용자 결정 후만)

**스모크 테스트**: 73건 통과 (`cd safeloop_demo && SAFELOOP_DEMO_MODE=1 python tests/smoke_test.py`)

**남은 사용자 작업**:
1. 모바일 체크리스트 10개 손 검증 (iPhone Safari·Android·HEIC·EXIF·세션·카톡 공유)
2. 본인 학교 사진 7컷 → `sample_images/` (선택)
3. 발표 녹화 + 스크린샷 백업
4. 일괄 커밋 (의미 단위 6개)

**Git 흐름**: `git pull` / `git push` (`wizbeee/safeloop` Private). 다른 PC 에서 이어 작업 시 `git clone https://github.com/wizbeee/safeloop.git`

**Why**: 콘테스트 + 본교 활용 + 1~3개 베타 도입 가능 수준 완성. 자잘한 정리 + 사용자 손 검증만 남음.

**How to apply**: 다음 세션은 `HANDOFF_NEXT.md` (루트) + `safeloop_demo/PRESENTATION_SCRIPT.md` 우선 읽기. 코드 수정은 무조건 `safeloop_demo/` 안에서.

**자주 쓰는 위치**:
- `modules/storage.py` — 발송함·수신함·별표·일괄액션·다이렉트 발송
- `modules/demo_responses.py` — LAW_BASIS 합성 응답
- `modules/ui.py` — 사이드바 직관 라벨 + 미열람 배지
- `pages/2_AI점검.py` — 자기보고 검증 + 시연 합성 명시
- `pages/6_데이터순환.py` — 📤 데이터 전송 통합
- `pages/7_교육청수신함.py` — 이메일 클라이언트 패턴
- `PRESENTATION_SCRIPT.md` — 발표 1분/3분/5분 시나리오
