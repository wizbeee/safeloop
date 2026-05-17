"""
대시보드 A — 본교 실시간 현황.

로컬 저장소에 저장된 점검 결과를 즉시 반영.
공공데이터 대시보드(B)와는 달리 익명화·집계 없이 식별 유지로 내부 관리용.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.session import ensure_state
from modules.storage import list_recent_sessions
from modules.ui import (
    apply_theme, divider, empty_state, hero, mobile_pc_hint,
    render_sidebar, section,
)

st.set_page_config(page_title="본교 현황 · SafeLoop", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="auto")
apply_theme()
ensure_state()
render_sidebar(active_key="school_dash")

# 역할 가드 — '본교 현황' 은 학교 담당자 전용
# (교육청·실 담당자는 별도 안내 + 적절 페이지로 유도)
if st.session_state.get("role") == "교육청":
    st.warning(
        "**교육청 담당자 모드** — '본교 현황' 은 학교 담당자가 자신의 학교 데이터를 "
        "확인하는 내부용 화면입니다. 교육청 관점에서는 '전국 대시보드' 를 사용하세요."
    )
    if st.button("전국 대시보드로 이동", key="dash_guard_national",
                  type="primary", width="stretch"):
        st.switch_page("pages/5_전국대시보드.py")
    st.stop()

if st.session_state.get("role") == "실":
    st.warning(
        "**실 담당자 모드** — '본교 현황' 은 학교 단위 통계·이력 화면으로 "
        "학교 담당자 전용입니다. 실 담당자는 본인 점검 흐름(점검 시작 AI 점검 결과 제출)을 사용하세요."
    )
    if st.button("내 점검 시작", key="dash_guard_space",
                  type="primary", width="stretch"):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

school = st.session_state.get("school")
if not school:
    st.warning("학교가 선택되지 않았습니다. 점검 시작에서 학교를 선택하세요.")
    if st.button("점검 시작", key="dash_noschool_to_start",
                  width="stretch"):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

hero("DASHBOARD · 내부용",
     "본교 현황",
     f"{school['학교명']} — 저장 즉시 반영 · 식별 유지 (관리자·교육청용)")

mobile_pc_hint("표·차트가 많아 PC·태블릿 가로 화면에서 더 정확히 읽힙니다")

sessions = [s for s in list_recent_sessions(limit=200)
            if s["school_code"] == school["정보공시 학교코드"]]

if not sessions:
    empty_state(
        title=f"{school.get('학교명','이 학교')}에 저장된 점검이 없습니다",
        description=(
            "AI 점검 후 결과 저장을 누르면 이 화면에 누적·시각화됩니다.\n\n"
            "**처음이라 어떻게 해볼지 모르시겠다면** — 홈으로 돌아가 "
            "**시연 시작**을 눌러보세요. 9개 공간 중 하나를 선택하면 "
            "더미 이미지 7컷 + AI 분석 + 점검표가 자동 진행되어 결과 화면까지 보여줍니다."
        ),
        action_label="지금 점검 시작",
        action_target="pages/1_점검시작.py",
    )
    if st.button("홈으로 돌아가서 시연 시작", width="stretch",
                  key="empty_state_demo_home"):
        st.switch_page("app.py")
    st.stop()

df = pd.DataFrame(sessions)
df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.sort_values("timestamp_dt")

latest = df.iloc[-1]
total = len(df)
avg_score = df["score"].mean()
grade_dist = df["grade"].value_counts().to_dict()
spaces_count = df["space_type"].nunique()

# ─── 재점검 주기 알림 — 마지막 점검 후 경과일 ───
# 교육시설법은 자체 점검을 분기·반기·연 1회 등으로 요구 (학교 정책 따름).
# 90일 경과 시 권장 알림, 180일 시 강한 경고.
import datetime as _dt_remind
_last_dt = pd.to_datetime(latest.get("timestamp"), errors="coerce")
if pd.notna(_last_dt):
    _elapsed = (_dt_remind.datetime.now() - _last_dt.to_pydatetime()).days
    if _elapsed >= 180:
        st.error(
            f"**재점검이 필요합니다** — 마지막 점검 후 **{_elapsed}일 경과** "
            f"(권장: 분기당 1회 = 90일 이내). 즉시 새 점검을 시작하세요."
        )
    elif _elapsed >= 90:
        st.warning(
            f"**재점검 권장** — 마지막 점검 후 **{_elapsed}일 경과**. "
            f"분기당 1회(90일 이내) 점검이 권장됩니다."
        )
    elif _elapsed >= 60:
        st.info(
            f"마지막 점검 후 **{_elapsed}일 경과** — 다음 점검까지 약 "
            f"{max(90 - _elapsed, 0)}일 남았습니다."
        )

# ─────────────────────────────────────────
# 데스크톱: 좌(KPI 4개 세로) | 우(차트 2개 세로)
# 모바일: 자동 세로 스택
# ─────────────────────────────────────────
left_col, right_col = st.columns([1, 2], gap="large")

with left_col:
    section("01", "누적 통계")
    st.metric("누적 점검 횟수", f"{total}회")
    # 본교 평균 vs 전국 평균 비교 (delta 표시)
    from modules.data_loader import estimated_national_safety_score
    _nat = estimated_national_safety_score()
    _nat_mean = _nat.get("mean", 0.0)
    # delta: 본교 - 전국. 양수면 본교가 더 안전, 음수면 평균 미달.
    _delta = round(avg_score - _nat_mean, 1) if _nat_mean else None
    st.metric(
        "본교 평균 점수",
        f"{avg_score:.1f}점",
        delta=(f"{_delta:+.1f}점 vs 전국 평균 {_nat_mean:.1f}점"
               if _delta is not None else None),
        help="전국 평균은 공공데이터 위험도 점수를 0~100 안전 점수로 변환해 산출",
    )
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
        # 전국 평균선 — 본교 vs 전국 즉시 비교
        if _nat_mean:
            fig1.add_hline(
                y=_nat_mean, line_dash="dot", line_color="#0A0A0B",
                annotation_text=f"전국 평균 {_nat_mean:.1f}점",
                annotation_position="bottom left",
            )
        fig1.update_layout(height=320, margin=dict(l=20, r=20, t=10, b=20),
                           paper_bgcolor="#FFF", plot_bgcolor="#FFF")
        st.plotly_chart(fig1, width="stretch")

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
        # 전국 평균 세로선
        if _nat_mean:
            fig2.add_vline(
                x=_nat_mean, line_dash="dot", line_color="#0A0A0B",
                annotation_text=f"전국 {_nat_mean:.1f}",
                annotation_position="top",
            )
        fig2.update_layout(height=260, margin=dict(l=20, r=20, t=10, b=20),
                            coloraxis_showscale=False, yaxis_title=None)
        st.plotly_chart(fig2, width="stretch")

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
        st.plotly_chart(fig3, width="stretch")

# ─────────────────────────────────────────
# 풀폭: 본교 vs 전국 — 시도 평균 + 학교 위치
# ─────────────────────────────────────────
divider()
section("03", "본교 vs 전국 비교", "공공데이터 환원 흐름의 시각화")

_school_code = school.get("정보공시 학교코드", "")
_school_sido = school.get("시도교육청", "")
_nat_school = _nat.get("school_score", {}).get(str(_school_code))
_nat_sido = _nat.get("sido_means", {}).get(_school_sido)

cmp_col1, cmp_col2, cmp_col3 = st.columns(3)
with cmp_col1:
    st.metric(
        "본교 평균 (실시간)",
        f"{avg_score:.1f}점",
        help="로컬 저장소에 누적된 점검 결과의 평균",
    )
with cmp_col2:
    st.metric(
        f"우리 시도 평균 ({_school_sido or '-'})",
        f"{_nat_sido:.1f}점" if _nat_sido is not None else "-",
        delta=(f"{avg_score - _nat_sido:+.1f}"
               if _nat_sido is not None else None),
        help="공공데이터 위험도 점수를 안전 점수로 변환한 시도 평균",
    )
with cmp_col3:
    st.metric(
        "전국 평균",
        f"{_nat_mean:.1f}점" if _nat_mean else "-",
        delta=(f"{avg_score - _nat_mean:+.1f}" if _nat_mean else None),
        help="공공데이터 환원 분기 갱신 — 전국 평균 안전 점수",
    )

# 시도 평균 막대 + 본교 강조 (go 는 파일 상단에 이미 import 됨)
sido_means = _nat.get("sido_means", {})
if sido_means:
    sido_df = pd.DataFrame(
        sorted(sido_means.items(), key=lambda x: x[1], reverse=True),
        columns=["시도교육청", "안전점수_평균"],
    )
    bar_colors = [
        "#D50000" if s == _school_sido else "#9A9A9F"
        for s in sido_df["시도교육청"]
    ]
    fig_sido = go.Figure()
    fig_sido.add_trace(go.Bar(
        y=sido_df["시도교육청"],
        x=sido_df["안전점수_평균"],
        orientation="h",
        marker_color=bar_colors,
        text=sido_df["안전점수_평균"].round(1),
        textposition="outside",
    ))
    # 본교 점수 세로선
    fig_sido.add_vline(
        x=avg_score, line_dash="dash", line_color="#D50000",
        annotation_text=f"본교 {avg_score:.1f}",
        annotation_position="top",
    )
    fig_sido.update_layout(
        title=f"시도별 평균 안전 점수 (본교 시도 = 빨강)",
        xaxis_title="안전 점수 (0~100)",
        yaxis_title=None,
        height=420, margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="#FFF", plot_bgcolor="#FFF",
        showlegend=False,
    )
    st.plotly_chart(fig_sido, width="stretch")

st.caption(
    "**공공데이터 환원 시각화** — 본교 점검은 익명화돼 공공 데이터셋에 합쳐지고, "
    "이 차트는 그 데이터셋을 기반으로 시도별 평균을 산출합니다. "
    "본교 점수(빨강 세로선)와 우리 시도 막대(빨강)를 한눈에 비교하세요."
)


# ─────────────────────────────────────────
# 풀폭: 점검 이력 표
# ─────────────────────────────────────────
divider()
section("04", "전체 점검 이력")
table = df[["timestamp", "space_type", "space_nickname", "score", "grade", "session_id"]].copy()
table.columns = ["점검일시", "공간 유형", "별칭", "점수", "등급", "세션 ID"]
table = table.sort_values("점검일시", ascending=False)
# PC 는 dataframe — 한눈에 다 보이고 정렬·복사 편함.
st.markdown("<div class='sl-table-pc'>", unsafe_allow_html=True)
st.dataframe(table, width="stretch", hide_index=True, height=320)
st.markdown("</div>", unsafe_allow_html=True)

# 모바일은 카드 리스트로 자동 분기 (CSS 미디어쿼리). 표보다 가독성 ↑.
_card_rows = []
for _, _r in table.head(50).iterrows():
    _score_v = _r["점수"]
    _score_disp = f"{_score_v}" if _score_v is not None else "-"
    _nick = _r["별칭"] or "별칭 없음"
    _card_rows.append(
        f"<div class='sl-hist-card'>"
        f"<div class='sl-hist-head'>"
        f"<b>{_r['공간 유형']}</b>"
        f"<span class='sl-hist-score'>{_score_disp}점 · {_r['등급']}</span>"
        f"</div>"
        f"<div class='sl-hist-meta'>{_nick} · {str(_r['점검일시'])[:16]}</div>"
        f"</div>"
    )
st.markdown(
    "<div class='sl-table-mobile'>"
    + "".join(_card_rows)
    + "</div>",
    unsafe_allow_html=True,
)
