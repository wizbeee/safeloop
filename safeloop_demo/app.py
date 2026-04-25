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
    <div style="text-align:center; padding: 60px 0 28px 0;">
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
# 진입점 선택 — 학교 담당자 / 교육청 담당자 (명확한 카드 분기)
# ─────────────────────────────────────────
current_role = st.session_state.get("role", "학교")

st.markdown(
    "<div style='text-align:center;font-size:12px;letter-spacing:0.28em;"
    "color:#6B6B70;font-weight:600;margin-bottom:14px;'>역할을 선택하세요</div>",
    unsafe_allow_html=True,
)

role_col_a, role_col_b = st.columns(2, gap="medium")

with role_col_a:
    is_school = current_role == "학교"
    border = "3px solid #D50000" if is_school else "1px solid #E5E5E8"
    bg = "#FFFFFF" if is_school else "#FAFAFA"
    st.markdown(
        f"<div style='border-left:{border};border-top:1px solid #E5E5E8;"
        f"border-right:1px solid #E5E5E8;border-bottom:1px solid #E5E5E8;"
        f"background:{bg};border-radius:6px;padding:22px 22px 14px 22px;"
        f"min-height:150px;'>"
        f"<div style='font-size:11px;letter-spacing:0.28em;color:#D50000;"
        f"font-weight:700;margin-bottom:8px;'>SCHOOL</div>"
        f"<div style='font-size:18px;font-weight:700;color:#0A0A0B;margin-bottom:6px;'>"
        f"학교 담당자</div>"
        f"<div style='font-size:13px;color:#6B6B70;line-height:1.6;'>"
        f"학교 식별·인증 후 AI 점검 → 에듀파인 결재용 패키지 생성 → 교육청 전송"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    if st.button("학교 담당자로 시작", key="enter_school",
                  type=("primary" if is_school else "secondary"),
                  use_container_width=True):
        # 교육청 모드에서 오거나 역할 스위치 시 학교 세션 유지 (학교 담당자 흐름)
        st.session_state["role"] = "학교"
        st.rerun()

with role_col_b:
    is_edu = current_role == "교육청"
    border = "3px solid #D50000" if is_edu else "1px solid #E5E5E8"
    bg = "#FFFFFF" if is_edu else "#FAFAFA"
    st.markdown(
        f"<div style='border-left:{border};border-top:1px solid #E5E5E8;"
        f"border-right:1px solid #E5E5E8;border-bottom:1px solid #E5E5E8;"
        f"background:{bg};border-radius:6px;padding:22px 22px 14px 22px;"
        f"min-height:150px;'>"
        f"<div style='font-size:11px;letter-spacing:0.28em;color:#D50000;"
        f"font-weight:700;margin-bottom:8px;'>EDU OFFICE</div>"
        f"<div style='font-size:18px;font-weight:700;color:#0A0A0B;margin-bottom:6px;'>"
        f"교육청 담당자</div>"
        f"<div style='font-size:13px;color:#6B6B70;line-height:1.6;'>"
        f"학교 제출본 수신·검증 → KEIIS 이관 → 전국 대시보드·정책 시뮬레이터 활용"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    if st.button("교육청 담당자로 시작", key="enter_edu",
                  type=("primary" if is_edu else "secondary"),
                  use_container_width=True):
        # 교육청 진입 시 학교 세션 자동 정리 (교육청 담당자는 특정 학교 소속이 아님)
        if st.session_state.get("role") != "교육청" \
                or st.session_state.get("school") or st.session_state.get("active_space"):
            from modules.session import reset_inspection
            reset_inspection()
            st.session_state["school"] = None
            st.session_state["auth_verified"] = False
        st.session_state["role"] = "교육청"
        st.toast("교육청 담당자 모드 — 학교 선택 세션이 정리되었습니다.", icon="🏛")
        st.rerun()

# 역할별 빠른 이동
st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
col_l, col_c, col_r = st.columns([1, 2, 1])
with col_c:
    if current_role == "교육청":
        if st.button("교육청 수신함 열기", type="primary",
                      use_container_width=True, key="go_inbox"):
            st.switch_page("pages/7_교육청수신함.py")
        st.markdown(
            "<div style='text-align:center; margin-top:8px; font-size:12px; color:#9A9A9F;'>"
            "수신·검증 → KEIIS 이관 · 약 2분 소요"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        if st.button("점검하러 가기", type="primary", use_container_width=True, key="go_inspect"):
            st.switch_page("pages/1_점검시작.py")
        st.markdown(
            "<div style='text-align:center; margin-top:8px; font-size:12px; color:#9A9A9F;'>"
            "모바일·태블릿 권장 · 약 3분 소요"
            "</div>",
            unsafe_allow_html=True,
        )

# ─────────────────────────────────────────
# 운영 모드
# ─────────────────────────────────────────
st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
divider()

demo = st.toggle(
    "시연 모드 (샘플 사진·자동 채움 허용)",
    value=st.session_state.get("demo_mode", True),
    help="샘플 사진·자동 값 채우기를 허용합니다. 실 운영에선 꺼두세요.",
)
st.session_state["demo_mode"] = demo

# ─────────────────────────────────────────
# 튜토리얼 다이얼로그 (플로팅 버튼에서 호출)
# ─────────────────────────────────────────
def _render_tutorial_content() -> None:
    st.markdown(
        "<div style='font-size:12px;letter-spacing:0.28em;color:#D50000;"
        "font-weight:700;margin-bottom:6px;'>3단계로 끝납니다</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "**1단계 · 학교 찾기 + 인증**  \n"
        "GPS · 학교명 · 지역 단계 검색 중 편한 방식으로 학교를 찾고, "
        "담당자 인증번호(6자리)를 입력합니다.\n\n"
        "**2단계 · AI 점검**  \n"
        "정면·우측·좌측 **광각 3장** 만 촬영하면 AI가 공간 유형과 안전설비를 자동 식별하여 "
        "맞춤 점검표를 생성합니다. 놓친 항목은 '보완 촬영' 으로 추가하세요.\n\n"
        "**3단계 · 저장 + 발송**  \n"
        "결과는 Human용(읽기 좋은 PDF/Excel) 과 Machine용(구조화 JSON) 으로 이중 저장됩니다. "
        "에듀파인 결재 후 교육청 수신함으로 즉시 전송할 수 있습니다."
    )
    st.markdown("---")
    st.caption(
        "💡 **팁** — 홈의 '시연 자동 재생' 버튼을 누르면 데모 학교·공간이 자동 세팅되고 "
        "AI 점검 화면까지 바로 이동합니다. 발표·리뷰 시 유용합니다."
    )


# Streamlit 1.32+ 의 @st.dialog 사용, 없으면 expander 폴백
try:
    _dialog_decorator = st.dialog("SafeLoop 사용 가이드")

    @_dialog_decorator
    def _show_tutorial_dialog():
        _render_tutorial_content()

    _use_dialog = True
except Exception:
    _use_dialog = False

# 플로팅 스타일 튜토리얼 트리거 (우상단 고정)
st.markdown(
    """
    <style>
    .sl-tutorial-floater {
        position: fixed; top: 70px; right: 24px; z-index: 9998;
        background: #FFFFFF; border: 1px solid #E5E5E8;
        border-radius: 999px; padding: 6px 14px 6px 10px;
        box-shadow: 0 4px 14px rgba(10,10,11,0.08);
        font-size: 12px; color: #6B6B70; font-weight: 500;
        letter-spacing: -0.01em;
    }
    .sl-tutorial-floater b { color: #D50000; font-size: 14px; margin-right: 4px; }
    @media (max-width: 768px) {
        .sl-tutorial-floater { top: 64px; right: 12px; padding: 5px 10px; }
    }
    </style>
    <div class="sl-tutorial-floater">
        <b>?</b>처음이신가요 ↓ 튜토리얼 보기
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────
# 튜토리얼 + 데모 자동 재생 (2컬럼)
# ─────────────────────────────────────────
divider()
oc1, oc2 = st.columns(2)

with oc1:
    st.markdown("**🎓 튜토리얼**")
    st.caption("3단계 플로우를 30초 안에 이해합니다. 언제든 다시 볼 수 있습니다.")
    if st.button("튜토리얼 열기", key="open_tutorial", use_container_width=True):
        # dialog 호출 실패 시 인라인 expander 로 폴백 (안전망)
        _tut_ok = False
        if _use_dialog:
            try:
                _show_tutorial_dialog()
                _tut_ok = True
            except Exception:
                _tut_ok = False
        if not _tut_ok:
            st.session_state["_tutorial_inline"] = True
            st.rerun()
    # 폴백: 인라인 expander (구버전 Streamlit 또는 dialog 실패)
    if st.session_state.get("_tutorial_inline"):
        with st.expander("SafeLoop 사용 가이드", expanded=True):
            _render_tutorial_content()
            if st.button("닫기", key="close_tutorial_inline"):
                st.session_state["_tutorial_inline"] = False
                st.rerun()

with oc2:
    st.markdown("**🎬 시연 자동 재생**")
    st.caption("심사·발표용 — 공간 선택 후 학교·공간·샘플 7장 자동 로드")

    # 공간 유형 토글 — 화학실 / 일반교실 / 미술실
    DEMO_SPACES = {
        "화학실": "chemistry_lab",
        "일반교실": "classroom",
        "미술실": "art_lab",
    }
    autoplay_space = st.radio(
        "데모 공간",
        options=list(DEMO_SPACES.keys()),
        horizontal=True,
        key="autoplay_space_choice",
    )

    has_existing = bool(st.session_state.get("school")) or bool(st.session_state.get("active_space"))
    if has_existing:
        st.markdown(
            "<div style='background:#FFF2F2; border:1px solid #F8D0D0; "
            "border-radius:6px; padding:8px 12px; font-size:12px; color:#D50000;'>"
            "⚠ 기존 선택된 학교·공간·진행 중 작업이 모두 초기화됩니다."
            "</div>",
            unsafe_allow_html=True,
        )
    # 원클릭 자동재생 — 2단계 확인 없이 즉시 실행 (발표 시 빠르게)
    if st.button(f"▶ 자동 재생 시작 ({autoplay_space})", key="autoplay_btn",
                  type="primary", use_container_width=True):
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

        # 0-3 수정: 자동재생 학교를 결정적으로 선택
        # 1) 세션에 이미 사용된 데모 학교 코드가 있으면 그걸 재사용
        # 2) 없으면 "중학교" 검색 → 학교명 정렬 → 첫 결과 → 세션에 저장
        demo_school = None
        cached_code = st.session_state.get("_demo_school_code")
        if cached_code:
            demo_school = get_school_by_code(cached_code)
        if not demo_school:
            df = search_schools_by_name("중학교", limit=50)
            if not df.empty:
                df = df.sort_values("학교명").reset_index(drop=True)
                picked_code = df.iloc[0]["정보공시 학교코드"]
                demo_school = get_school_by_code(picked_code)
                if demo_school:
                    st.session_state["_demo_school_code"] = picked_code

        if not demo_school:
            st.error("데모 학교 데이터를 찾을 수 없습니다.")
        else:
            st.session_state["school"] = demo_school
            st.session_state["auth_verified"] = True

            # 0-2: 동일 데모 공간 재사용 (누적 방지)
            school_code = demo_school.get("정보공시 학교코드")
            demo_space_type = autoplay_space  # "화학실" / "일반교실" / "미술실"
            existing_demo = next(
                (sp for sp in st.session_state.get("registered_spaces", [])
                 if sp.get("school_code") == school_code
                 and sp.get("type") == demo_space_type
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
                    "type": demo_space_type,
                    "nickname": "데모 · 3층 A",
                }
                st.session_state.setdefault("registered_spaces", []).append(demo_space)
            st.session_state["active_space"] = demo_space

            # 🎬 시연 자동 재생 실제화 — 새 7컷 구조에 샘플 분배 + AI 자동실행
            sample_folder = DEMO_SPACES.get(autoplay_space, "chemistry_lab")
            sample_root = Path(__file__).resolve().parent / "sample_images" / sample_folder
            # 7컷 기본 키 (close_supplement·back_door_diag 는 선택)
            SHOT_KEYS = [
                "entrance_diag", "front_view", "center_window", "center_corridor",
                "center_front_door", "center_back_door", "ceiling",
            ]
            shots = {k: [] for k in SHOT_KEYS + ["back_door_diag", "close_supplement"]}

            # 폴더에 7장 이상 있으면 그대로, 부족하면 화학실 폴백 후 그것도 부족하면 가용한 만큼만 분배
            available_paths: list[Path] = []
            if sample_root.exists():
                available_paths = sorted(sample_root.glob("*.jpg"))
            if len(available_paths) < 3:
                # 폴백: chemistry_lab 으로 (현재 가장 많은 샘플 보유)
                fallback = Path(__file__).resolve().parent / "sample_images" / "chemistry_lab"
                if fallback.exists():
                    available_paths = sorted(fallback.glob("*.jpg"))

            # 7컷에 가용 사진을 균등 분배 (사진이 부족하면 일부 컷은 비어 있음)
            if available_paths:
                for i, key in enumerate(SHOT_KEYS):
                    if i < len(available_paths):
                        p = available_paths[i]
                        shots[key].append({
                            "name": p.name,
                            "bytes": p.read_bytes(),
                            "source": "sample",
                        })
                st.session_state["shots"] = shots
                # 이전 AI 결과 클리어 (다시 분석하도록)
                for _k in ["stage1_result", "stage2_result", "stage2_confirmed",
                           "stage3_result", "item_scores", "score_result",
                           "recommendations"]:
                    st.session_state[_k] = None

            st.session_state["_autoplay"] = True
            # 2_AI점검 페이지가 이 플래그를 감지해 캐시 폴백 가능 시 즉시 분석 실행
            st.session_state["_autoplay_run_ai"] = True
            st.toast(f"데모: {autoplay_space} 7컷 세팅 완료 → AI 점검 이동", icon="🎬")
            st.switch_page("pages/2_AI점검.py")

# 8-7: 세션 초기화는 설정 페이지에만 두기 (사이드바 중복 제거)
