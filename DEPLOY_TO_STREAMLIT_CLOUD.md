# Streamlit Community Cloud 배포 (5분, 무료 HTTPS)

iPhone 카메라/GPS는 **HTTPS 필수**. 배포하면 모든 모바일에서 즉시 작동.

## 0) 사전 준비
- GitHub 계정 (`wizbeee`)
- 현재 저장소 `science-lab-application`이 public 상태 (확인됨)
- Anthropic API 키 (또는 OpenAI 키)

## 1) Streamlit Cloud 가입 및 앱 생성

1. https://share.streamlit.io 접속
2. **Continue with GitHub** → wizbeee 계정으로 로그인
3. 우상단 **New app** → **From existing repo**
4. 다음 값으로 입력:

| 필드 | 값 |
|---|---|
| Repository | `wizbeee/science-lab-application` |
| Branch | `feat/safeloop-demo` |
| Main file path | `SafeLoop_데모앱_이관세트/safeloop_demo/app.py` |
| App URL (선택) | `safeloop` (URL: `https://safeloop.streamlit.app`) |

## 2) Secrets 설정 (★ 중요)

배포 직전에 **Advanced settings** → **Secrets** 클릭:

```toml
ANTHROPIC_API_KEY = "sk-ant-api03-..."

# OpenAI도 함께 쓰려면:
# OPENAI_API_KEY = "sk-..."

# 자동 공급자 선택 (선택)
# SAFELOOP_PROVIDER = "anthropic"
```

이렇게 하면 **`.env` 없이도** 배포된 앱이 즉시 AI 호출 가능.
(`modules/ai_providers.py`가 `st.secrets`를 자동 fallback으로 읽음)

## 3) 배포

**Deploy** 클릭 → 약 2~3분 후 https://safeloop.streamlit.app (또는 자동 URL) 발급.

## 4) 배포 후 점검

- [ ] 홈에서 "점검하러 가기" 동작
- [ ] 학교 검색 → 인증 → 공간 등록까지 흐름
- [ ] 시연 모드 켜고 화학실 샘플 6장 → AI 분석 (약 30~60초)
- [ ] 결과 저장 → PDF·ZIP 다운로드
- [ ] iPhone Safari에서 카메라 동작 (HTTPS 자동)
- [ ] iPhone "공유" → "홈 화면에 추가" → PWA 설치 확인

## 5) 슬라이드·발표 자료에 URL 삽입

- 슬라이드 1 (표지): URL + QR
- 슬라이드 15 (마무리): URL 다시 강조
- README.md 상단 배지 추가:
  ```markdown
  [![Demo](https://img.shields.io/badge/demo-safeloop.streamlit.app-D50000)](https://safeloop.streamlit.app)
  ```

## 6) 발표 전날 워밍업

Streamlit Cloud 무료 Tier는 **7일 미사용 시 자동 슬립**. 슬립 상태에서 첫 접속은 30초 부팅 소요.

발표 1일 전:
1. URL 직접 접속해 워밍업
2. AI 분석 1회 실행 (캐시 적재)
3. 시연 자동재생 1회 실행

## 7) 무료 한도

| 항목 | 한도 | 우리 사용 예상 |
|---|---|---|
| 메모리 | 1 GB | ~600 MB (CSV 캐시 포함) |
| 동시 사용자 | ~10명 | 발표 시 5명 내외 |
| 슬립 정책 | 7일 미사용 시 | 워밍업으로 회피 |
| 트래픽 | 비공개 (제한 거의 없음) | — |

## 8) 도메인 커스텀 (선택)

`safeloop.streamlit.app` 대신 자체 도메인을 쓰려면:
- Streamlit Cloud 무료는 자체 도메인 미지원
- 대안: Cloudflare Pages 또는 Vercel + Streamlit 백엔드 (별도 구성)

## 9) 문제 해결

| 증상 | 해결 |
|---|---|
| `ModuleNotFoundError: cryptography` | `requirements.txt`에 이미 포함, Streamlit Cloud 재빌드 |
| 한글 PDF 깨짐 | `packages.txt`에 `fonts-nanum` 추가 (Linux 환경) |
| `ANTHROPIC_API_KEY not set` | Secrets 재확인 후 재배포 |
| 첫 로딩 30초 이상 | 슬립 해제 중, 정상 |
| iPhone 카메라 권한 안 뜸 | HTTPS 확인 + 사파리 설정에서 카메라 허용 |

### packages.txt (Linux 폰트 설치 — 필요 시)
```
fonts-nanum
fonts-noto-cjk
```

`SafeLoop_데모앱_이관세트/safeloop_demo/packages.txt`로 만들면 Streamlit Cloud가 자동 apt-get 설치.

## 10) 업데이트 워크플로

```bash
# 로컬에서 수정 후
git add .
git commit -m "feat: ..."
git push origin feat/safeloop-demo
```

→ Streamlit Cloud가 자동 재배포 (1~2분)

---

## 빠른 체크리스트

- [ ] https://share.streamlit.io 가입
- [ ] New app → repo·branch·main file 입력
- [ ] Secrets에 ANTHROPIC_API_KEY 입력
- [ ] Deploy
- [ ] 배포된 URL을 README + 슬라이드에 삽입
- [ ] iPhone에서 PWA 설치 테스트
- [ ] 발표 1일 전 워밍업
