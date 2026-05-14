"""
수합·검토 페이지 — 학교 담당자 전용.

본교의 실 담당자들이 제출한 점검을 한눈에 보고 처리:
- ✅ 승인  (교육청 발송 대상으로 확정)
- ⛔ 반려  (사유 입력 → 실 담당자에게 재점검 요청)
- ✏️ 직접 수정 (학교 담당자가 점수·항목을 바로 보정)

검토 결과는 master.json 의 status + status_history 에 누적 기록.
"""
from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
import streamlit as st

from modules.score import calculate_safety_score
from modules.session import ensure_state, require_school
from modules.storage import (
    list_school_submissions,
    load_master_record,
    update_submission_scores,
    update_submission_status,
)
from modules.ui import (
    apply_theme, divider, empty_state, hero, render_sidebar, section,
)

st.set_page_config(
    page_title="수합·검토 · SafeLoop",
    page_icon="static/icon-192.png",
    layout="wide",
    initial_sidebar_state="auto",
)
apply_theme()
ensure_state()
render_sidebar(active_key="review")

# ─────────────────────────────────────────
# 역할·인증 가드 — 학교 담당자 전용
# ─────────────────────────────────────────
_role = st.session_state.get("role", "학교")
if _role == "교육청":
    st.warning(
        "🏛 **교육청 담당자 모드** — 본 페이지는 학교 담당자가 우리 학교의 "
        "실 담당자 제출본을 검토하는 화면입니다. 교육청 입장에서는 "
        "**교육청 수신함**을 사용하세요."
    )
    if st.button("→ 교육청 수신함", type="primary", width="stretch",
                  key="review_to_inbox"):
        st.switch_page("pages/7_교육청수신함.py")
    st.stop()

if _role == "실":
    st.warning(
        "👤 **실 담당자 모드** — 본 페이지는 학교 담당자(안전관리 책임자)가 "
        "실 담당자 제출본을 검토하는 화면입니다. 실 담당자는 자기 점검을 "
        "[점검 시작] 에서 진행하세요."
    )
    if st.button("→ 내 점검 시작", type="primary", width="stretch",
                  key="review_to_inspect"):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

school = require_school()
if not school:
    if st.button("← 학교 찾기로", key="review_noschool_back", width="stretch"):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

school_code = school.get("정보공시 학교코드") or ""
school_name = school.get("학교명") or ""

hero(
    "REVIEW · 학교 담당자",
    "수합·검토",
    f"{school_name} — 실 담당자 제출본을 검토하고 승인·반려·수정합니다.",
)

# 모바일 사용자 안내 — 본 페이지는 표·다중 컬럼이 많아 PC 권장
st.markdown(
    """
    <div class='sl-mobile-hint' style='display:none;padding:8px 12px;
    background:#FFF6F6;border:1px solid #F8D0D0;border-radius:6px;
    font-size:12.5px;color:#0A0A0B;margin-bottom:10px;line-height:1.55;'>
    📱 <b>모바일에서 보고 계시네요.</b> 이 화면은 표가 많아 PC·태블릿 가로 화면에서
    더 보기 편합니다. 모바일에선 가로 스크롤이나 화면 회전을 활용하세요.
    </div>
    <style>
    @media (max-width: 768px) {
        .sl-mobile-hint { display: block !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────
# 데이터 로드 + KPI
# ─────────────────────────────────────────
all_subs = list_school_submissions(school_code)


def _count(status: str) -> int:
    return sum(1 for s in all_subs if s.get("status") == status)


submitted_n = _count("submitted")
approved_n = _count("approved")
returned_n = _count("returned")
consolidated_n = _count("consolidated")

if not all_subs:
    empty_state(
        title=f"{school_name} 에 제출된 점검이 없습니다",
        description=(
            "실 담당자가 [점검 시작] → [AI 점검] → [결과 저장] 까지 진행하면 "
            "이 화면에 검토 대기 항목이 나타납니다.\n\n"
            "💡 학교 담당자 본인이 직접 점검한 경우는 자동으로 **승인 상태**로 "
            "저장됩니다 (별도 검토 절차 없음).\n\n"
            "**실 담당자가 아직 명부에 없다면** → [설정] 페이지의 "
            "**실 담당자 명부 관리**에서 먼저 등록하세요."
        ),
        action_label="실 담당자 명부 등록",
        action_target="pages/8_설정.py",
    )
    st.stop()

# KPI 카드 4개
k1, k2, k3, k4 = st.columns(4)
k1.metric("⏳ 검토 대기", submitted_n, help="실 담당자가 제출 후 학교 담당자 검토 대기 중")
k2.metric("✅ 승인 완료", approved_n, help="검토 통과 — 교육청 발송 후보")
k3.metric("⛔ 반려", returned_n, help="수정 후 재제출 요청됨")
k4.metric("📤 통합·발송 완료", consolidated_n, help="교육청 통합 보고서에 포함되어 발송됨")

# ─────────────────────────────────────────
# 필터
# ─────────────────────────────────────────
divider()
section("FILTER", "목록 필터",
        "원하는 상태·공간·제출자만 골라서 빠르게 보기")

filter_col1, filter_col2, filter_col3 = st.columns(3)
with filter_col1:
    status_label = st.selectbox(
        "상태",
        ["전체", "검토 대기 (submitted)", "승인 (approved)",
         "반려 (returned)", "통합 완료 (consolidated)"],
        index=1 if submitted_n > 0 else 0,  # 대기 있으면 우선 표시
        key="_review_filter_status",
    )

STATUS_MAP = {
    "전체": None,
    "검토 대기 (submitted)": "submitted",
    "승인 (approved)": "approved",
    "반려 (returned)": "returned",
    "통합 완료 (consolidated)": "consolidated",
}
status_filter = STATUS_MAP.get(status_label)

# 공간·제출자 옵션은 현재 데이터 기반
all_space_types = sorted({s.get("space_type") or "(불명)" for s in all_subs})
all_submitters = sorted({s.get("submitter_name") or "(미상)" for s in all_subs})

with filter_col2:
    space_filter = st.multiselect(
        "공간 유형",
        options=all_space_types,
        default=[],
        placeholder="전체",
        key="_review_filter_space",
    )

with filter_col3:
    submitter_filter = st.multiselect(
        "제출자",
        options=all_submitters,
        default=[],
        placeholder="전체",
        key="_review_filter_submitter",
    )


def _passes(item: dict) -> bool:
    if status_filter and item.get("status") != status_filter:
        return False
    if space_filter and item.get("space_type") not in space_filter:
        return False
    if submitter_filter and item.get("submitter_name") not in submitter_filter:
        return False
    return True


visible = [s for s in all_subs if _passes(s)]

# ─────────────────────────────────────────
# 목록 + 액션
# ─────────────────────────────────────────
divider()
section("LIST", f"제출 목록 ({len(visible)}건)",
        "각 항목을 펼치면 상세 + 액션 버튼이 나타납니다.")

if not visible:
    st.info(
        "필터 조건에 맞는 제출이 없습니다. "
        "사이드 옵션을 완화하거나 [전체] 로 보세요."
    )
    st.stop()

# 일괄 액션 — 검토 대기만 골랐을 때 활성
if status_filter == "submitted" and visible:
    _bulk_col1, _bulk_col2 = st.columns([1, 3])
    with _bulk_col1:
        if st.button(
            f"✅ {len(visible)}건 모두 승인",
            key="_bulk_approve",
            type="primary",
            width="stretch",
            help="필터로 보이는 모든 검토 대기 항목을 한 번에 승인",
        ):
            _approver = school.get("학교명", "학교 담당자") + " 학교 담당자"
            _ok = 0
            for _s in visible:
                if update_submission_status(
                    school_code,
                    _s["session_id"],
                    "approved",
                    by=_approver,
                    by_role="학교",
                    note="일괄 승인",
                ):
                    _ok += 1
            st.toast(f"{_ok}건 일괄 승인 완료", icon="✅")
            st.rerun()
    with _bulk_col2:
        st.caption("⚠ 일괄 승인은 되돌릴 수 없습니다. 개별 확인 후 사용 권장.")

# ─────────────────────────────────────────
# 각 항목 카드
# ─────────────────────────────────────────
STATUS_BADGE = {
    "submitted": ("⏳", "#FF9800", "검토 대기"),
    "approved": ("✅", "#10B981", "승인"),
    "returned": ("⛔", "#EF4444", "반려"),
    "consolidated": ("📤", "#1E2761", "통합 완료"),
}


def _format_time(ts: str | None) -> str:
    if not ts:
        return "-"
    try:
        return ts.replace("T", " ")[:16]
    except Exception:
        return str(ts)[:16]


for sub in visible:
    sid = sub["session_id"]
    status = sub.get("status") or "approved"
    badge_emoji, badge_color, badge_label = STATUS_BADGE.get(
        status, ("•", "#888", status)
    )
    score = sub.get("score")
    grade = sub.get("grade") or "-"
    space_disp = sub.get("space_type") or "(불명)"
    if sub.get("space_nickname"):
        space_disp += f" · {sub['space_nickname']}"

    title_html = (
        f"<div style='display:flex;align-items:center;gap:12px;'>"
        f"<span style='font-size:11px;letter-spacing:0.16em;color:{badge_color};"
        f"font-weight:700;background:{badge_color}1A;padding:2px 8px;border-radius:4px;'>"
        f"{badge_emoji} {badge_label.upper()}</span>"
        f"<b style='font-size:14px;'>{space_disp}</b>"
        f"<span style='color:#6B6B70;font-size:12.5px;'>"
        f" · 점수 <b style='color:#0A0A0B;'>{score if score is not None else '-'}</b>"
        f" · 등급 <b>{grade}</b>"
        f" · 제출자 <b>{sub.get('submitter_name', '-')}</b> ({sub.get('submitter_role') or '?'})"
        f" · {_format_time(sub.get('timestamp'))}"
        f"</span></div>"
    )

    with st.expander("　", expanded=False):
        st.markdown(title_html, unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # 상세 데이터 로드 (지연 — expander 열림 시에만)
        master = load_master_record(school_code, sid)
        if not master:
            st.error("master.json 을 읽을 수 없습니다.")
            continue

        # 1. 점수·등급 분해
        score_result = ((master.get("inspection") or {}).get("score_result") or {})
        cats = score_result.get("category_scores") or {}

        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            st.metric("종합", f"{score_result.get('score', '-')}점")
            st.metric("등급", score_result.get("grade", "-"))
        with c2:
            if cats:
                cat_df = pd.DataFrame([
                    {"카테고리": k, "점수": v.get("score", 0)}
                    for k, v in cats.items()
                ])
                st.dataframe(cat_df, hide_index=True, width="stretch")
        with c3:
            st.caption(f"세션 ID `{sid}`")
            st.caption(f"상태 변경 {sub.get('history_count', 0)}회")
            st.caption(f"공간 ID `{sub.get('space_id', '-')}`")

        # 2. 점검표 항목 (간단 표)
        stage3 = ((master.get("ai_pipeline") or {}).get("stage3") or {})
        items_list = stage3.get("items") or []
        if items_list:
            with st.expander(f"📋 AI 점검표 ({len(items_list)} 항목)", expanded=False):
                table_rows = []
                item_scores = ((master.get("inspection") or {}).get("item_scores") or {})
                for it in items_list:
                    no = it.get("no")
                    raw = item_scores.get(str(no)) if item_scores else None
                    if raw is None and item_scores:
                        raw = item_scores.get(no)
                    label = {1.0: "양호", 0.5: "불량", 0.0: "부재"}.get(
                        float(raw) if raw is not None else -1, "미입력"
                    )
                    table_rows.append({
                        "번호": no,
                        "분류": it.get("category"),
                        "제목": it.get("title"),
                        "점검 결과": label,
                        "우선순위": it.get("priority"),
                    })
                st.dataframe(pd.DataFrame(table_rows),
                              hide_index=True, width="stretch")

        # 3. 상태 변경 이력
        history = master.get("status_history") or []
        if history:
            with st.expander(f"📜 상태 변경 이력 ({len(history)}건)", expanded=False):
                for h in history:
                    st.markdown(
                        f"- **{h.get('status')}** · "
                        f"`{h.get('by')}` ({h.get('by_role')}) · "
                        f"{_format_time(h.get('at'))} · "
                        f"_{h.get('note', '')}_"
                    )

        # 4. 액션 버튼 — 상태에 따라 다른 메뉴
        st.markdown(
            "<div style='height:6px;border-top:1px dashed #E5E5E8;margin:10px 0;'></div>",
            unsafe_allow_html=True,
        )
        st.markdown("**액션**")

        approver_id = school.get("학교명", "학교 담당자") + " 학교 담당자"

        action_col1, action_col2, action_col3, action_col4 = st.columns(4)

        # 4-1. 승인
        with action_col1:
            can_approve = status in ("submitted", "returned")
            if st.button(
                "✅ 승인",
                key=f"approve_{sid}",
                type="primary",
                width="stretch",
                disabled=not can_approve,
                help="이 제출본을 승인 — 교육청 발송 후보로 확정"
                      if can_approve else "이미 승인됨 또는 통합 완료된 상태",
            ):
                if update_submission_status(
                    school_code, sid, "approved",
                    by=approver_id, by_role="학교", note="검토 후 승인",
                ):
                    st.toast(f"{space_disp} 승인 완료", icon="✅")
                    st.rerun()

        # 4-2. 반려
        with action_col2:
            can_return = status == "submitted"
            if st.button(
                "⛔ 반려",
                key=f"return_{sid}",
                width="stretch",
                disabled=not can_return,
                help="수정 사유를 적어 실 담당자에게 재점검 요청"
                      if can_return else "검토 대기 상태에서만 반려 가능",
            ):
                st.session_state["_return_target_sid"] = sid
                st.rerun()

        # 4-3. 직접 수정
        with action_col3:
            if st.button(
                "✏️ 직접 수정",
                key=f"edit_{sid}",
                width="stretch",
                disabled=status == "consolidated",
                help="학교 담당자가 점검 항목 점수를 직접 보정"
                      if status != "consolidated" else "통합·발송 완료 후에는 수정 불가",
            ):
                st.session_state["_edit_target_sid"] = sid
                st.rerun()

        # 4-4. 다시 검토 대기로 (승인된 항목을 되돌리기)
        with action_col4:
            can_revert = status in ("approved", "returned")
            if st.button(
                "↩ 검토 대기로",
                key=f"revert_{sid}",
                width="stretch",
                disabled=not can_revert,
                help="결정을 되돌려 다시 검토 대기 상태로",
            ):
                if update_submission_status(
                    school_code, sid, "submitted",
                    by=approver_id, by_role="학교",
                    note="검토 결과 되돌림 (재검토 대기)",
                ):
                    st.toast(f"{space_disp} 검토 대기로 되돌림", icon="↩")
                    st.rerun()

        # 반려 사유 입력 폼 (이 항목이 타겟인 경우)
        if st.session_state.get("_return_target_sid") == sid:
            with st.container(border=True):
                st.markdown("##### 반려 사유 입력")
                reason = st.text_area(
                    "사유 (실 담당자에게 표시됨)",
                    placeholder="예: 사진 2번 흄후드가 흐려서 다시 촬영 부탁드립니다.",
                    key=f"_return_reason_{sid}",
                )
                rb1, rb2 = st.columns(2)
                if rb1.button("반려 확정", key=f"_return_confirm_{sid}",
                               type="primary", width="stretch"):
                    if not reason.strip():
                        st.error("사유를 입력하세요.")
                    elif update_submission_status(
                        school_code, sid, "returned",
                        by=approver_id, by_role="학교",
                        note=f"반려 사유: {reason.strip()}",
                    ):
                        st.session_state.pop("_return_target_sid", None)
                        st.toast(f"{space_disp} 반려 완료", icon="⛔")
                        st.rerun()
                if rb2.button("취소", key=f"_return_cancel_{sid}",
                               width="stretch"):
                    st.session_state.pop("_return_target_sid", None)
                    st.rerun()

        # 직접 수정 폼 (이 항목이 타겟인 경우)
        if st.session_state.get("_edit_target_sid") == sid:
            with st.container(border=True):
                st.markdown("##### 점수 직접 수정")
                st.caption(
                    "각 항목별 양호(1.0) / 불량(0.5) / 부재(0.0) 또는 미입력 "
                    "중 선택. 저장 시 종합 점수가 재계산됩니다."
                )

                cur_item_scores = dict(
                    ((master.get("inspection") or {}).get("item_scores")) or {}
                )
                edited_scores: dict[str, Any] = {}
                _space_type = (master.get("space") or {}).get("type")

                # AI 점검표 항목 기준으로 입력 폼 생성
                _items = stage3.get("items") or []
                if not _items:
                    st.warning("AI 점검표 항목이 없어 점수 수정이 불가합니다.")
                else:
                    for _it in _items[:30]:  # 안전상 30개 제한 (UI 부담)
                        _no = _it.get("no")
                        _title = _it.get("title", f"항목 {_no}")
                        # 기존 점수 키 후보 (다양한 저장 패턴 호환)
                        _existing = (
                            cur_item_scores.get(str(_no))
                            or cur_item_scores.get(_no)
                            or cur_item_scores.get(_title)
                        )
                        try:
                            _existing_f = float(_existing) if _existing is not None else None
                        except Exception:
                            _existing_f = None

                        OPTIONS = [None, 1.0, 0.5, 0.0]
                        _idx = OPTIONS.index(_existing_f) if _existing_f in OPTIONS else 0
                        _picked = st.radio(
                            f"{_no}. {_title}",
                            options=OPTIONS,
                            format_func=lambda x: {
                                None: "미입력", 1.0: "양호", 0.5: "불량", 0.0: "부재",
                            }.get(x, str(x)),
                            index=_idx,
                            horizontal=True,
                            key=f"_edit_radio_{sid}_{_no}",
                        )
                        if _picked is not None:
                            edited_scores[str(_no)] = _picked
                            edited_scores[_title] = _picked

                eb1, eb2 = st.columns(2)
                if eb1.button(
                    "수정 저장 + 점수 재계산",
                    key=f"_edit_save_{sid}",
                    type="primary", width="stretch",
                ):
                    try:
                        # 점수 재계산 (공간 유형 고려)
                        _calc = calculate_safety_score(
                            edited_scores, space_type=_space_type,
                        )
                        if update_submission_scores(
                            school_code, sid,
                            new_item_scores=edited_scores,
                            new_score_result=_calc,
                            by=approver_id,
                            note="학교 담당자 직접 수정",
                        ):
                            st.session_state.pop("_edit_target_sid", None)
                            st.toast(
                                f"{space_disp} 수정 완료 — 새 점수 "
                                f"{_calc.get('score', '-')}",
                                icon="✅",
                            )
                            st.rerun()
                    except Exception as e:
                        st.error(f"수정 실패: {e}")
                if eb2.button("취소", key=f"_edit_cancel_{sid}",
                               width="stretch"):
                    st.session_state.pop("_edit_target_sid", None)
                    st.rerun()

# ─────────────────────────────────────────
# 본교 통합 발송 — 승인된 점검들을 묶어 교육청에 한 보고서로 발송
# ─────────────────────────────────────────
divider()
section(
    "DISPATCH",
    "본교 통합 발송 — 교육청 보고",
    "승인된 점검들을 한 묶음 보고서로 만들어 교육청에 발송합니다.",
)

from modules.consolidate import (
    build_consolidated_excel,
    build_consolidated_pdf,
    build_consolidated_record,
    list_consolidatable,
    mark_consolidated,
)

_dispatchable = list_consolidatable(school_code)

if not _dispatchable:
    st.info(
        "📤 교육청에 발송할 **승인 완료된 점검이 없습니다**. "
        "위에서 실 담당자 제출본을 승인하거나, 본인이 직접 점검·저장한 항목이 "
        "있어야 통합 보고서에 포함할 수 있습니다."
    )
else:
    st.caption(
        f"승인 완료된 점검 **{len(_dispatchable)}건**. "
        "원하는 항목을 선택해 통합 보고서를 생성하세요."
    )

    # 선택 UI — 기본은 전부 선택
    _disp_df_rows = []
    for d in _dispatchable:
        _disp_df_rows.append({
            "선택": True,
            "공간": (d.get("space_type") or "-")
                + (f" · {d['space_nickname']}" if d.get("space_nickname") else ""),
            "점수": d.get("score"),
            "등급": d.get("grade"),
            "제출자": d.get("submitter_name"),
            "역할": d.get("submitter_role"),
            "session_id": d.get("session_id"),
        })

    _disp_df = pd.DataFrame(_disp_df_rows)
    _edited = st.data_editor(
        _disp_df,
        hide_index=True,
        width="stretch",
        column_config={
            "선택": st.column_config.CheckboxColumn(
                "포함",
                help="이번 통합 보고서에 포함",
                default=True,
            ),
            "session_id": None,  # 숨김 (key 용)
        },
        disabled=["공간", "점수", "등급", "제출자", "역할"],
        key="_dispatch_selector",
    )

    _selected_sids = [
        row["session_id"] for _, row in _edited.iterrows() if row.get("선택")
    ]

    if not _selected_sids:
        st.warning("최소 1개 이상 선택하세요.")
    else:
        # 미리보기·다운로드 트리거
        _preview_active = st.session_state.get("_dispatch_preview_active", False)
        _bp1, _bp2 = st.columns([1, 1])
        with _bp1:
            if st.button(
                f"📊 통합 보고서 미리보기 ({len(_selected_sids)}개)",
                key="_dispatch_preview",
                type="primary",
                width="stretch",
            ):
                # 통합 record 생성 + 세션에 캐시
                _admin = school.get("학교명", "") + " 학교 담당자"
                _record = build_consolidated_record(
                    school_code, _selected_sids,
                    school_admin_name=_admin,
                )
                st.session_state["_dispatch_record"] = _record
                st.session_state["_dispatch_preview_active"] = True
                st.session_state["_dispatch_session_ids"] = _selected_sids
                st.rerun()
        with _bp2:
            if _preview_active and st.button(
                "✖ 미리보기 닫기",
                key="_dispatch_close",
                width="stretch",
            ):
                for _k in (
                    "_dispatch_record",
                    "_dispatch_preview_active",
                    "_dispatch_session_ids",
                ):
                    st.session_state.pop(_k, None)
                st.rerun()

        # 미리보기 + 다운로드 + 발송
        if _preview_active and st.session_state.get("_dispatch_record"):
            _record = st.session_state["_dispatch_record"]
            _selected_now = st.session_state.get(
                "_dispatch_session_ids", _selected_sids
            )

            with st.container(border=True):
                st.markdown("### 📋 통합 보고서 미리보기")

                # KPI
                _pk1, _pk2, _pk3 = st.columns(3)
                _pk1.metric("포함 공간 수", _record.get("spaces_count", 0))
                _pk2.metric(
                    "평균 점수",
                    f"{_record.get('average_score', '-')}",
                )
                _pk3.metric(
                    "발송 학교",
                    (_record.get("school") or {}).get("name", "-"),
                )

                # 공간별 요약 표
                st.markdown("##### 포함된 공간 목록")
                _spaces_df = pd.DataFrame([
                    {
                        "공간 유형": s.get("space_type"),
                        "별칭": s.get("space_nickname") or "-",
                        "점수": s.get("score"),
                        "등급": s.get("grade"),
                        "제출자": s.get("submitter_name"),
                        "승인 일시": (s.get("approved_at") or "").replace("T", " ")[:16],
                    }
                    for s in (_record.get("spaces") or [])
                ])
                st.dataframe(_spaces_df, hide_index=True, width="stretch")

                # 다운로드 — PDF + Excel + JSON
                st.markdown("##### 산출물 다운로드")
                try:
                    _pdf_bytes = build_consolidated_pdf(_record)
                    _xlsx_bytes = build_consolidated_excel(_record)
                    import json as _json
                    _json_bytes = _json.dumps(
                        _record, ensure_ascii=False, indent=2
                    ).encode("utf-8")

                    _dl1, _dl2, _dl3 = st.columns(3)
                    _ts_label = datetime.datetime.now().strftime("%Y%m%d-%H%M")
                    _school_n = (_record.get("school") or {}).get("name", "school")
                    _file_base = f"{_school_n}_통합점검보고서_{_ts_label}"

                    with _dl1:
                        st.download_button(
                            "📄 PDF (결재·인쇄용)",
                            _pdf_bytes,
                            file_name=f"{_file_base}.pdf",
                            mime="application/pdf",
                            width="stretch",
                            key="_dl_consolidated_pdf",
                        )
                    with _dl2:
                        st.download_button(
                            "📊 Excel (KEIIS 입력용)",
                            _xlsx_bytes,
                            file_name=f"{_file_base}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            width="stretch",
                            key="_dl_consolidated_xlsx",
                        )
                    with _dl3:
                        st.download_button(
                            "🗂 JSON (시스템 연동)",
                            _json_bytes,
                            file_name=f"{_file_base}.json",
                            mime="application/json",
                            width="stretch",
                            key="_dl_consolidated_json",
                        )
                except Exception as _err:
                    st.error(f"산출물 생성 실패: {_err}")
                    st.caption("디버그: " + str(type(_err).__name__))

                # 교육청 발송 (상태 일괄 consolidated)
                st.markdown("##### 교육청 발송 + 상태 처리")
                st.caption(
                    "발송 처리 시 선택된 점검들의 상태가 일괄 **통합 완료(consolidated)** 로 변경됩니다. "
                    "실제 교육청 이메일 발송은 위 PDF/Excel/JSON 을 첨부해 별도로 진행하세요. "
                    "(다음 단계에서 자동 발송 통합 예정)"
                )

                _send_col1, _send_col2 = st.columns([2, 1])
                with _send_col1:
                    _confirm = st.checkbox(
                        "✅ 위 산출물을 교육청에 발송했고, 이제 상태를 통합 완료로 처리합니다",
                        key="_dispatch_confirm",
                    )
                with _send_col2:
                    if st.button(
                        "📤 통합 완료 처리",
                        key="_dispatch_finalize",
                        type="primary",
                        width="stretch",
                        disabled=not _confirm,
                    ):
                        _admin_label = school.get("학교명", "") + " 학교 담당자"
                        _ok = mark_consolidated(
                            school_code,
                            _selected_now,
                            by=_admin_label,
                            note=f"학교 단위 통합 발송 ({len(_selected_now)}건)",
                        )
                        # 세션 정리
                        for _k in (
                            "_dispatch_record",
                            "_dispatch_preview_active",
                            "_dispatch_session_ids",
                            "_dispatch_confirm",
                        ):
                            st.session_state.pop(_k, None)
                        st.toast(
                            f"{_ok}건 통합 완료 처리 — 교육청 발송 기록 저장됨",
                            icon="📤",
                        )
                        st.rerun()
