# 🚀 다른 컴퓨터에서 SafeLoop 작업 이어가기

> **5단계 · 약 15분.** 한 번 설정 후엔 `git pull` / `git push` 만으로 동기화.

---

## ✅ 사전 점검

다른 PC 에 다음 3가지 설치 (없으면 먼저 설치):

| 항목 | 설치 | 확인 |
|---|---|---|
| **Git** | https://git-scm.com/download/win | `git --version` |
| **Python 3.10+** | https://www.python.org/downloads/ → ⚠ "Add to PATH" 체크 | `python --version` |
| **GitHub CLI** | https://cli.github.com/ | `gh --version` |

---

## 1️⃣ GitHub 인증 (1회만)

```powershell
gh auth login
```
- GitHub.com → HTTPS → Login with a web browser
- 본인 계정(`wizbeee`)으로 로그인

---

## 2️⃣ 코드 받기

```powershell
cd $env:USERPROFILE\Desktop
mkdir "클로드 코드 관련" -ErrorAction SilentlyContinue
cd "클로드 코드 관련"
git clone https://github.com/wizbeee/safeloop.git
cd safeloop
```

성공 확인:
```powershell
git log --oneline -5
# → 최근 5개 커밋 출력되면 OK
```

---

## 3️⃣ Python 패키지 설치

```powershell
cd safeloop_app
python -m pip install -r requirements.txt
```

⏱ 처음 5~10분.

---

## 4️⃣ API 키 (`.env`) 복원 — **3가지 옵션 중 하나**

API 키는 보안상 GitHub 에 올라가지 않습니다. 다음 중 **하나** 선택:

### 옵션 A — `.env.enc` 복호화 (이전 PC 에서 lock 한 경우)
```powershell
python setup.py unlock
# → 비밀번호 입력 (이전 PC 에서 정한 값)
# → .env 자동 생성
```

### 옵션 B — Anthropic 새 키 발급 (권장 · 가장 간단)
1. https://console.anthropic.com/settings/keys
2. "Create Key" → 복사
3. 메모장으로 두 위치에 동일 내용 저장:
   - `safeloop\env_config\.env`
   - `safeloop\safeloop_app\.env`
   ```
   ANTHROPIC_API_KEY=sk-ant-여기에-새-키-붙여넣기
   ```

### 옵션 C — 기존 PC 에서 USB 로 복사
```powershell
# USB 에서 복사
Copy-Item "X:\.env" "safeloop\safeloop_app\.env"
Copy-Item "X:\.env" "safeloop\env_config\.env"
```

---

## 5️⃣ Claude Code 메모리 복원 (선택 — 권장)

새 Claude 세션이 SafeLoop 작업 컨텍스트를 자동 인식하려면:

```powershell
# 메모리 폴더 만들기 (Claude 가 자동 생성하기도 함 — 첫 세션 후 진행)
$memDir = "$env:USERPROFILE\.claude\projects\C--Users-$env:USERNAME-Desktop----------\memory"
New-Item -ItemType Directory -Path $memDir -Force | Out-Null

# 레포의 시드 메모리 복사
Copy-Item "_claude_memory\project_safeloop.md" $memDir -Force
```

> 자세한 내용: `_claude_memory/README.md` 참고

---

## 🎬 실행

```powershell
cd safeloop_app
$env:SAFELOOP_DEMO_MODE = "1"
python -m streamlit run app.py
```

→ 브라우저에서 `http://localhost:8501` 자동 열림.

---

## 🔄 일상 작업 (앞으로)

### 변경 후 동기화
```powershell
git add .
git commit -m "..."
git push
```

### 다른 PC 에서 받기
```powershell
git pull
```

> `.env` 는 `.gitignore` 라 push 안 됨 — 한 번 옵션 A/B/C 로 복원 후엔 그대로 유지.

---

## 🆘 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `git: command not found` | Git 미설치 | 사전 점검 다시 |
| `Authentication failed` (clone 시) | GitHub 인증 X | `gh auth login` |
| `pip install` 실패 | Python PATH 미설정 | Python 재설치 시 "Add to PATH" 체크 |
| `ModuleNotFoundError` (실행 시) | 패키지 미설치 | 3단계 다시 |
| AI 분석 안 됨 | `.env` 누락 | 4단계 다시 |
| 한글 깨짐 (PowerShell) | 인코딩 | `chcp 65001` 또는 새 PowerShell 7 사용 |

---

## ✅ 검증 (모두 OK 면 완성)

```powershell
cd safeloop\safeloop_app
$env:SAFELOOP_DEMO_MODE = "1"
python tests\smoke_test.py
```
→ **"73건 통과 / 0건 실패"** 출력되면 정상.

---

## 📁 폴더 구조 (받은 직후)

```
safeloop\                                 ← git clone 으로 받음
├── README.md
├── NEW_PC_START.md                       ← 이 파일
├── HANDOFF_NEXT.md                       ← 작업 인계
├── safeloop_app\
│   ├── app.py·modules\·pages\·tests\
│   ├── PRESENTATION_SCRIPT.md            ← 발표 시나리오
│   ├── PRESENTATION_KIT.md               ← 발표 자료 키트
│   ├── setup.py                          ← .env 암호화 도구
│   ├── .env.enc                          ← 암호화된 API 키 (옵션 A 시 사용)
│   ├── .env.example                      ← API 키 입력 예시
│   ├── data\·sample_images\
│   └── ... (코드)
├── _claude_memory\                       ← Claude 세션 컨텍스트 시드
│   ├── README.md
│   └── project_safeloop.md
└── docs\·reference_pdfs\·env_config\
```

---

## 💡 핵심 정보

| 항목 | 값 |
|---|---|
| **GitHub 레포** | https://github.com/wizbeee/safeloop (Private) |
| **기본 브랜치** | `main` |
| **시연 모드 환경변수** | `SAFELOOP_DEMO_MODE=1` |
| **교육청 PIN (시연용)** | `EDU2026` (운영 시 `SAFELOOP_EDU_PIN` 으로 분리) |
| **포트** | 8501 (기본) 또는 8516 (`launch.json` 사용 시) |

---

## 🎯 다음 작업

`HANDOFF_NEXT.md` 를 먼저 읽으면 **현재 어디까지 했고 다음 무엇을 해야 하는지** 즉시 파악 가능합니다.

1. 현재 완성도: **93점** (시연·콘테스트 가능 · 베타 도입 가능)
2. 사용자 손 검증 영역: 모바일 폰 직접 검증 (`HANDOFF_NEXT.md` 의 10개 체크리스트)
3. 발표 자료 작업: `safeloop_app/PRESENTATION_KIT.md`
