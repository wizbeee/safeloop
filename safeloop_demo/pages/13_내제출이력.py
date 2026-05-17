"""
내 제출 이력 — 실 담당자 전용.

본인이 학교 담당자에게 제출한 점검들의 현재 상태(검토 대기/승인/반려/통합 완료)를
한눈에 확인하고, 반려된 경우 사유와 재점검 진입점을 제공한다.

설계:
- 본인 매니저 ID (`space_manager.manager_id`) 로 list_school_submissions 결과 필터링.
- 상태별 카드 묶음 — 반려 우선 노출 (재제출 안내), 그 다음 검토 대기, 승인, 통합 완료.
- 각 카드에서 상태 변경 이력(status_history) 펼쳐 학교 담당자 메모(반려 사유 등) 확인.
- 반려 카드에 "다시 점검하러 가기" 버튼 — wizard_step 초기화 + 같은 공간 재선택.
"""
from __future__ import annotations

import streamlit as st

from modules.session import ensure_state, require_school
from modules.storage import list_school_submissions, load_master_record
from modules.ui import apply_theme, divider, empty_state, hero, render_sidebar, section

st.set_page_config(
    page_title="내 제출 이력 · SafeLoop",
    page_icon="static/icon-192.png",
    layout="wide",
    initial_sidebar_state="auto",
)
apply_theme()
ensure_state()
render_sidebar(active_key="my_history")

# ─────────────────────────────────────────
# 역할 가드 — 실 담당자 전용
# ─────────────────────────────────────────
_role = st.session_state.get("role", "학교")
if _role == "교육청":
    st.warning(
        "**교육청 담당자 모드** — 본 페이지는 실 담당자가 본인의 제출 점검 "
        "상태를 확인하는 화면입니다. 교육청 입장에서는 [교육청 수신함]을 사용하세요."
    )
    if st.button("교육청 수신함", type="primary", width="stretch",
                  key="myhistory_to_inbox"):
        st.switch_page("pages/7_교육청수신함.py")
    st.stop()

if _role != "실":
    st.warning(
        "**학교 담당자 모드** — 본 페이지는 실 담당자(공간 담당 교사) 전용입니다. "
        "학교 단위로 모든 제출본을 보려면 [수합·검토] 페이지를 사용하세요."
    )
    if st.button("수합·검토로", type="primary", width="stretch",
                  key="myhistory_to_review"):
        st.switch_page("pages/0_수합검토.py")
    st.stop()

# ─────────────────────────────────────────
# 학교·매니저 컨텍스트
# ─────────────────────────────────────────
school = require_school()
if not school:
    empty_state(
        title="학교 인증이 필요합니다",
        description="점검 시작 페이지에서 학교 인증번호로 인증한 뒤 본인 PIN으로 "
                    "로그인하면 본 페이지에서 본인 제출 이력을 볼 수 있습니다.",
        action_label="점검 시작으로",
        action_target="pages/1_점검시작.py",
    )
    st.stop()

_space_mgr = st.session_state.get("space_manager") or {}
_my_mid = _space_mgr.get("manager_id")
_my_name = _space_mgr.get("name") or "실 담당자"

if not _my_mid:
    empty_state(
        title="실 담당자 인증이 필요합니다",
        description="점검 시작 페이지에서 본인 PIN으로 로그인하면 본 페이지에서 "
                    "본인의 제출 이력을 확인할 수 있습니다.",
        action_label="점검 시작으로",
        action_target="pages/1_점검시작.py",
    )
    st.stop()

school_code = school.get("정보공시 학교코드") or ""
school_name = school.get("학교명") or ""

hero(
    "MY HISTORY · 실 담당자",
    "내 제출 이력",
    f"{school_name} — {_my_name} 님이 제출한 점검의 현재 상태",
)

# ─────────────────────────────────────────
# 데이터 로드 + 본인 필터
# ─────────────────────────────────────────
all_subs = list_school_submissions(school_code)
my_subs = [s for s in all_subs if s.get("submitter_manager_id") == _my_mid]

if not my_subs:
    empty_state(
        title="아직 제출한 점검이 없습니다",
        description=(
            "[점검 시작] → [AI 점검] → [결과 제출] 까지 진행하면 여기에 "
            "제출 이력이 표시됩니다. 학교 담당자가 검토하면 상태(승인/반려)가 "
            "이 페이지에서 업데이트됩니다."
        ),
        action_label="점검 시작하러 가기",
        action_target="pages/1_점검시작.py",
    )
    st.stop()

# ─────────────────────────────────────────
# 상태별 분류 + KPI
# ─────────────────────────────────────────
def _count(status: str) -> int:
    return sum(1 for s in my_subs if s.get("status") == status)

returned_n = _count("returned")
submitted_n = _count("submitted")
approved_n = _count("approved")
consolidated_n = _count("consolidated")

k1, k2, k3, k4 = st.columns(4)
k1.metric("반려 (재점검 필요)", returned_n,
           help="학교 담당자가 수정 요청. 사유 확인 후 재점검 권장.")
k2.metric("검토 대기", submitted_n,
           help="제출 완료 — 학교 담당자 검토 대기 중.")
k3.metric("승인", approved_n,
           help="검토 통과 — 교육청 통합 보고서 후보로 등록됨.")
k4.metric("통합 완료", consolidated_n,
           help="학교 담당자가 교육청에 통합 보고서로 발송 처리함.")

if returned_n > 0:
    st.warning(
        f"**반려된 점검 {returned_n}건**이 있습니다. 아래 [반려] 카드에서 "
        f"사유를 확인하고 재점검 후 다시 제출해 주세요."
    )

# ─────────────────────────────────────────
# 상태별 카드 (반려 우선, 그 다음 대기/승인/통합)
# ─────────────────────────────────────────
STATUS_INFO = {
    "returned": {
        "label": "반려 — 재점검 필요",
        "color": "#EF4444",
        "icon_bg": "#FEF2F2",
        "order": 0,
        "help": "학교 담당자가 수정 사유를 적어 돌려보냈습니다. 사유 확인 후 같은 공간을 재점검해 다시 제출하세요.",
    },
    "submitted": {
        "label": "검토 대기",
        "color": "#FF9800",
        "icon_bg": "#FFF7ED",
        "order": 1,
        "help": "제출 완료. 학교 담당자가 곧 검토합니다.",
    },
    "approved": {
        "label": "승인 완료",
        "color": "#10B981",
        "icon_bg": "#F0FDF4",
        "order": 2,
        "help": "검토 통과. 학교 담당자가 교육청 통합 보고서를 만들 때 포함됩니다.",
    },
    "consolidated": {
        "label": "통합 완료",
        "color": "#1E2761",
        "icon_bg": "#F0F4FF",
        "order": 3,
        "help": "학교 담당자가 교육청에 통합 보고서로 발송 처리 완료. SafeLoop 내부 상태 표시이며 실제 발송은 외부 채널을 통해 이루어집니다.",
    },
}


def _format_time(ts: str | None) -> str:
    if not ts:
        return "-"
    try:
        return ts.replace("T", " ")[:16]
    except Exception:
        return str(ts)[:16]


# 상태별로 묶고 order 순서대로 표시
by_status: dict[str, list[dict]] = {}
for s in my_subs:
    st_key = s.get("status") or "approved"
    by_status.setdefault(st_key, []).append(s)

ordered_statuses = sorted(
    by_status.keys(),
    key=lambda x: STATUS_INFO.get(x, {"order": 99})["order"],
)

for status in ordered_statuses:
    info = STATUS_INFO.get(status, {
        "label": status, "color": "#888", "icon_bg": "#F5F5F5",
        "help": "",
    })
    items = by_status[status]

    divider()
    section(
        status.upper(),
        f"{info['label']} ({len(items)}건)",
        info["help"],
    )

    for sub in items:
        sid = sub["session_id"]
        score = sub.get("score")
        grade = sub.get("grade") or "-"
        space_disp = sub.get("space_type") or "(불명)"
        if sub.get("space_nickname"):
            space_disp += f" · {sub['space_nickname']}"

        with st.container(border=True):
            # 헤더 — 공간·점수·시간
            h1, h2 = st.columns([3, 1])
            with h1:
                st.markdown(
                    f"<div style='font-size:11px;letter-spacing:0.16em;"
                    f"color:{info['color']};font-weight:700;"
                    f"background:{info['icon_bg']};display:inline-block;"
                    f"padding:2px 10px;border-radius:4px;'>"
                    f"{info['label']}</div>"
                    f"<div style='font-size:15px;font-weight:700;"
                    f"margin-top:6px;'>{space_disp}</div>"
                    f"<div style='font-size:12px;color:#6B6B70;margin-top:2px;'>"
                    f"점수 <b>{score if score is not None else '-'}</b> · "
                    f"등급 <b>{grade}</b> · 제출 {_format_time(sub.get('timestamp'))}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with h2:
                if status == "returned":
                    if st.button(
                        "다시 점검",
                        key=f"redo_{sid}",
                        type="primary",
                        width="stretch",
                        help="같은 공간으로 점검 시작 페이지 이동 — 사진부터 다시 진행",
                    ):
                        # 같은 공간 선택 상태로 점검 시작 페이지 진입.
                        # active_space 만 set 하면 1_점검시작 진입 후 자동 선택됨.
                        from modules.session import reset_inspection
                        reset_inspection()
                        # 같은 공간 정보 복원
                        st.session_state["active_space"] = {
                            "space_id": sub.get("space_id"),
                            "school_code": school_code,
                            "type": sub.get("space_type"),
                            "nickname": sub.get("space_nickname"),
                        }
                        st.switch_page("pages/1_점검시작.py")

            # 상태 변경 이력 (펼치기) — 학교 담당자 메모·반려 사유 확인
            master = load_master_record(school_code, sid)
            history = (master or {}).get("status_history") or []
            if history:
                with st.expander(
                    f"상태 변경 이력 보기 ({len(history)}건)",
                    expanded=(status == "returned"),  # 반려는 기본 펼침
                ):
                    for h in history:
                        h_status = h.get("status", "")
                        h_label = STATUS_INFO.get(h_status, {}).get("label", h_status)
                        st.markdown(
                            f"- **{h_label}** · "
                            f"by `{h.get('by', '?')}` · "
                            f"{_format_time(h.get('at'))}"
                        )
                        h_note = h.get("note", "").strip()
                        if h_note:
                            # 반려 사유는 더 눈에 띄게
                            if h_status == "returned":
                                st.markdown(
                                    f"   <div style='background:#FEF2F2;"
                                    f"border-left:3px solid #EF4444;"
                                    f"padding:8px 12px;font-size:13px;"
                                    f"margin:4px 0 8px 16px;border-radius:4px;'>"
                                    f"<b style='color:#EF4444;'>사유</b><br>"
                                    f"{h_note}</div>",
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.caption(f"   메모: {h_note}")
