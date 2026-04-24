"""
SafeLoop — 홈 엔트리 포인트.

공공데이터로 시작해, 공공데이터로 돌아옵니다.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from modules.session import ensure_state, reset_all
from modules.ui import apply_theme, confirm_button, divider, render_sidebar

load_dotenv(Path(__file__).parent / ".env")

st.set_page_config(
    page_title="SafeLoop",
    page_icon="static/icon-192.png",
    layout="centered",
    initial_sidebar_state="collapsed",
)

apply_theme()
ensure_state()
render_sidebar(active_key="home")

# ─────────────────────────────────────────
# 히어로
# ─────────────────────────────────────────
st.markdown(
    """
    <div style="text-align:center; padding: 80px 0 40px 0;">
      <div style="font-size:11px; letter-spacing:0.4em; font-weight:600; color:#D50000; margin-bottom:14px; text-transform:uppercase;">SAFELOOP</div>
      <div style="font-size:42px; font-weight:800; color:#0A0A0B; letter-spacing:-0.03em; line-height:1.1; margin-bottom:14px;">
        학교 안전, 지금 바로 점검
      </div>
      <div style="font-size:15px; color:#6B6B70; letter-spacing:-0.01em;">
        공공데이터로 시작해, 공공데이터로 돌아옵니다.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────
# 중앙 CTA
# ─────────────────────────────────────────
col_l, col_c, col_r = st.columns([1, 2, 1])
with col_c:
    if st.button("점검하러 가기", type="primary", use_container_width=True, key="go_inspect"):
        st.switch_page("pages/1_점검시작.py")
    st.markdown(
        "<div style='text-align:center; margin-top:8px; font-size:12px; color:#9A9A9F;'>"
        "모바일·태블릿 권장 · 약 3분 소요"
        "</div>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────
# 운영 모드 / 역할
# ─────────────────────────────────────────
st.markdown("<div style='height:56px'></div>", unsafe_allow_html=True)
divider()

mode_c1, mode_c2 = st.columns(2)
with mode_c1:
    demo = st.toggle(
        "시연 모드",
        value=st.session_state.get("demo_mode", True),
        help="샘플 사진·자동 값 채우기를 허용합니다. 실 운영에선 꺼두세요.",
    )
    st.session_state["demo_mode"] = demo
with mode_c2:
    role = st.radio(
        "역할",
        options=["학교 담당자", "교육청 담당자"],
        index=0 if st.session_state.get("role", "학교") == "학교" else 1,
        horizontal=True,
        label_visibility="collapsed",
    )
    st.session_state["role"] = "학교" if role == "학교 담당자" else "교육청"

if st.session_state["role"] == "교육청":
    st.info("교육청 담당자 모드입니다. 아래 버튼으로 수신함을 여세요.")
    if st.button("교육청 수신함 열기", use_container_width=True):
        st.switch_page("pages/7_교육청수신함.py")

# ─────────────────────────────────────────
# 첫 방문 온보딩 + 데모 자동재생 (간이)
# ─────────────────────────────────────────
divider()
oc1, oc2 = st.columns(2)

with oc1:
    if not st.session_state.get("_onboarding_done"):
        with st.expander("ⓘ 처음 사용하시나요? (3단계 안내)", expanded=True):
            st.markdown(
                "**1단계 · 학교 찾기 + 인증** — GPS · 학교명 · 지역 단계 검색 중 편한 방식\n\n"
                "**2단계 · AI 점검** — 정면·우측·좌측 3장 촬영 후 AI 자동 분석 → 점검표 입력\n\n"
                "**3단계 · 저장 + 발송** — Human/Machine 이중 저장, 에듀파인 결재 후 교육청 전송"
            )
            if st.button("이해했습니다 (다시 보지 않기)", key="dismiss_onboarding"):
                st.session_state["_onboarding_done"] = True
                st.rerun()
    else:
        st.caption("✓ 온보딩 완료")

with oc2:
    st.markdown("**시연 자동 재생**")
    st.caption("심사·발표용 — 데모 학교·인증 자동 통과 + 화학실 샘플 등록")
    has_existing = bool(st.session_state.get("school")) or bool(st.session_state.get("active_space"))
    if has_existing:
        st.markdown(
            "<div style='background:#FFF2F2; border:1px solid #F8D0D0; "
            "border-radius:6px; padding:8px 12px; font-size:12px; color:#D50000;'>"
            "기존 선택된 학교·공간·진행 중 작업이 모두 초기화됩니다."
            "</div>",
            unsafe_allow_html=True,
        )
    if confirm_button(
        "자동 재생 시작",
        key="autoplay",
        message="현재 선택된 학교·공간·촬영본·AI 결과가 모두 초기화되고 데모 학교로 전환됩니다."
        if has_existing else "데모 학교로 즉시 전환합니다.",
        use_container_width=True,
    ):
        from modules.data_loader import search_schools_by_name, get_school_by_code
        from modules.session import reset_inspection
        from modules.storage import clear_draft

        # 0-4: 이전 세션·드래프트 모두 정리
        old_school = st.session_state.get("school") or {}
        old_code = old_school.get("정보공시 학교코드")
        if old_code:
            try:
                clear_draft(old_code)
            except Exception:
                pass
        reset_inspection()
        st.session_state["demo_mode"] = True

        # 데모 학교 — 결정적 선택 (정렬된 첫 결과)
        demo_school = None
        df = search_schools_by_name("중학교", limit=50)
        if not df.empty:
            df = df.sort_values("학교명").reset_index(drop=True)
            demo_school = get_school_by_code(df.iloc[0]["정보공시 학교코드"])

        if not demo_school:
            st.error("데모 학교 데이터를 찾을 수 없습니다.")
        else:
            st.session_state["school"] = demo_school
            st.session_state["auth_verified"] = True

            # 0-2: 동일 데모 공간 재사용 (누적 방지)
            school_code = demo_school.get("정보공시 학교코드")
            existing_demo = next(
                (sp for sp in st.session_state.get("registered_spaces", [])
                 if sp.get("school_code") == school_code
                 and sp.get("type") == "화학실"
                 and sp.get("nickname") == "데모 · 3층 A"),
                None,
            )
            if existing_demo:
                demo_space = existing_demo
            else:
                import uuid
                demo_space = {
                    "space_id": uuid.uuid4().hex[:10],
                    "school_code": school_code,
                    "type": "화학실",
                    "nickname": "데모 · 3층 A",
                }
                st.session_state.setdefault("registered_spaces", []).append(demo_space)
            st.session_state["active_space"] = demo_space
            st.session_state["_autoplay"] = True
            st.toast(f"데모 학교: {demo_school.get('학교명')}")
            st.switch_page("pages/2_AI점검.py")

# 8-7: 세션 초기화는 설정 페이지에만 두기 (사이드바 중복 제거)
