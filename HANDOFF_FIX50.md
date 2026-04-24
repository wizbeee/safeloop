# 50개 모순·오작동 수정 핸드오프

다른 컨텍스트 창에서 이어서 작업할 수 있도록 모든 이슈와 진행 상태를 정리한 문서입니다.

## 🎯 새 컨텍스트 창에서 시작하는 방법

```bash
# 1) 최신 코드 받기
cd "<클론한 경로>/science-lab-application"
git checkout feat/safeloop-demo
git pull
cd "SafeLoop_데모앱_이관세트"

# 2) 본 문서를 첫 메시지에 붙여넣기
cat HANDOFF_FIX50.md

# 3) Claude에게 다음과 같이 요청:
#    "HANDOFF_FIX50.md 의 ⏳ pending 항목들 이어서 수정해줘"
```

## 📦 작업 원칙

- 50개 이슈를 **3개 Phase**로 나눠 단계별 검증·커밋
- 각 이슈는 **(상태) ID — 제목 — 위치 — 수정 방향** 형식
- Phase 끝마다 스모크 테스트 51건 통과 + HTTP 200 확인 + 단일 커밋
- 본 문서는 작업 진행에 따라 갱신됨 (체크박스·날짜)

## 🚦 상태 표시

- ✅ Done — 수정·검증·커밋 완료
- 🔄 Partial — 일부만 처리, 후속 필요
- ⏳ Pending — 미착수
- 🚫 Skip — 의도적 보류 (이유 명시)

---

## Phase 1 — 발표 사고 방지 (🔴 11개)

### 0-1 자동재생 시 기존 학교·공간 덮어쓰기 ✅
- 파일: `safeloop_demo/app.py:127-141`
- 수정: `school` 또는 `active_space` 가 이미 있으면 confirm_button 후에만 진행

### 0-2 자동재생 반복 시 데모 공간 누적 ✅
- 파일: `safeloop_demo/app.py:138`
- 수정: `setdefault(...).append` 대신 동일 type+nickname 있으면 재사용

### 0-4 자동재생 후 stage 결과 잔존 ✅
- 파일: `safeloop_demo/app.py:127-142`
- 수정: 자동재생 시 `reset_inspection()` 호출

### 2-2 사진 비어있는데 stage 결과 남으면 드래프트 안내 안 뜸 ✅
- 파일: `safeloop_demo/pages/2_AI점검.py:131-132`
- 수정: stage1·2·3 결과가 있으면 그것도 함께 정리하거나 안내

### 2-11 AI 캐시 키가 전체 사진 해시 → 보완 시 모든 단계 재호출 ✅
- 파일: `modules/ai_vision.py:79, 105`
- 수정: stage1 캐시는 광각 3장 해시, stage2/3은 사용자 합의된 입력 해시로 분리

### 2-15 AI 분석 try 안에서 rerun → except 영원히 안 들어감 ✅
- 파일: `safeloop_demo/pages/2_AI점검.py:680-695`
- 수정: `_go_to_step("supplement")`을 try 바깥(finally)으로 이동

### 3-2 결과 저장 후 다른 공간 점검 시 saved_session_id 휘발 ✅
- 파일: `modules/session.py:71-88` reset_inspection
- 수정: saved_session_id 보존하거나 별도 키로 이력 보관

### 5-1 BEFORE/AFTER 토글이 차트 안 바꿈 ✅
- 파일: `safeloop_demo/pages/5_전국대시보드.py:67-84, 121-155`
- 수정: AFTER 모드일 땐 가상의 4차원 해상도 시뮬 (또는 안내문만 강화)

### 5-2 필터 적용해도 차트는 원본 사용 ✅
- 파일: `safeloop_demo/pages/5_전국대시보드.py:91-106, 121-155`
- 수정: subset에서 시도별 집계 재계산하여 fig1·fig2·fig3에 반영

### 8-4 cross_check 토글 disabled여도 세션 True 잔존 ✅
- 파일: `safeloop_demo/pages/8_설정.py:191-199`
- 수정: `if not multi_avail: cross_check = False` 강제 정리

### G-2 사이드바 confirm 버튼 깨짐 ✅
- 파일: `safeloop_demo/app.py:148-152` + `modules/ui.py confirm_button`
- 수정: 사이드바에선 confirm 대신 단순 버튼 + st.toast 또는 사이드바 전용 컴팩트 모드

---

## Phase 2 — 흐름 모순 critical (🟡 14개)

### 1-1 GPS 탭 정리 ✅
- 파일: `safeloop_demo/pages/1_점검시작.py:128-148`
- 수정: GPS 탭 제거 또는 "현재 위치 확인 (참고용)" 라벨로 명확화

### 1-5 이미 active_space 있는데 새 등록 시 충돌 ✅
- 파일: `safeloop_demo/pages/1_점검시작.py:280-295`
- 수정: 새 공간 등록 전 reset_inspection 호출

### 1-6 등록된 공간 선택 시 이전 작업 그대로 따라감 ✅
- 파일: `safeloop_demo/pages/1_점검시작.py:265-273`
- 수정: 다른 공간 선택 시 reset_inspection 호출

### 2-1 드래프트 학교+공간 단위로 분리 ✅
- 파일: `modules/storage.py` save_draft_shots / load_draft_shots
- 수정: school_code+space_id 기반 드래프트 (현재 학교만)

### 2-4 시연 모드 샘플 로드 expander 펼침 ✅
- 파일: `safeloop_demo/pages/2_AI점검.py:377`
- 수정: `expanded=True` (시연 모드 ON일 때)

### 2-9 보완 사진 재분석 자동화 ✅
- 파일: `safeloop_demo/pages/2_AI점검.py:504-507`
- 수정: 버튼 클릭 시 즉시 stage1·2·3 재실행, ai_run 거치지 않음

### 2-13 "설비 확정 저장" 버튼 무동작 ✅
- 파일: `safeloop_demo/pages/2_AI점검.py:819-820`
- 수정: 버튼 제거 (저장은 매 rerun 자동)

### 3-1 추천 생성 버튼 중복 ✅
- 파일: `safeloop_demo/pages/3_결과저장.py:117-119`
- 수정: 추천 자동 표시, 버튼은 "재생성"으로 변경

### 3-7 결재라인 단일 진입점 ✅
- 파일: `safeloop_demo/pages/3_결과저장.py:267-274`
- 수정: 결과 저장 페이지에선 영구 저장 옵션 추가하거나 "설정에서 변경" 링크만

### 8-1 설정 페이지 06번 누락 ✅
- 파일: `safeloop_demo/pages/8_설정.py`
- 수정: 06 = 디스크 사용량(현재 expander 안), 07 = 세션 관리

### 8-7 세션 초기화 단일화 ✅
- 파일: `safeloop_demo/app.py:148-152` + `safeloop_demo/pages/8_설정.py:250`
- 수정: 설정 페이지에만 두기

### G-1 페이지 라벨 통일 ✅
- 파일: 모든 페이지 hero + section + 사이드바
- 수정: AI 점검("AI 맞춤 점검" → "AI 점검"), 본교 현황("본교 실시간 현황" → "본교 현황"), 결과 저장("결과 저장 · 발송" → "결과 저장") — 사이드바 라벨과 hero 제목 일치

### G-3 empty_state 통일 적용 ✅
- 파일: `safeloop_demo/pages/6_데이터순환.py`, `pages/10_점검이력.py`, `pages/7_교육청수신함.py`
- 수정: 3개 대상 페이지 모두 `empty_state()` 헬퍼 이미 적용 확인 (기존 commit 반영)

### G-5 사이드바에 공간 정보 표시 ✅
- 파일: `modules/ui.py render_sidebar`
- 수정: active_space 있으면 컨텍스트 카드에 표시 (이미 코드 있음 — 동작 확인만)

---

## Phase 3 — 폴리시 (🟢 + 나머지 🟡, 25개)

### 0-3 자동재생 학교 검색 일관성 ✅
- 파일: `safeloop_demo/app.py:121-125`
- 수정: 세션에 선택된 데모 학교 코드를 저장(`_demo_school_code`) 후 재사용 — 매번 동일 학교

### 0-5 시연 모드 OFF + 교육청 모드 중복 진입 ✅
- 파일: `safeloop_demo/app.py:85-88`
- 수정: 사이드바에 같은 메뉴 있으므로 홈의 안내 박스 제거

### 0-6 온보딩 다시 보기 옵션 없음 ✅
- 파일: `safeloop_demo/pages/8_설정.py` (01 운영 모드 섹션 하단)
- 수정: 설정 페이지에 "온보딩 다시 보기" 버튼 추가 (`_onboarding_done=False` 후 홈 이동)

### 1-2 학교명 검색 결과 페이지네이션 ✅
- 파일: `safeloop_demo/pages/1_점검시작.py:67-89`
- 수정: 20개씩 페이지네이션 + 학교명 정렬 + 이전/다음 버튼

### 1-3 자동 입력이 사용자 입력 덮어쓰기 ✅
- 파일: `safeloop_demo/pages/1_점검시작.py:185-199`
- 수정: 사용자가 이미 입력한 값 있으면 "확인하고 덮어쓰기" 2단계 버튼으로 전환

### 1-4 _seen_auth_help 위치 버그 ✅
- 파일: `safeloop_demo/pages/1_점검시작.py:173-182`
- 수정: expander 바깥에서 `_seen_auth_help=True` 설정

### 1-7 "AI 점검으로 이동" 버튼 위치 ✅
- 파일: `safeloop_demo/pages/1_점검시작.py` (hero 바로 아래)
- 수정: 공간·인증 완료 시 상단에 바로가기 카드 + "→ AI 점검으로 바로 이동" 버튼

### 2-3 위저드 토글 발견성 ✅
- 파일: `safeloop_demo/pages/2_AI점검.py:188-195`
- 수정: 라벨을 "클래식 모드(전체 한 번에 보기)" 로 명확화 + 현재 모드 caption 표시

### 2-5 샘플 분배 비대 ✅
- 파일: `safeloop_demo/pages/2_AI점검.py:391-396`
- 수정: 광각 3장만 분배 · 나머지는 무시 + 캡션 안내 추가

### 2-6 카메라 위젯 script 누적 ✅
- 파일: `safeloop_demo/pages/2_AI점검.py:256-275`
- 수정: `_render_shot_card` 에서 `<script>` 제거 → hero 직후 페이지당 1회만 주입

### 2-7 사진 byte 중복 사용자 안내 ✅
- 파일: `safeloop_demo/pages/2_AI점검.py:308-318`
- 수정: 중복 거부된 사진 수를 `st.toast` 로 안내 + 업로더 리셋 처리

### 2-8 cam_ctr 정리 ✅ (검토 B-1 — 이미 적용됨)
- 파일: `modules/session.py:97-100`
- 수정: `reset_inspection` 에서 `cam_ctr_*` 모든 키 카운터 증가 이미 구현

### 2-10 supplement 다음 안내 ✅
- 파일: `safeloop_demo/pages/2_AI점검.py:509-513`
- 수정: 보완 안 했을 때 caption "보완 없이 결과로 가시려면 그대로 다음"

### 2-12 cached_demo 잘못된 활성화 ✅ (검토 D-2)
- 파일: `modules/ai_vision.py` — `samples_hit_cache(images)` 함수 신설
- 수정: 현재 업로드 사진 광각 3장 해시가 실제 캐시 stage1 파일과 정확 매칭될 때만 True · 2_AI점검.py 에서 이 함수로 교체 + "캐시 가능성만 있음" 보조 안내 분기 추가

### 2-14 교차검증 ERROR 표시 ✅
- 파일: `safeloop_demo/pages/2_AI점검.py:720-730`
- 수정: provider 별 에러도 표시

### 2-16 점수 매핑 실패 ✅
- 파일: `safeloop_demo/pages/2_AI점검.py:881-895`
- 수정: 자동 매핑 결과 카운트 표시 + 70% 미만이면 warning + 수동 매핑 expander (미매핑 항목별 표준 설비 selectbox) · 0건이면 에러 차단

### 2-17 시연 모드 OFF 자동 채움 부재 ⏳
- 파일: `safeloop_demo/pages/2_AI점검.py:838-855`
- 수정: 정상 (실 운영에선 자동 채움 의미 없음)
- 🚫 Skip 후보

### 3-3 ZIP 매번 재생성 ✅
- 파일: `safeloop_demo/pages/3_결과저장.py:283-294`
- 수정: 세션에 `_edufine_zip_cache` / `_edufine_letter_cache` 저장 · 세션 ID 변경 시만 재빌드

### 3-4 결재 시뮬 5번 클릭 ✅
- 파일: `safeloop_demo/pages/3_결과저장.py:243-260`
- 수정: "결재 즉시 완료 (시연용)" 빠른 버튼 추가

### 3-5 결재 자동 + 수동 충돌 ✅
- 파일: `safeloop_demo/pages/3_결과저장.py:255-257`
- 수정: 자동 시 체크박스 disabled

### 3-6 발송 안 한 상태 버튼 노출 ✅
- 파일: `safeloop_demo/pages/3_결과저장.py:354-360`
- 수정: edu_app_sent 조건 추가

### 4-1 빈 상태 메시지 부정확 ✅
- 파일: `safeloop_demo/pages/4_본교현황.py:26-46`
- 수정: 메시지 정확화

### 4-2 1개 공간만 있을 때 차트 ✅
- 파일: `safeloop_demo/pages/4_본교현황.py:99-113`
- 수정: 점검 기록이 1건이면 시계열 차트 대신 요약 카드(공간·점수·등급·일시) 표시

### 5-3 고위험군 리스트 컬럼 밖 ✅
- 파일: `safeloop_demo/pages/5_전국대시보드.py:157-170`
- 수정: divider 후 명시적 풀폭 섹션으로

### 5-4 사이드바 안내 이모지 ✅
- 파일: `safeloop_demo/pages/5_전국대시보드.py:184-188`
- 수정: 이모지 제거

### 6-1 Sankey 단순화 ✅
- 파일: `safeloop_demo/pages/6_데이터순환.py:33-65`
- 수정: 13노드 → 9노드 축약 (AI 점검/클라우드/KEIIS/익명화/환원을 의미 단위로 통합)

### 6-2 여정 빈 상태 ✅
- 파일: `safeloop_demo/pages/6_데이터순환.py:77-80`
- 수정: 본교 클라우드 데이터 있을 때 다른 안내

### 6-3 두 페이지 결재 상태 동기화 ✅
- 파일: `safeloop_demo/pages/6_데이터순환.py:82-101`
- 수정: `_approval_demo_stage` + `edufine_approved` 조합으로 ◯/◐/✅ 세밀화 (단계 X/5 표기)

### 7-1 빈 수신함 디자인 ✅
- 파일: `safeloop_demo/pages/7_교육청수신함.py:49-51`
- 수정: empty_state 사용

### 7-3 .review.json 원본 손상 위험 ✅
- 파일: `safeloop_demo/pages/7_교육청수신함.py:135-139`
- 수정: with_suffix 대신 stem + ".review.json" 형태

### 8-2 결재라인 학교 미선택 시 일관성 ✅
- 파일: `safeloop_demo/pages/8_설정.py:63-72`
- 수정: 공간 사전 등록과 동일하게 학교 선택 안내

### 8-3 공간 사전 등록 학교 미선택 시 일관성 ✅
- 파일: `safeloop_demo/pages/8_설정.py:81-83`
- 수정: 결재라인과 동일 패턴

### 8-5 키 저장 버튼 의미 ✅
- 파일: `safeloop_demo/pages/8_설정.py:170-182`
- 수정: 라벨 "연결 확인"으로 변경 (저장은 자동임을 명시)

### 8-6 학교 클라우드 정리 ✅
- 파일: `modules/storage.py` — `cleanup_school_storage(days)` 함수 신설 · `pages/8_설정.py` 06 섹션에 슬라이더 + `confirm_button` UI 추가 · 시스템 디렉터리(`_`) 보호

### 9-1 (없음 — 9_프로젝트소개는 이슈 없음)

### 10-1 점검 이력 03 누락 ✅
- 파일: `safeloop_demo/pages/10_점검이력.py`
- 수정: 섹션 번호 재정렬

### 10-2 다른 공간 비교 의미 약함 ✅
- 파일: `safeloop_demo/pages/10_점검이력.py:101-153`
- 수정: "같은 공간(유형+별칭)을 2회 이상 점검" 조건 만족 시에만 비교 활성화 · 공간 선택 selectbox 선행

### 11-1 정책시뮬 03 누락 ✅
- 파일: `safeloop_demo/pages/11_정책시뮬레이터.py`
- 수정: 섹션 번호 재정렬

### 11-2 면책 문구 중복 ✅
- 파일: `safeloop_demo/pages/11_정책시뮬레이터.py:65-72, 169-173`
- 수정: 한 곳만 유지

### 11-3 가짜 부재율 라벨 ✅
- 파일: `safeloop_demo/pages/11_정책시뮬레이터.py:144-146`
- 수정: "(시연용 가상값)" 라벨 명시

### G-4 모바일 4-컬럼 메트릭 ✅
- 파일: `modules/ui.py` (CSS `@media (max-width: 768px)` · `@media (max-width: 480px)`)
- 수정: `[data-testid="stHorizontalBlock"]` 에 `flex-wrap: wrap` + 컬럼 `min-width:140px` 로 2×2 유도 · 480px 이하는 100% 세로 스택

### G-6 인쇄 시 page_link 숨김으로 페이지 제목 안 보임 ✅
- 파일: `modules/ui.py @media print`
- 수정: `[data-testid="stPageLink"]` 만 숨기고 hero/섹션 요소는 명시적으로 `display:block` 보장

### G-7 confirm_button 키 충돌 ✅
- 파일: `modules/ui.py` — `_page_key_prefix()` 헬퍼 신설
- 수정: 호출 파일명(stem)의 md5 6자리를 key 에 자동 prefix — 여러 페이지에서 같은 `key` 이름 써도 충돌 없음

### D-3 결재 시뮬 5번 클릭 시연 시간 낭비 ⏳
- (3-4와 통합)

---

## 📅 진행 로그

| 날짜 | Phase | 처리 건수 | 커밋 | 비고 |
|---|---|:-:|---|---|
| 2026-04-24 | 0 | — | 9cfad95 | 핸드오프 문서 작성 |
| 2026-04-24 | 1 | 11 | 9cfad95 | 🔴 발표 사고 방지 완료 |
| 2026-04-24 | 2 | 13 | a721475 | 🟡 흐름 모순 critical 완료 (G-1·G-3 🔄) |
| 2026-04-24 | 3 | 21 | bf1ad80 | 🟢 폴리시 1차 (21건 pending) |
| 2026-04-25 | 4 | 23 | (현재) | ✅ 50건 완주 (중요 4 + 편의 14 + 전역 5) |

**누적 진행**: **완료 50건 + Skip 1건 + 통합 1건 = 총 52건** (100% 처리)

## 🏁 최종 현황 — 전 항목 완료

**중요 4건** ✅ — 2-12(cached_demo 정확 매칭), 2-16(점수 매핑 가드), 2-6(script 1회 주입), 6-3(결재 스테이지 동기화)

**편의 14건** ✅ — 0-3, 0-6, 1-2, 1-3, 1-7, 2-3, 2-5, 2-7, 2-8, 3-3, 4-2, 6-1, 8-6, 10-2

**전역 5건** ✅ — G-1(라벨 통일), G-3(empty_state 확산), G-4(모바일 메트릭), G-6(인쇄 hero), G-7(confirm_button prefix)

**Skip 1건** 🚫 — 2-17 (정상 동작, 수정 불필요)

### 검증 결과
- 스모크 테스트: **51건 / 51건 통과** (0 실패)
- 구문 검사: 27 파일 / 0 실패
- Streamlit 서버: HTTP 200 OK (port 8511)

## 🎯 다음 세션 시작 프롬프트

새 Claude 창에 다음 그대로:
```
HANDOFF_FIX50.md 의 ⏳ pending 항목 21개를 이어서 수정해줘.

현재 브랜치: feat/safeloop-demo
최신 커밋: bf1ad80
누적 완료: 29/50 (중요·critical 단계 모두 완료)

원칙:
1. 각 항목마다 해당 파일 읽고 실제 코드 근거 확인 후 수정
2. Phase 단위로 묶어 검증 (51건 스모크) + 커밋
3. 본 문서의 해당 항목 상태를 ✅ 로 표시
4. 시작 전 `git pull origin feat/safeloop-demo` 로 동기화
```

---

## ⚙️ 검증 체크리스트 (Phase 종료마다)

```bash
cd safeloop_demo
PYTHONIOENCODING=utf-8 python tests/smoke_test.py    # 51건 모두 OK
python -m streamlit run app.py --server.port 8501    # HTTP 200
```

## 📝 새 컨텍스트에서 수정 진행 명령

```
HANDOFF_FIX50.md 의 ⏳ pending 항목을 우선순위 순으로 이어서 수정해줘.
원칙:
1. Phase 단위로 모아 검증 + 커밋
2. 각 항목 수정 후 본 문서의 상태를 ✅ 또는 🔄 로 업데이트
3. 50개 모두 끝날 때까지 진행
4. 컨텍스트 부족 감지 시 본 문서 갱신 후 종료
```
