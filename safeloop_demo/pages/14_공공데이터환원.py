"""
공공데이터 환원 — 교육청 담당자 전용.

흐름:
1. 수신함의 학교 점검 데이터를 필터·선택
2. 공유 폴더 경로 입력 (대시보드와 동일 폴더 권장)
3. 환원 실행 — 익명화·집계 CSV 생성
4. 환원 이력 + 롤백 (잘못 환원한 경우 되돌리기)

대시보드(safeloop-dashboard)가 같은 공유 폴더를 자동 읽어 합산하므로,
환원 즉시 대시보드에 반영됩니다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.auth import is_authenticated_session
from modules.opendata_export import (
    default_shared_dir,
    export_opendata_csv,
    list_export_history,
    list_inbox_for_export,
    rollback_export,
)
from modules.session import ensure_state
from modules.ui import apply_theme, divider, hero, render_sidebar, section

st.set_page_config(
    page_title="공공데이터 환원 · SafeLoop",
    page_icon="static/icon-192.png",
    layout="wide",
    initial_sidebar_state="auto",
)
apply_theme()
ensure_state()
render_sidebar(active_key="opendata_export")

# ─────────────────────────────────────────
# 인증 + 역할 가드 — 교육청 담당자 전용
# ─────────────────────────────────────────
if not is_authenticated_session("edu"):
    st.warning(
        "**교육청 담당자 인증이 필요합니다** — 홈으로 돌아가 PIN 입력 또는 "
        "자동 로그인을 해주세요."
    )
    if st.button("홈으로 돌아가서 인증", type="primary",
                  width="stretch", key="opendata_back_home"):
        st.session_state["_show_pin_edu"] = True
        st.switch_page("app.py")
    st.stop()

_current_role = st.session_state.get("role", "학교")
if _current_role != "교육청":
    st.warning(
        f"공공 환원은 **교육청 담당자 전용** 화면입니다. "
        f"현재 {_current_role} 담당자 모드 — 역할을 변경하시려면 [설정]에서 "
        "전환해 주세요."
    )
    if st.button("설정으로 이동", type="primary",
                  width="stretch", key="opendata_to_settings"):
        st.switch_page("pages/8_설정.py")
    st.stop()

hero(
    "OPEN DATA · 환원",
    "공공데이터 환원",
    "교육청 수신함의 학교 점검 데이터를 익명화·집계해 공공데이터로 환원합니다. "
    "환원된 데이터는 지정 폴더에 저장되고, 대시보드(safeloop-dashboard)에 자동 반영됩니다.",
)

if st.session_state.get("demo_mode"):
    st.info(
        "📌 **공공데이터 등록은 교육부·KEIIS 등 상급 기관에서 이루어집니다.** "
        "본 화면은 시도교육청 단계의 환원 준비 흐름 — 익명화·집계된 결과를 "
        "상급 기관 전달용 데이터셋으로 출력하고, 본 시스템의 대시보드에 즉시 반영합니다."
    )

# ─────────────────────────────────────────
# 01 — 환원 대상 선택
# ─────────────────────────────────────────
section("01", "환원 대상 선택",
        "수신함의 학교 점검 데이터를 필터·선택합니다.")

inbox_items = list_inbox_for_export()
selected_items: list[dict] = []

if not inbox_items:
    st.info(
        "아직 환원할 수신 데이터가 없습니다. 교육청 수신함에 학교 점검 결과가 "
        "도착하면 여기 표시됩니다."
    )
else:
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        sido_opts = sorted({it["sido"] for it in inbox_items if it["sido"]})
        sido_filter = st.multiselect(
            "시도교육청 필터", options=sido_opts, default=[],
            key="opendata_sido_filter",
        )
    with fcol2:
        level_opts = sorted({it["school_level"] for it in inbox_items if it["school_level"]})
        level_filter = st.multiselect(
            "학교급 필터", options=level_opts, default=[],
            key="opendata_level_filter",
        )

    filtered = inbox_items
    if sido_filter:
        filtered = [it for it in filtered if it["sido"] in sido_filter]
    if level_filter:
        filtered = [it for it in filtered if it["school_level"] in level_filter]

    st.caption(f"표시 대상: {len(filtered)}건 / 전체 {len(inbox_items)}건")

    select_all = st.checkbox(
        f"전체 선택 ({len(filtered)}건)", key="opendata_select_all",
    )

    df_view = pd.DataFrame([
        {
            "선택": select_all,
            "익명 ID": (it["school_anonymous_id"] or "")[:8] + "...",
            "시도": it["sido"],
            "학교급": it["school_level"],
            "설립": it["establishment"],
            "공간": it["space_type"],
            "점수": it["safety_score"],
            "등급": it["grade"],
            "수신일": (it["received_at"] or "")[:10],
            "_idx": idx,
        }
        for idx, it in enumerate(filtered)
    ])

    edited = st.data_editor(
        df_view,
        column_config={
            "선택": st.column_config.CheckboxColumn(required=True),
            "_idx": None,
        },
        disabled=["익명 ID", "시도", "학교급", "설립", "공간", "점수", "등급", "수신일"],
        hide_index=True,
        use_container_width=True,
        height=400,
        key="opendata_inbox_editor",
    )

    selected_idxs = edited[edited["선택"]]["_idx"].tolist()
    selected_items = [filtered[i] for i in selected_idxs]
    st.metric("선택된 학교", f"{len(selected_items)}개")

divider()

# ─────────────────────────────────────────
# 02 — 공유 폴더 경로
# ─────────────────────────────────────────
section("02", "공유 폴더 경로",
        "환원 CSV가 저장될 폴더. 대시보드도 같은 폴더의 환원 데이터를 읽어 합산합니다.")

default_dir_str = str(default_shared_dir())
output_dir_str = st.text_input(
    "공유 폴더 절대 경로",
    value=default_dir_str,
    help="대시보드(safeloop-dashboard)도 같은 폴더의 환원 CSV를 자동 읽어 합산합니다. "
         "양쪽 모두 환경변수 SAFELOOP_SHARED_DIR 로 override 가능.",
    key="opendata_output_dir",
)

divider()

# ─────────────────────────────────────────
# 03 — 환원 실행
# ─────────────────────────────────────────
section("03", "환원 실행",
        "선택된 학교 데이터를 익명화·집계해 한 개의 CSV로 export 합니다.")

run_disabled = (not inbox_items) or len(selected_items) == 0
if run_disabled:
    st.caption("⓵ 환원할 항목을 한 개 이상 선택해야 활성화됩니다.")

if st.button("📤 공공 환원 실행", type="primary",
              disabled=run_disabled, key="opendata_run"):
    with st.spinner(f"{len(selected_items)}개 학교 데이터를 익명화·집계 중..."):
        result = export_opendata_csv(selected_items, output_dir_str)
    if result.get("ok"):
        st.success(
            f"✓ 환원 완료 — {result['count']}개교  \n"
            f"파일: `{result['file_name']}`  \n"
            f"위치: `{result['file_path']}`  \n"
            f"대시보드 새로고침 시 자동 반영됩니다."
        )
        with st.expander("시도 분포"):
            st.json(result["sido_distribution"])
    else:
        st.error(result.get("error") or "환원 실패 — 항목 또는 폴더 권한을 확인해 주세요.")

divider()

# ─────────────────────────────────────────
# 04 — 환원 이력 + 롤백
# ─────────────────────────────────────────
section("04", "환원 이력 + 롤백",
        "과거 환원 기록. 잘못 환원한 경우 ↩ 롤백으로 대시보드 반영에서 제외할 수 있습니다.")

history = list_export_history(output_dir_str)
if not history:
    st.info("아직 환원 이력이 없습니다.")
else:
    for idx, h in enumerate(history):
        status_badge = "🟢 활성" if h["status"] == "active" else "⚪ 롤백됨"
        sido_summary = " · ".join(
            f"{k} {v}" for k, v in sorted(
                (h.get("sido_distribution") or {}).items(),
                key=lambda x: -x[1],
            )[:3]
        ) or "—"
        c1, c2, c3, c4, c5 = st.columns([2.2, 0.8, 2, 0.8, 1])
        c1.markdown(
            f"**{h['file_name']}**  \n"
            f"*{(h.get('exported_at','')[:19] or '').replace('T',' ')}*"
        )
        c2.markdown(f"{h['count']}개교")
        c3.markdown(f"시도: {sido_summary}")
        c4.markdown(status_badge)
        with c5:
            if h["status"] == "active":
                if st.button("↩ 롤백", key=f"opendata_rollback_{idx}",
                              width="stretch"):
                    res = rollback_export(h["file_path"])
                    if res.get("ok"):
                        st.success(res["message"])
                        st.rerun()
                    else:
                        st.error(res["message"])
            else:
                st.caption("롤백됨")

divider()
st.caption(
    f"공유 폴더 — `{output_dir_str}`  \n"
    f"환원 시각은 한국 표준시(KST) 기준 · 익명화는 SHA-256 해시 (data_loader.anonymize_code)."
)
