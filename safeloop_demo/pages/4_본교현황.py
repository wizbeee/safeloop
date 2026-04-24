"""
대시보드 A — 본교 실시간 현황.

학교 클라우드에 저장된 점검 결과를 즉시 반영.
공공데이터 대시보드(B)와는 달리 익명화·집계 없이 식별 유지로 내부 관리용.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.laws import CATEGORIES
from modules.session import ensure_state
from modules.storage import list_recent_sessions
from modules.ui import apply_theme, divider, empty_state, hero, render_sidebar, section

st.set_page_config(page_title="본교 현황 · SafeLoop", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="expanded")
apply_theme()
ensure_state()
render_sidebar(active_key="school_dash")

# 역할 가드 — '본교 현황' 은 학교 담당자 전용
# (교육청 담당자는 '본교' 개념이 없으므로 전국 대시보드로 유도)
if st.session_state.get("role") == "교육청":
    st.warning(
        "🏛 **교육청 담당자 모드** — '본교 현황' 은 학교 담당자가 자신의 학교 데이터를 "
        "확인하는 내부용 화면입니다. 교육청 관점에서는 '전국 대시보드' 를 사용하세요."
    )
    if st.button("→ 전국 대시보드로 이동", key="dash_guard_national",
                  type="primary", use_container_width=True):
        st.switch_page("pages/5_전국대시보드.py")
    st.stop()

school = st.session_state.get("school")
if not school:
    st.warning("학교가 선택되지 않았습니다. 점검 시작에서 학교를 선택하세요.")
    if st.button("← 점검 시작", key="dash_noschool_to_start",
                  use_container_width=True):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

hero("DASHBOARD · 내부용",
     "본교 현황",
     f"{school['학교명']} — 저장 즉시 반영 · 식별 유지 (관리자·교육청용)")

sessions = [s for s in list_recent_sessions(limit=200)
            if s["school_code"] == school["정보공시 학교코드"]]

if not sessions:
    empty_state(
        title=f"{school.get('학교명','이 학교')}에 저장된 점검이 없습니다",
        description="AI 점검 후 결과 저장을 누르면 이 화면에 누적·시각화됩니다.",
        action_label="지금 점검 시작",
        action_target="pages/1_점검시작.py",
    )
    st.stop()

df = pd.DataFrame(sessions)
df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.sort_values("timestamp_dt")

latest = df.iloc[-1]
total = len(df)
avg_score = df["score"].mean()
grade_dist = df["grade"].value_counts().to_dict()
spaces_count = df["space_type"].nunique()

# ─────────────────────────────────────────
# 데스크톱: 좌(KPI 4개 세로) | 우(차트 2개 세로)
# 모바일: 자동 세로 스택
# ─────────────────────────────────────────
left_col, right_col = st.columns([1, 2], gap="large")

with left_col:
    section("01", "누적 통계")
    st.metric("누적 점검 횟수", f"{total}회")
    st.metric("평균 점수", f"{avg_score:.1f}점")
    st.metric("점검된 공간 유형", f"{spaces_count}종")
    st.metric("최근 점검일", latest["timestamp"][:10] if latest["timestamp"] else "-")

    st.markdown(
        "<div style='margin-top:24px; padding:14px; background:#FAFAFA; "
        "border:1px solid #E5E5E8; border-radius:6px; font-size:12px; "
        "line-height:1.6; color:#6B6B70;'>"
        "이 화면은 <b>대시보드 A — 실시간(내부)</b>입니다. "
        "공공데이터 환원 분기 갱신 화면은 <b>전국 대시보드</b>를 보세요."
        "</div>",
        unsafe_allow_html=True,
    )

with right_col:
    section("02", "점수 추이", "공간별 시계열 — 80점 B등급 기준선")
    # 4-2 수정: 기록이 1건뿐이면 차트 대신 요약 텍스트 (점 1개 차트는 정보가 없음)
    if len(df) == 1:
        only = df.iloc[0]
        st.markdown(
            f"<div style='border:1px solid #E5E5E8;border-radius:8px;padding:18px 22px;"
            f"background:#FAFAFA;'>"
            f"<div style='font-size:12px;letter-spacing:0.2em;color:#6B6B70;margin-bottom:8px;'>"
            f"첫 점검 결과</div>"
            f"<div style='font-size:15px;color:#0A0A0B;line-height:1.7;'>"
            f"<b>{only['space_type']}</b>"
            f" · <b>{only['score']:.1f}점</b> ({only['grade']}등급)"
            f" · {only['timestamp'][:16].replace('T',' ')}"
            f"</div>"
            f"<div style='margin-top:8px;font-size:12px;color:#9A9A9F;'>"
            f"※ 시계열 차트는 점검이 2회 이상 누적되면 표시됩니다."
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        fig1 = px.line(
            df, x="timestamp_dt", y="score",
            color="space_type", markers=True,
            labels={"timestamp_dt": "점검 일시", "score": "안전 점수", "space_type": "공간"},
        )
        fig1.add_hline(y=80, line_dash="dash", line_color="#4CAF50",
                        annotation_text="B 등급")
        fig1.add_hline(y=60, line_dash="dash", line_color="#FFC107",
                        annotation_text="D 등급")
        fig1.update_layout(height=320, margin=dict(l=20, r=20, t=10, b=20),
                           paper_bgcolor="#FFF", plot_bgcolor="#FFF")
        st.plotly_chart(fig1, use_container_width=True)

    # 공간 유형별 + 등급 분포 (우측 안에서 좌-우 분할)
    sub_a, sub_b = st.columns(2, gap="medium")

    with sub_a:
        st.markdown("<div class='sl-h' style='font-size:15px; "
                    "margin:18px 0 6px 0;'>공간 유형별 평균</div>",
                    unsafe_allow_html=True)
        space_df = df.groupby("space_type").agg(
            평균점수=("score", "mean"),
        ).reset_index().sort_values("평균점수", ascending=True)
        fig2 = px.bar(space_df, x="평균점수", y="space_type", orientation="h",
                      text="평균점수", color="평균점수",
                      color_continuous_scale=["#D50000", "#FFC107", "#4CAF50"],
                      range_x=[0, 100])
        fig2.update_traces(texttemplate="%{text:.1f}")
        fig2.update_layout(height=260, margin=dict(l=20, r=20, t=10, b=20),
                            coloraxis_showscale=False, yaxis_title=None)
        st.plotly_chart(fig2, use_container_width=True)

    with sub_b:
        st.markdown("<div class='sl-h' style='font-size:15px; "
                    "margin:18px 0 6px 0;'>등급 분포</div>",
                    unsafe_allow_html=True)
        grade_df = pd.DataFrame([{"등급": g, "건수": c} for g, c in grade_dist.items()])
        fig3 = px.pie(grade_df, names="등급", values="건수",
                      color="등급",
                      color_discrete_map={"A": "#4CAF50", "B": "#8BC34A",
                                           "C": "#FFC107", "D": "#FF9800",
                                           "E": "#D50000"})
        fig3.update_layout(height=260, margin=dict(l=20, r=20, t=10, b=20))
        st.plotly_chart(fig3, use_container_width=True)

# ─────────────────────────────────────────
# 풀폭: 점검 이력 표
# ─────────────────────────────────────────
divider()
section("03", "전체 점검 이력")
table = df[["timestamp", "space_type", "space_nickname", "score", "grade", "session_id"]].copy()
table.columns = ["점검일시", "공간 유형", "별칭", "점수", "등급", "세션 ID"]
table = table.sort_values("점검일시", ascending=False)
st.dataframe(table, use_container_width=True, hide_index=True, height=320)
