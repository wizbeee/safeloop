# Claude 메모리 동기화 폴더

> 다른 PC 에서 새 Claude Code 세션 시작 시 **SafeLoop 작업 컨텍스트 자동 인식**용.

## 무엇이 들어있나

### `project_safeloop.md`
SafeLoop 프로젝트 현황 — 위치·브랜치·발송 흐름·금지사항·다음 작업 등 핵심 메타데이터.
다음 Claude 세션이 SafeLoop 작업을 즉시 이어갈 수 있도록 자동 인식되는 메모리.

---

## 다른 PC 에서 사용법 (3단계)

### Step 1. 메모리 폴더 위치 만들기
```powershell
$memDir = "$env:USERPROFILE\.claude\projects\C--Users-$env:USERNAME-Desktop----------\memory"
New-Item -ItemType Directory -Path $memDir -Force | Out-Null
```

> ⚠ 위 경로는 워크스페이스가 `Desktop\클로드 코드 관련\` 일 때만 유효.
> 다른 폴더 명이면 `C--Users-...-` 부분이 달라짐. Claude 세션 처음 진입 시
> Claude 가 자동으로 만들어주므로 **첫 세션 1회 진행 후** 메모리 복사하는 게 안전.

### Step 2. 이 폴더의 메모리 복사
```powershell
Copy-Item "safeloop\_claude_memory\*.md" $memDir -Force
```

### Step 3. 메모리 인덱스에 SafeLoop 항목 추가 (선택)
`$memDir\MEMORY.md` 파일에 다음 한 줄 추가 (없으면 새로 작성):

```markdown
- [SafeLoop 프로젝트](project_safeloop.md) — 학교 안전 점검 앱 — `safeloop/` 폴더 (GitHub `wizbeee/safeloop` Private, main 브랜치). 다음 세션은 `safeloop/HANDOFF_NEXT.md` 우선
```

→ Claude 세션 시작 시 이 줄을 보고 `project_safeloop.md` 자동 로드.

---

## 동기화 (앞으로)

작업 진행에 따라 메모리가 갱신되면:

```powershell
# 갱신된 메모리를 레포로
Copy-Item "$env:USERPROFILE\.claude\projects\C--Users-$env:USERNAME-Desktop----------\memory\project_safeloop.md" "safeloop\_claude_memory\" -Force

# Git push
cd safeloop
git add _claude_memory/
git commit -m "docs: Claude 메모리 갱신"
git push
```

---

## 주의

- `_claude_memory/` 폴더는 **참고·시드 데이터** — 실 메모리는 사용자 홈 디렉토리.
- API 키 같은 비밀 정보는 절대 메모리에 두지 마세요.
- 다른 사용자(공동 작업자)와 다른 PC 환경에선 SafeLoop 외 다른 프로젝트 메모리는 별도 관리.
