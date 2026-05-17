"""
SafeLoop — 홈 엔트리 포인트.

공공데이터로 시작해, 공공데이터로 돌아옵니다.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from modules.auth import is_authenticated, render_pin_gate
from modules.session import ensure_state
from modules.ui import apply_theme, divider, render_sidebar

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
# 자동 로그인 — 홈 진입 시 한 번만 쿠키 검사 (다른 페이지에선 호출 X 깜빡임 방지)
#
# 의도적 설계: cookie_manager 가 매 호출 시 IFrame 을 로드하므로 모든 페이지
# 에서 호출하면 사이드바·콘텐츠가 깜빡인다. 따라서 홈 진입 시 1회만 검사하고
# 결과를 세션에 저장. 사용자가 보호 페이지(예: /교육청수신함)에 URL 직접 진입
# 시에는 자동 로그인 안 되고 PIN 입력 요구 — 이는 보안과 UX의 트레이드오프
# 끝에 선택된 방향. 변경 시 사이드바 깜빡임 회귀 위험 있음.
# ─────────────────────────────────────────
if not st.session_state.get("_auto_login_checked"):
    # 교육청 자동 로그인 시도 (쿠키 세션)
    is_authenticated("edu")
    st.session_state["_auto_login_checked"] = True

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
# 진입점 선택 — 실 담당자 / 학교 담당자 / 교육청 담당자 (3 카드 분기)
#
# 실 담당자: 화학실·물리실·디자인실 등 공간 담당 교사. 본인 담당 공간만 점검·제출.
# 학교 담당자: 우리 학교 실 담당자 제출분 수합·검토·발송. 본인이 점검할 수도 있음.
# 교육청 담당자: 학교 제출본 수신·검증·전국 대시보드.
# ─────────────────────────────────────────
current_role = st.session_state.get("role", "학교")

st.markdown(
    "<div style='text-align:center;font-size:12px;letter-spacing:0.28em;"
    "color:#6B6B70;font-weight:600;margin-bottom:14px;'>역할을 선택하세요</div>",
    unsafe_allow_html=True,
)


def _role_card_html(label_en: str, label_kr: str, desc: str, active: bool) -> str:
    border = "3px solid #D50000" if active else "1px solid #E5E5E8"
    bg = "#FFFFFF" if active else "#FAFAFA"
    return (
        f"<div style='border-left:{border};border-top:1px solid #E5E5E8;"
        f"border-right:1px solid #E5E5E8;border-bottom:1px solid #E5E5E8;"
        f"background:{bg};border-radius:6px;padding:22px 18px 14px 18px;"
        f"min-height:170px;'>"
        f"<div style='font-size:11px;letter-spacing:0.28em;color:#D50000;"
        f"font-weight:700;margin-bottom:8px;'>{label_en}</div>"
        f"<div style='font-size:17px;font-weight:700;color:#0A0A0B;margin-bottom:6px;'>"
        f"{label_kr}</div>"
        f"<div style='font-size:12.5px;color:#6B6B70;line-height:1.55;'>{desc}</div>"
        f"</div>"
    )


role_col_a, role_col_b, role_col_c = st.columns(3, gap="medium")

# 실 담당자 카드 — 흐름의 첫 단계 (가장 많이 사용)
with role_col_a:
    is_space = current_role == "실"
    st.markdown(
        _role_card_html(
            "SPACE",
            "실 담당자",
            "본인 담당 공간(화학실·물리실·디자인실 등) AI 점검 학교 담당자에게 제출",
            is_space,
        ),
        unsafe_allow_html=True,
    )
    if st.button("실 담당자로 시작", key="enter_space",
                  type=("primary" if is_space else "secondary"),
                  width="stretch"):
        st.session_state["role"] = "실"
        st.session_state["_show_pin_edu"] = False
        # 매니저 인증은 별도 PIN 으로 다시 받아야 함 (space_manager 정리).
        # 학교 인증번호(school_auth_verified)는 보존 — 같은 학교를 역할 토글하며
        # 사용할 때 매번 학교 인증번호 재입력하는 마찰 제거.
        st.session_state["space_manager"] = None
        st.rerun()

# 학교 담당자 카드
with role_col_b:
    is_school = current_role == "학교"
    st.markdown(
        _role_card_html(
            "SCHOOL",
            "학교 담당자",
            "실 담당자 제출 수합·검토 + 본인 점검 가능 교육청 발송 (이메일)",
            is_school,
        ),
        unsafe_allow_html=True,
    )
    if st.button("학교 담당자로 시작", key="enter_school",
                  type=("primary" if is_school else "secondary"),
                  width="stretch"):
        st.session_state["role"] = "학교"
        st.session_state["_show_pin_edu"] = False
        # 학교 담당자 모드는 실 담당자 세션을 비움
        st.session_state["space_manager"] = None
        st.rerun()

# 교육청 담당자 카드
with role_col_c:
    is_edu = current_role == "교육청"
    st.markdown(
        _role_card_html(
            "EDU OFFICE",
            "교육청 담당자",
            "학교 제출본 수신·검증 전국 대시보드·정책 시뮬레이터",
            is_edu,
        ),
        unsafe_allow_html=True,
    )
    if st.button("교육청 담당자로 시작", key="enter_edu",
                  type=("primary" if is_edu else "secondary"),
                  width="stretch"):
        st.session_state["role"] = "교육청"
        st.session_state["space_manager"] = None
        if is_authenticated("edu"):
            from modules.session import reset_inspection
            reset_inspection()
            st.session_state["school"] = None
            st.session_state["school_auth_verified"] = False
            st.switch_page("pages/7_교육청수신함.py")
        else:
            st.session_state["_show_pin_edu"] = True
            st.rerun()

# ─────────────────────────────────────────
# 교육청 PIN 입력 박스 (카드에서 호출 시 표시)
# - role 이 "학교" 면 PIN 박스 안 띄움 (학교 담당자 모드에서는 교육청 인증 불필요)
# - 사용자가 학교 카드 클릭 시 role="학교" 로 자동 설정되므로,
# 다른 페이지 갔다 돌아와도 PIN 박스가 잔존하지 않음
# ─────────────────────────────────────────
if (st.session_state.get("_show_pin_edu")
        and st.session_state.get("role", "학교") != "학교"
        and not is_authenticated("edu")):
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    render_pin_gate(
        "edu",
        on_success_redirect="pages/7_교육청수신함.py",
        cancel_label="닫기",
        cancel_redirect=None,
    )

# 역할별 빠른 이동 — 시작 카드를 클릭하지 않은 사용자도 한 번에 이동 가능
st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
col_l, col_c, col_r = st.columns([1, 2, 1])
with col_c:
    if current_role == "교육청":
        if st.button("교육청 수신함 열기", type="primary",
                      width="stretch", key="go_inbox"):
            st.switch_page("pages/7_교육청수신함.py")
        st.markdown(
            "<div style='text-align:center; margin-top:8px; font-size:12px; color:#9A9A9F;'>"
            "수신·검증 · 약 2분 소요"
            "</div>",
            unsafe_allow_html=True,
        )
    elif current_role == "실":
        if st.button("내 담당 공간 점검 시작", type="primary",
                      width="stretch", key="go_inspect_space"):
            st.switch_page("pages/1_점검시작.py")
        st.markdown(
            "<div style='text-align:center; margin-top:8px; font-size:12px; color:#9A9A9F;'>"
            "학교 + 본인 PIN 인증 본인 담당 공간만 표시"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        if st.button("점검하러 가기", type="primary", width="stretch", key="go_inspect"):
            st.switch_page("pages/1_점검시작.py")
        st.markdown(
            "<div style='text-align:center; margin-top:8px; font-size:12px; color:#9A9A9F;'>"
            "모바일·태블릿 권장 · 약 3분 소요"
            "</div>",
            unsafe_allow_html=True,
        )

# ─────────────────────────────────────────
# 운영 모드 안내 — demo_mode 켜져 있을 때만 시연 관련 UI 노출.
# 시연 모드가 꺼져 있으면 시연 안내·시연 시작 카드·사용 방법(시연 흐름) 모두
# 숨김. 시연 진입은 [설정] 페이지의 "시연 모드 시작" 버튼으로 일원화.
# ─────────────────────────────────────────
st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
_demo_active = bool(st.session_state.get("demo_mode"))
if _demo_active:
    divider()
    st.caption(
        "현재 **시연 모드** 입니다 — 더미 이미지·자동 채움 허용. "
        "실 사용 시에는 설정 페이지에서 '시연 종료' 를 누르세요."
    )

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
        "**1단계 · 학교 찾기 + 인증** \n"
        "GPS · 학교명 · 지역 단계 검색 중 편한 방식으로 학교를 찾고, "
        "담당자 인증번호(6자리)를 입력합니다.\n\n"
        "**2단계 · AI 점검** \n"
        "정면·우측·좌측 **광각 3장** 만 촬영하면 AI가 공간 유형과 안전설비를 자동 식별하여 "
        "맞춤 점검표를 생성합니다. 놓친 항목은 '보완 촬영' 으로 추가하세요.\n\n"
        "**3단계 · 저장 + 발송** \n"
        "결과는 Human용(읽기 좋은 PDF/Excel) 과 Machine용(구조화 JSON) 으로 이중 저장됩니다. "
        "내부 결재 완료 후 교육청 담당자 이메일로 발송할 수 있습니다."
    )
    st.markdown("---")
    st.caption(
        "**팁** — 홈의 '시연 시작' 버튼을 누르면 데모 학교·공간이 자동 세팅되고 "
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

# 플로팅 튜토리얼 안내 div 는 클릭 처리가 어려워 제거함.
# 튜토리얼은 아래 oc1 컬럼의 "튜토리얼 열기" 버튼으로 진입.

# ─────────────────────────────────────────
# 시연 모드 꺼져 있으면 — 튜토리얼/시연 시작 카드/더미 입력 안내 모두 숨김.
# 시연 진입은 [설정] 에서 토글로만 가능.
# ─────────────────────────────────────────
if not _demo_active:
    st.stop()

# ─────────────────────────────────────────
# 튜토리얼 + 시연 시작 (2컬럼) — 시연 모드 ON 일 때만
# ─────────────────────────────────────────
divider()
oc1, oc2 = st.columns(2)

with oc1:
    st.markdown("**사용 방법 안내 (글)**")
    st.caption(
        "글로 읽는 3단계 흐름 — 학교 검색·인증 AI 점검 결과 저장·발송. "
        "처음 사용 시 30초 안에 이해 가능."
    )
    if st.button("사용 방법 보기", key="open_tutorial", width="stretch"):
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
    st.markdown("**시연 시작 (자동 흐름)**")
    st.caption(
        "1클릭 시연 — 공간 선택 후 학교·공간·더미 사진 7장 + AI 분석까지 "
        "**자동 진행**. 그 다음 단계(점검표 입력·점수 계산·결과 저장)는 사용자가 직접 "
        "조작합니다. 글로 읽기보다 직접 화면을 보면서 이해하고 싶을 때 사용하세요."
    )

    # 시연 가능한 10개 공간 (MVP 전체 — 더미 이미지로 모두 시연 가능)
    DEMO_SPACES = [
        "일반교실", "화학실", "물리실", "생명과학실", "지구과학실",
        "기술실", "가정실", "음악실", "미술실", "디자인실",
    ]
    autoplay_space = st.selectbox(
        "데모 공간",
        options=DEMO_SPACES,
        index=1, # 기본 화학실 (가장 풍부한 점검표)
        key="autoplay_space_choice",
    )

    has_existing = bool(st.session_state.get("school")) or bool(st.session_state.get("active_space"))
    if has_existing:
        st.markdown(
            "<div style='background:#FFF2F2; border:1px solid #F8D0D0; "
            "border-radius:6px; padding:8px 12px; font-size:12px; color:#D50000;'>"
            "기존 선택된 학교·공간·진행 중 작업이 모두 초기화됩니다."
            "</div>",
            unsafe_allow_html=True,
        )
    # 원클릭 자동재생 — 2단계 확인 없이 즉시 실행 (발표 시 빠르게)
    if st.button(f"시연 시작 ({autoplay_space})", key="autoplay_btn",
                  type="primary", width="stretch"):
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
        # 2) 없으면 "중학교" 검색 학교명 정렬 첫 결과 세션에 저장
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
            st.session_state["school_auth_verified"] = True

            # 0-2: 동일 데모 공간 재사용 (누적 방지)
            school_code = demo_school.get("정보공시 학교코드")
            demo_space_type = autoplay_space # "화학실" / "일반교실" / "미술실"
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

            # 시연 자동 재생 — PIL 더미 이미지로 7컷 즉석 생성 (실 사진 사용 X)
            from modules.demo_image import make_all_demo_shots
            shots = make_all_demo_shots(autoplay_space)
            st.session_state["shots"] = shots

            # 이전 AI 결과 클리어
            for _k in ["stage1_result", "stage2_result", "stage2_confirmed",
                       "stage3_result", "item_scores", "score_result",
                       "recommendations"]:
                st.session_state[_k] = None

            # 시연용 풍부한 응답을 세션에 직접 주입 — API 호출 우회.
            # API 키가 있어도 더미 이미지에 실 API 를 호출하면 "부재 N" 결과가
            # 나오므로, 시연 의도(풍부한 응답 표시)에 맞춰 합성 응답을 미리 세팅.
            # 실패 시 silent pass 하면 빈 결과로 supplement 점프해 사용자 혼란 명시 에러.
            try:
                from modules.demo_responses import (
                    synth_stage2_for_space, synth_stage3_for_space,
                )
                _s2 = synth_stage2_for_space(autoplay_space)
                _s3 = synth_stage3_for_space(autoplay_space, _s2)
                st.session_state["stage1_result"] = {
                    "space_type_primary": autoplay_space,
                    "confidence": 1.0,
                    "evidence": ["담당자 등록 정보"],
                    "secondary_hypothesis": None,
                    "notes": "시연 — 사용자 등록 정보 (Stage 1 생략)",
                    "_provider": "demo-synth",
                    "_cached": True,
                    "_skipped": True,
                }
                st.session_state["stage2_result"] = _s2
                st.session_state["stage3_result"] = _s3
                # 디스크 캐시도 함께 보장 (재진입·반복 시 hash 적중)
                from modules.ai_vision import ensure_demo_cache_for_shots
                ensure_demo_cache_for_shots(shots, autoplay_space)
            except Exception as e:
                st.error(
                    f"시연 합성 응답 준비 실패 — {e.__class__.__name__}: {e}\n\n"
                    f"다시 시도하거나 다른 공간을 선택하세요. 문제가 반복되면 "
                    f"`modules/demo_responses.py` 또는 `modules/ai_vision.py` "
                    f"확인 필요."
                )
                st.stop()

            st.session_state["_autoplay"] = True
            # 합성 응답을 이미 주입했으므로 AI 페이지에서 추가 호출 안 함.
            # supplement 스텝으로 직접 점프 — 분석 결과 카드 + 보완 안내 표시.
            st.session_state["_autoplay_run_ai"] = False
            st.session_state["wizard_step"] = "supplement"
            st.session_state["_autoplay_consumed"] = True
            st.toast(
                f"{autoplay_space} 시연 시작 — 더미 이미지로 흐름 진행",
                icon=None,
            )
            st.switch_page("pages/2_AI점검.py")

# 8-7: 세션 초기화는 설정 페이지에만 두기 (사이드바 중복 제거)
