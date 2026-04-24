"""
설정 페이지.

- 학교 프로필 · 결재라인 기본값
- 공간 사전 등록 (일괄)
- 시연 모드 토글
- API 상태 확인
- 세션 초기화
"""
from __future__ import annotations

import uuid

import streamlit as st

from modules.ai_vision import api_key_available, current_provider_label
from modules.ai_providers import ALL_PROVIDERS, providers_status, test_provider_connection
from modules.session import ensure_state, reset_all
from modules.ui import apply_theme, confirm_button, divider, hero, render_sidebar, section

st.set_page_config(page_title="설정 · SafeLoop", page_icon="static/icon-192.png",
                   layout="centered", initial_sidebar_state="expanded")
apply_theme()
ensure_state()
render_sidebar(active_key="settings")

hero("SETTINGS", "설정", "운영 모드 · 결재라인 · 사전 등록 · 시스템 상태")

# ─────────────────────────────────────────
# 모드 토글
# ─────────────────────────────────────────
section("01", "운영 모드")
col_a, col_b = st.columns(2)
with col_a:
    demo = st.toggle("시연 모드 (샘플 사진·자동 채움 허용)",
                     value=st.session_state.get("demo_mode", True))
    st.session_state["demo_mode"] = demo
with col_b:
    role = st.radio(
        "역할",
        ["학교 담당자", "교육청 담당자"],
        horizontal=True,
        index=0 if st.session_state.get("role", "학교") == "학교" else 1,
    )
    st.session_state["role"] = "학교" if role == "학교 담당자" else "교육청"

# 0-6 수정: 온보딩 다시 보기 버튼
st.markdown("---")
oc1, oc2 = st.columns([3, 1])
with oc1:
    st.caption(
        "첫 방문 시 홈에 표시된 3단계 플로우 안내를 다시 보고 싶을 때 사용하세요."
    )
with oc2:
    if st.button("온보딩 다시 보기", key="show_onboarding_again",
                  use_container_width=True):
        st.session_state["_onboarding_done"] = False
        st.toast("홈으로 이동하면 온보딩 안내가 다시 표시됩니다.", icon="ℹ️")
        st.switch_page("app.py")

# ─────────────────────────────────────────
# 공간 사전 등록 (이전 02 결재라인 기본값 섹션은 삭제 —
#   실제 결재는 K에듀파인에서 이뤄지므로 이 앱에서 관리할 필요 없음)
# ─────────────────────────────────────────
divider()
section("02", "공간 사전 등록")
st.caption("첫 점검 전에 학교 내 공간 목록을 미리 등록할 수 있습니다.")

school = st.session_state.get("school")
if not school:
    st.warning("먼저 학교를 선택하세요. (점검 시작 페이지)")
else:
    SPACE_TYPES = [
        "화학실", "물리실", "생명과학실", "지구과학실",
        "기술실", "가정실", "음악실", "미술실",
        "강당", "체육관", "급식실", "일반교실", "특별교실(과목 불명)",
    ]
    col_type, col_nick = st.columns([1, 2])
    with col_type:
        new_type = st.selectbox("공간 유형", SPACE_TYPES)
    with col_nick:
        new_nick = st.text_input("별칭 (선택)", placeholder="예: 3층 화학실 A")

    if st.button("공간 추가"):
        st.session_state.setdefault("registered_spaces", []).append({
            "space_id": uuid.uuid4().hex[:10],
            "school_code": school.get("정보공시 학교코드"),
            "type": new_type,
            "nickname": new_nick.strip() or None,
        })
        st.success("등록 완료")
        st.rerun()

    # 등록된 공간 목록
    spaces = [s for s in st.session_state.get("registered_spaces", [])
              if s.get("school_code") == school.get("정보공시 학교코드")]
    if spaces:
        st.markdown("##### 등록된 공간")
        for idx, sp in enumerate(spaces):
            colA, colB = st.columns([5, 1])
            with colA:
                st.markdown(f"- **{sp['type']}** · {sp.get('nickname') or '별칭 없음'} "
                            f"<span style='color:#888;font-size:11px'>({sp['space_id']})</span>",
                            unsafe_allow_html=True)
            with colB:
                if st.button("삭제", key=f"del_sp_{sp['space_id']}"):
                    st.session_state["registered_spaces"] = [
                        s for s in st.session_state["registered_spaces"]
                        if s["space_id"] != sp["space_id"]
                    ]
                    st.rerun()

# ─────────────────────────────────────────
# AI 공급자 (이전 04 → 03 으로 번호 재정렬)
# ─────────────────────────────────────────
divider()
section("03", "AI 공급자",
        "Claude · Gemini · GPT 중 선택. "
        "프롬프트·파이프라인은 동일하며 호출 대상만 교체됩니다.")

_providers = providers_status()
_avail_map = {p["id"]: p for p in _providers}

# 현재 선택
current_choice = st.session_state.get("ai_provider") or next(
    (p["id"] for p in _providers if p["available"]), "anthropic"
)

options = [p["id"] for p in _providers]

def _fmt(pid: str) -> str:
    p = _avail_map[pid]
    mark = "✓ 사용 가능" if p["available"] else "✗ 키 필요"
    src = f" · {p['key_source']}" if p.get("key_source") else ""
    return f"{p['label']}  —  {mark}{src}"

sel = st.radio(
    "공급자 선택",
    options=options,
    index=options.index(current_choice) if current_choice in options else 0,
    format_func=_fmt,
)
st.session_state["ai_provider"] = sel

# 선택된 공급자의 키 입력
selected = _avail_map[sel]
key_field = f"api_key_{sel}"
existing = st.session_state.get(key_field, "")
placeholder = "환경변수에서 자동 감지됨" if selected["key_source"] == "환경변수" and not existing \
    else "sk-..."
new_key = st.text_input(
    f"{selected['label']} API 키",
    value=existing,
    placeholder=placeholder,
    type="password",
    help=f"환경변수 {selected['env_var']} 로도 설정 가능",
)
if new_key != existing:
    st.session_state[key_field] = new_key.strip()

st.caption("키는 입력 즉시 세션에 저장됩니다. 아래 버튼은 공급자에 실제 ping 호출로 연결 확인만 합니다.")
if st.button("연결 확인 (ping)"):
    if not api_key_available():
        st.error("이 공급자의 API 키가 감지되지 않습니다.")
    else:
        with st.spinner(f"{selected['label']} 에 ping 호출 중…"):
            ok, msg = test_provider_connection(sel)
        if ok:
            st.success(f"✅ {selected['label']} — {msg}")
        else:
            st.error(f"❌ {selected['label']} — {msg}")

# 전체 공급자 상태 요약
st.markdown("##### 전체 공급자 상태")
for p in _providers:
    status = "✅ 사용 가능" if p["available"] else "⚪ 키 없음"
    src = f" · {p['key_source']}" if p.get("key_source") else ""
    st.markdown(f"- **{p['label']}** — {status}{src}")

st.markdown("##### 추가 옵션")
multi_avail = sum(1 for p in _providers if p["available"]) >= 2
# 사용 불가 상태면 세션 값 강제 정리 (잔존 방지)
if not multi_avail and st.session_state.get("cross_check"):
    st.session_state["cross_check"] = False
cross = st.toggle(
    "단계 1 교차 검증 (Claude × GPT 합의)",
    value=st.session_state.get("cross_check", False),
    disabled=not multi_avail,
    help="두 공급자가 모두 가능한 경우에만 동작. 비용·속도는 2배.",
)
# 토글 disabled여도 사용자가 cross 변수에 입력은 못 하지만, 안전 차 추가 가드
st.session_state["cross_check"] = bool(cross) and multi_avail
img_check = st.toggle(
    "이미지 품질 사전 검사 (블러·어두움 · 자동 회전·리사이즈)",
    value=st.session_state.get("image_quality_check", True),
    help="흐리거나 어두운 사진을 AI에 보내기 전에 차단합니다.",
)
st.session_state["image_quality_check"] = img_check

divider()
section("04", "AI 시스템 상태")
if api_key_available():
    st.success(f"AI 파이프라인 사용 가능 — 현재 공급자: {current_provider_label()}")
else:
    st.error("현재 선택된 공급자의 API 키가 없습니다. 위 섹션에서 키를 입력하세요.")

# ─────────────────────────────────────────
# 데이터 저장·처리 원칙 (보안·컴플라이언스 안내)
# ─────────────────────────────────────────
divider()
section("05", "데이터 저장 원칙 (시연 vs 운영)",
        "학교 안전 점검 로우데이터는 학교 내부 결재가 선행되어야 하는 자료입니다.")
st.markdown(
    "<div style='border:1px solid #F8D0D0;background:#FFF6F6;"
    "border-radius:6px;padding:14px 18px;font-size:13px;color:#0A0A0B;line-height:1.75;'>"
    "<b style='color:#D50000;'>⚠ 중요</b> — 현재 이 앱은 "
    "<b>Streamlit Community Cloud</b> 데모 컨테이너에서 실행 중일 수 있습니다. "
    "이 환경의 파일 시스템(`school_storage/`)은 <b>임시 저장소</b>이며, "
    "컨테이너 재시작 시 초기화됩니다. 외부 인가 없이 영구 저장되지 않습니다.<br><br>"
    "<b>⚙ 실 운영 시에는 반드시 다음 중 하나로 전환하세요:</b><br>"
    "① <b>학교 내부망 온프렘 배포</b> — 학교 서버·NAS 에 Streamlit 컨테이너 설치<br>"
    "② <b>브라우저 세션 전용 모드</b> — 하단 옵션으로 디스크 저장 비활성화<br>"
    "③ <b>교육청 내부 클라우드</b> — 교육청 인증 게이트웨이 통한 격리된 테넌트<br><br>"
    "<b>현재 시연 모드</b>에서는 결과 저장 시 파일이 임시로 생성되지만, "
    "앱 밖으로 반출되려면 반드시 사용자가 <b>다운로드 버튼</b>으로 직접 내려받아야 합니다. "
    "수동 다운로드 없이는 외부로 전송되지 않습니다."
    "</div>",
    unsafe_allow_html=True,
)

_session_only = st.toggle(
    "📁 **세션 전용 모드** — 디스크에 저장하지 않고 브라우저 메모리에만 유지",
    value=st.session_state.get("_session_only_mode", False),
    help="ON: 점검 이력이 디스크에 쓰이지 않음 (새로고침·재시작 시 소멸). "
         "다운로드로만 이력 보관 가능. 개인정보·보안이 우려될 때 권장."
)
st.session_state["_session_only_mode"] = _session_only
if _session_only:
    st.info(
        "세션 전용 모드 ON — 결과 저장 버튼을 눌러도 디스크에 기록되지 않습니다. "
        "반드시 **다운로드 버튼**으로 결과물을 내려받아 학교 내부 결재에 첨부하세요."
    )

# ─────────────────────────────────────────
# 디스크 사용량 (관리자 도구)
# ─────────────────────────────────────────
divider()
section("06", "디스크 사용량 · 캐시 정리",
        "로컬/자체 호스팅 환경에서만 의미 있음. Streamlit Cloud는 재시작 시 초기화.")
with st.expander("관리자 도구 열기", expanded=False):
    st.caption(
        "이 정보는 **현재 Streamlit 서버가 실행 중인 호스트의 로컬 파일 시스템** 기준입니다. "
        "Streamlit Cloud 환경에선 컨테이너 재시작마다 초기화되므로 관리 의미는 제한적이며, "
        "주로 **로컬 개발·자체 호스팅 운영** 시 캐시 누적 점검용입니다."
    )

    from modules.storage import storage_usage, cleanup_old_cache
    usage = storage_usage()
    def _fmt(b: int) -> str:
        if b < 1024:
            return f"{b}B"
        if b < 1024 * 1024:
            return f"{b/1024:.1f}KB"
        return f"{b/1024/1024:.2f}MB"

    uc1, uc2, uc3 = st.columns(3)
    uc1.metric("학교 클라우드", _fmt(usage["school_storage"]))
    uc2.metric("AI 캐시", _fmt(usage["ai_cache"]))
    uc3.metric("교육청 수신함", _fmt(usage["edu_receipt"]))

    cdays = st.slider("캐시 보존 기간(일)", 7, 90, 30, step=1)
    if st.button(f"{cdays}일 이전 AI 캐시 정리"):
        n, freed = cleanup_old_cache(days=cdays)
        if n:
            st.success(f"{n}개 파일 삭제 · {_fmt(freed)} 회수")
        else:
            st.info("정리할 파일이 없습니다.")
        st.rerun()

    # 8-6 수정: 학교 클라우드 정리 (위험 경고 + confirm_button)
    st.markdown("---")
    st.markdown(
        "<div style='border:1px solid #F8D0D0;background:#FFF6F6;"
        "border-radius:6px;padding:10px 14px;font-size:12px;color:#D50000;'>"
        "⚠ <b>학교 클라우드 정리</b>는 실제 점검 이력 폴더를 통째로 삭제합니다. "
        "복구 불가 — 신중히 사용하세요. (`_ai_cache`, `_drafts` 등 시스템 폴더는 보호됩니다.)"
        "</div>",
        unsafe_allow_html=True,
    )
    sdays = st.slider("학교 클라우드 보존 기간(일)", 30, 365, 90, step=10,
                       key="school_storage_days")
    from modules.storage import cleanup_school_storage
    if confirm_button(
        f"{sdays}일 이전 학교 클라우드 점검 이력 삭제",
        key="cleanup_school_storage",
        message=f"⚠ {sdays}일 이상 지난 모든 학교의 점검 세션 폴더를 삭제합니다. "
                f"이 작업은 되돌릴 수 없습니다.",
    ):
        n_s, freed_s = cleanup_school_storage(days=sdays)
        if n_s:
            st.success(f"세션 폴더 {n_s}개 삭제 · {_fmt(freed_s)} 회수")
        else:
            st.info("정리할 세션 폴더가 없습니다.")
        st.rerun()

divider()
section("07", "세션 관리", "모든 세션 데이터(학교 선택·공간·촬영·AI 결과 등)를 초기화합니다.")
if confirm_button("전체 세션 초기화", key="reset_all_settings",
                   message="학교 선택·공간·촬영본·AI 결과 등 모든 세션 데이터 삭제."):
    reset_all()
    st.success("초기화 완료")
    st.rerun()
