"""
점검 이력 — 학교별 영구 저장 + 시계열 추이.

storage.list_recent_sessions() 가 디스크에서 master.json 들을 읽어 누적 표시.
세션이 끊겨도, 다른 컴퓨터에서 git pull 후 같은 학교 클라우드를 쓰면 이력이 유지된다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.session import ensure_state
from modules.storage import STORAGE_DIR, list_recent_sessions
from modules.ui import apply_theme, divider, empty_state, hero, render_sidebar, section

st.set_page_config(page_title="점검 이력 · SafeLoop", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="expanded")
apply_theme()
ensure_state()
render_sidebar(active_key="history")

# 역할 가드 — '점검 이력' 은 학교 담당자가 본교 이력을 추적하는 도구
# 교육청 담당자는 전체 학교 이력 대신 '교육청 수신함' 또는 '전국 대시보드' 사용
if st.session_state.get("role") == "교육청":
    st.warning(
        "🏛 **교육청 담당자 모드** — '점검 이력' 은 학교 담당자가 본교의 점검 시계열을 "
        "추적하는 화면입니다. 교육청 관점의 수신 데이터는 '교육청 수신함'을 이용하세요."
    )
    if st.button("→ 교육청 수신함으로 이동", type="primary"):
        st.switch_page("pages/7_교육청수신함.py")
    st.stop()

hero("HISTORY", "점검 이력",
     "학교 클라우드에 누적된 모든 점검 결과를 시계열·공간별로 추적합니다.")

# ─────────────────────────────────────────
# 전체 이력 로드
# ─────────────────────────────────────────
all_sessions = list_recent_sessions(limit=10000)
if not all_sessions:
    empty_state(
        title="누적된 점검 이력이 없습니다",
        description="AI 점검 → 결과 저장을 한 번 이상 수행하면 이 화면에 시계열·비교가 표시됩니다.",
        action_label="지금 점검 시작",
        action_target="pages/1_점검시작.py",
    )
    st.stop()

df = pd.DataFrame(all_sessions)
df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.dropna(subset=["timestamp_dt"]).sort_values("timestamp_dt")

# 학교 필터
school = st.session_state.get("school")
default_code = school.get("정보공시 학교코드") if school else None
codes = sorted(df["school_code"].unique().tolist())
labels = {c: f"{c}  ·  {df[df['school_code']==c]['school_name'].iloc[-1]}" for c in codes}

# ─────────────────────────────────────────
# 데스크톱: 좌(학교 선택 + KPI) | 우(시계열 추이)
# ─────────────────────────────────────────
left_col, right_col = st.columns([1, 2], gap="large")

with left_col:
    section("01", "학교 선택")
    sel_code = st.selectbox(
        "학교",
        options=codes,
        index=codes.index(default_code) if default_code in codes else 0,
        format_func=lambda c: labels.get(c, c),
        label_visibility="collapsed",
    )
    sub = df[df["school_code"] == sel_code].copy()
    school_name = sub["school_name"].iloc[-1] if len(sub) else sel_code

    st.markdown(f"<div style='margin-top:14px; font-size:12px; color:#6B6B70; "
                f"letter-spacing:0.16em;'>누적 통계 · {school_name}</div>",
                unsafe_allow_html=True)
    st.metric("총 점검 수", f"{len(sub)}회")
    st.metric("평균 점수", f"{sub['score'].mean():.1f}점")
    st.metric("점검 공간 종류", f"{sub['space_type'].nunique()}종")
    st.metric("최근 점검", str(sub["timestamp_dt"].max().date()))

with right_col:
    section("02", "시계열 추이", "공간별 색상 — 등급 구간 음영")
    fig = px.line(
        sub, x="timestamp_dt", y="score",
        color="space_type", markers=True,
        labels={"timestamp_dt": "점검 일시", "score": "안전 점수", "space_type": "공간 유형"},
    )
    fig.add_hrect(y0=80, y1=100, fillcolor="#4CAF50", opacity=0.06, line_width=0)
    fig.add_hrect(y0=60, y1=80, fillcolor="#FFC107", opacity=0.06, line_width=0)
    fig.add_hrect(y0=0, y1=60, fillcolor="#D50000", opacity=0.06, line_width=0)
    fig.update_layout(height=380, margin=dict(l=20, r=20, t=10, b=20),
                      paper_bgcolor="#FFF", plot_bgcolor="#FFF")
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────
# 공간별 박스플롯 (분포)
# ─────────────────────────────────────────
divider()
section("03", "공간 유형별 점수 분포")
fig2 = px.box(sub, x="space_type", y="score", points="all",
              color_discrete_sequence=["#D50000"],
              labels={"space_type": "공간 유형", "score": "점수"})
fig2.update_layout(height=320, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig2, use_container_width=True)

# ─────────────────────────────────────────
# 비교 모드 — 두 시점 선택
# ─────────────────────────────────────────
divider()
section("04", "두 시점 비교",
        "같은 공간의 이전 vs 최근 — 카테고리별 개선/악화 한눈에")

# 10-2 수정: 같은 공간(type + nickname)끼리만 비교 가능하도록 공간 필터 선행
sessions_for_pick = sub[["session_id", "timestamp_dt", "space_type", "space_nickname",
                          "score", "grade"]].copy()
sessions_for_pick["공간키"] = sessions_for_pick.apply(
    lambda r: f"{r['space_type']} · {r['space_nickname'] or '(별칭 없음)'}", axis=1
)
sessions_for_pick["라벨"] = sessions_for_pick.apply(
    lambda r: f"{r['timestamp_dt']:%Y-%m-%d %H:%M} · {r['score']}점",
    axis=1,
)

# 같은 공간으로 2회 이상 점검된 공간 목록
counts = sessions_for_pick["공간키"].value_counts()
comparable_spaces = counts[counts >= 2].index.tolist()

if not comparable_spaces:
    st.info(
        "같은 공간(유형·별칭 일치)을 **2회 이상** 점검해야 비교가 활성화됩니다. "
        "현재는 단일 점검 공간들만 있어 개선/악화를 신뢰 있게 비교할 수 없습니다."
    )
else:
    space_pick = st.selectbox(
        "비교할 공간 선택 (같은 공간만 나옴)",
        options=comparable_spaces,
        key="hist_space_pick",
    )
    space_subset = sessions_for_pick[sessions_for_pick["공간키"] == space_pick] \
        .sort_values("timestamp_dt").set_index("session_id")

    col_a, col_b = st.columns(2)
    with col_a:
        sid_old = st.selectbox("이전 시점", options=space_subset.index,
                                format_func=lambda s: space_subset.loc[s, "라벨"],
                                index=0, key="hist_old")
    with col_b:
        sid_new = st.selectbox("최근 시점", options=space_subset.index,
                                format_func=lambda s: space_subset.loc[s, "라벨"],
                                index=len(space_subset) - 1, key="hist_new")

    if sid_old == sid_new:
        st.caption("서로 다른 시점을 선택하세요.")
    else:
        def _load(sid: str) -> dict | None:
            path = Path(sub[sub["session_id"] == sid]["path"].iloc[0]) / "master.json"
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None

        old_m = _load(sid_old)
        new_m = _load(sid_new)
        if old_m and new_m:
            old_cat = ((old_m.get("inspection") or {}).get("score_result") or {}).get("category_scores") or {}
            new_cat = ((new_m.get("inspection") or {}).get("score_result") or {}).get("category_scores") or {}
            cats = sorted(set(old_cat.keys()) | set(new_cat.keys()))
            rows = []
            for c in cats:
                o = (old_cat.get(c, {}) or {}).get("score", 0)
                n = (new_cat.get(c, {}) or {}).get("score", 0)
                rows.append({"카테고리": c, "이전": o, "최근": n, "변화": n - o})
            cmp_df = pd.DataFrame(rows)
            st.dataframe(cmp_df, use_container_width=True, hide_index=True)

            fig3 = go.Figure()
            fig3.add_trace(go.Bar(name="이전", x=cmp_df["카테고리"], y=cmp_df["이전"],
                                  marker_color="#9A9A9F"))
            fig3.add_trace(go.Bar(name="최근", x=cmp_df["카테고리"], y=cmp_df["최근"],
                                  marker_color="#D50000"))
            fig3.update_layout(barmode="group", height=320,
                               margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig3, use_container_width=True)

# ─────────────────────────────────────────
# 전체 이력 표
# ─────────────────────────────────────────
divider()
section("05", "전체 이력")
table = sub[["timestamp_dt", "space_type", "space_nickname", "score", "grade", "session_id"]].copy()
table.columns = ["점검 일시", "공간 유형", "별칭", "점수", "등급", "세션 ID"]
table = table.sort_values("점검 일시", ascending=False)
st.dataframe(table, use_container_width=True, hide_index=True)
