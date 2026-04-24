"""
대시보드 B — 전국 공공데이터 현황 (Stage 1).

공공데이터포털 환원분을 소스로 하는 공개용 대시보드.
학교명은 가명(학교_00001)으로 표시, 시도·학교급·위험등급 필터 제공.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.data_loader import (
    load_cluster_summary,
    load_high_risk,
    load_master,
    load_sensitivity,
    load_sido_summary,
)
from modules.session import ensure_state
from modules.ui import apply_theme, divider, hero, render_sidebar, section

st.set_page_config(page_title="전국 대시보드 · SafeLoop", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="expanded")
apply_theme()
ensure_state()
render_sidebar(active_key="national_dash")

hero("DASHBOARD · 공공용",
     "전국 대시보드",
     "공공데이터포털에 환원된 학교 안전 지표 — 집계만 공개, 개별 학교는 비공개.")

try:
    master = load_master()
    sido_sum = load_sido_summary()
    cluster = load_cluster_summary()
    sens = load_sensitivity()
    hr = load_high_risk()
except FileNotFoundError as e:
    st.error("📁 공공데이터 CSV가 누락되었습니다.")
    st.markdown(
        f"```\n{e}\n```\n\n"
        "**해결 방법**\n"
        "1. `git pull` 로 최신 데이터 받기\n"
        "2. 또는 `SafeLoop_데모앱_이관세트/data/` 폴더의 CSV를 "
        "`safeloop_demo/data/` 로 복사"
    )
    st.stop()

# ─────────────────────────────────────────
# 한줄 요약 KPI (모든 학교 기준 · 필터 전)
# ─────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("분석 대상 학교", f"{len(master):,}개교",
          help="현재 공공데이터포털에 공개된 전국 과학실 보유 학교 수")
c2.metric("고위험군 학교", f"{len(hr):,}개교",
          help="복합 지표로 산출된 위험도 상위 학교 수")
c3.metric("시도교육청", f"{master['시도교육청'].nunique()}개")
c4.metric("고위험 비율", f"{len(hr) / len(master) * 100:.1f}%",
          help="전체 학교 대비 고위험군 비율")

# ─────────────────────────────────────────
# 01 어떤 학교를 볼까? (필터 간소화 — 시도만)
# ─────────────────────────────────────────
divider()
section("01", "지역 필터",
        "한 번에 하나의 질문만 던지세요 — ‘어느 시도의 어떤 학교급이 가장 위험한가’")

f_col_a, f_col_b, f_col_c = st.columns(3)
with f_col_a:
    sidos = ["(전체)"] + sorted(master["시도교육청"].dropna().unique().tolist())
    sel_sido = st.selectbox("시도교육청", sidos, key="flt_sido",
                              help="선택 시 해당 시도 학교만 집계")
with f_col_b:
    levels = ["(전체)"] + sorted(master["학교급"].dropna().unique().tolist())
    sel_level = st.selectbox("학교급", levels, key="flt_level")
with f_col_c:
    establishment = ["(전체)"] + sorted(master["설립구분"].dropna().unique().tolist())
    sel_est = st.selectbox("설립구분 (국·공·사립)", establishment, key="flt_est")

# 필터 적용
subset = master.copy()
hr_filtered = hr.copy()
if sel_sido != "(전체)":
    subset = subset[subset["시도교육청"] == sel_sido]
    hr_filtered = hr_filtered[hr_filtered["시도교육청"] == sel_sido]
if sel_level != "(전체)":
    subset = subset[subset["학교급"] == sel_level]
    hr_filtered = hr_filtered[hr_filtered["학교급"] == sel_level]
if sel_est != "(전체)":
    subset = subset[subset["설립구분"] == sel_est]
    hr_filtered = hr_filtered[hr_filtered["설립구분"] == sel_est]

# 필터 요약 — 자연스러운 문장으로
filter_desc_parts = []
if sel_sido != "(전체)":
    filter_desc_parts.append(f"**{sel_sido}**")
else:
    filter_desc_parts.append("**전국**")
if sel_level != "(전체)":
    filter_desc_parts.append(f"**{sel_level}**")
if sel_est != "(전체)":
    filter_desc_parts.append(f"**{sel_est}**")
filter_desc = " · ".join(filter_desc_parts)

ratio_now = (len(hr_filtered) / len(subset) * 100) if len(subset) else 0

st.markdown(
    f"<div style='border:1px solid #E5E5E8;border-left:3px solid #D50000;"
    f"background:#FAFAFA;border-radius:6px;padding:12px 16px;margin:10px 0;"
    f"font-size:14px;line-height:1.7;'>"
    f"현재 보고 있는 데이터: {filter_desc} 의 과학실 보유 학교 "
    f"<b>{len(subset):,}개교</b> 중 "
    f"<b style='color:#D50000;'>{len(hr_filtered):,}개교 ({ratio_now:.1f}%)</b> "
    f"가 고위험군으로 분류됩니다."
    f"</div>",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────
# 02 TOP 10 시도별 비교 (간결하게 한 차트만)
# ─────────────────────────────────────────
divider()
section("02", "시도별 고위험 비율 TOP 10",
        "선택한 필터 조건에서 — 가로 막대 하나로 순위를 한눈에")

if sel_sido != "(전체)":
    # 단일 시도 → 시도별 차트 대신 학교급 비교로 대체
    st.caption(f"💡 단일 시도({sel_sido}) 선택 — 학교급별 고위험 비율로 대체 표시")
    by_level = (
        subset.groupby("학교급").size().reset_index(name="전체")
        .merge(hr_filtered.groupby("학교급").size().reset_index(name="고위험"),
                on="학교급", how="left").fillna(0)
    )
    by_level["고위험 비율(%)"] = (by_level["고위험"] / by_level["전체"].replace(0, 1) * 100).round(1)
    by_level = by_level.sort_values("고위험 비율(%)", ascending=True)
    fig_main = px.bar(
        by_level, x="고위험 비율(%)", y="학교급", orientation="h",
        text="고위험 비율(%)",
        color="고위험 비율(%)",
        color_continuous_scale=["#4CAF50", "#FFC107", "#D50000"],
        range_x=[0, 100],
    )
    fig_main.update_traces(texttemplate="%{text:.1f}%")
else:
    # 전국 — 시도별 TOP 10
    by_sido = (
        subset.groupby("시도교육청").size().reset_index(name="전체")
        .merge(hr_filtered.groupby("시도교육청").size().reset_index(name="고위험"),
                on="시도교육청", how="left").fillna(0)
    )
    by_sido["고위험 비율(%)"] = (by_sido["고위험"] / by_sido["전체"].replace(0, 1) * 100).round(1)
    by_sido = by_sido.sort_values("고위험 비율(%)", ascending=False).head(10) \
        .sort_values("고위험 비율(%)", ascending=True)
    fig_main = px.bar(
        by_sido, x="고위험 비율(%)", y="시도교육청", orientation="h",
        text="고위험 비율(%)",
        color="고위험 비율(%)",
        color_continuous_scale=["#4CAF50", "#FFC107", "#D50000"],
        range_x=[0, max(by_sido["고위험 비율(%)"].max() + 3, 20)],
    )
    fig_main.update_traces(texttemplate="%{text:.1f}%")

fig_main.update_layout(
    height=360, margin=dict(l=20, r=20, t=10, b=20),
    coloraxis_showscale=False, yaxis_title=None,
    paper_bgcolor="#FFF", plot_bgcolor="#FFF",
)
st.plotly_chart(fig_main, use_container_width=True)

# ─────────────────────────────────────────
# 03 설립구분별 위험도 — 간단한 도넛 + 설명
# ─────────────────────────────────────────
divider()
section("03", "설립구분별 고위험 분포",
        "국·공·사립 중 어디에 고위험이 많이 몰려 있을까")

est_sum = (
    hr_filtered.groupby("설립구분").size().reset_index(name="고위험 수")
    .sort_values("고위험 수", ascending=False)
)
if len(est_sum):
    col_dn, col_exp = st.columns([2, 3])
    with col_dn:
        fig_dn = px.pie(est_sum, values="고위험 수", names="설립구분", hole=0.55,
                         color_discrete_sequence=["#D50000", "#FFC107", "#9A9A9F", "#4CAF50"])
        fig_dn.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10),
                              showlegend=True,
                              legend=dict(orientation="h", yanchor="bottom", y=-0.15))
        st.plotly_chart(fig_dn, use_container_width=True)
    with col_exp:
        top_est = est_sum.iloc[0]
        other_total = est_sum["고위험 수"].sum() - top_est["고위험 수"]
        st.markdown(
            f"<div style='padding:16px 0;font-size:14px;line-height:1.8;'>"
            f"• 고위험군의 <b style='color:#D50000;'>{top_est['고위험 수']:,}개</b> "
            f"({top_est['고위험 수']/est_sum['고위험 수'].sum()*100:.0f}%)가 "
            f"<b>{top_est['설립구분']}</b> 에 집중<br>"
            f"• 나머지 {other_total:,}개는 다른 설립구분에 분산<br>"
            f"<span style='color:#6B6B70;font-size:12px;'>※ 비율은 필터 조건 내에서 "
            f"계산됩니다. 설립구분 필터 적용 시 해당 구분만 표시됩니다.</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
else:
    st.info("선택한 필터 조건에 해당하는 고위험 학교가 없습니다.")

# ─────────────────────────────────────────
# 풀폭: 고위험군 통계 요약 (개별 학교 리스트는 제거 — 공공 대시보드 취지상 부적절)
# ─────────────────────────────────────────
divider()
section("04", "고위험군 위험도 분포",
        "현재 필터 조건의 고위험 학교들이 얼마나 심각한지 한눈에")

if len(hr_filtered):
    sum_col1, sum_col2, sum_col3 = st.columns(3)
    sum_col1.metric("필터 내 고위험 학교 수", f"{len(hr_filtered):,}개교")
    sum_col2.metric("평균 위험도 점수",
                     f"{hr_filtered['위험도_점수'].mean():.1f}")
    sum_col3.metric("최고 위험도",
                     f"{hr_filtered['위험도_점수'].max():.1f}")

    # 위험도 점수 히스토그램 — 어느 구간에 많이 몰려 있는지
    fig_hist = px.histogram(
        hr_filtered, x="위험도_점수", nbins=20,
        color_discrete_sequence=["#D50000"],
        labels={"위험도_점수": "위험도 점수 (높을수록 심각)",
                 "count": "학교 수"},
    )
    fig_hist.update_layout(height=240, margin=dict(l=20, r=20, t=10, b=40),
                            bargap=0.05,
                            paper_bgcolor="#FFF", plot_bgcolor="#FAFAFA",
                            yaxis_title="학교 수")
    st.plotly_chart(fig_hist, use_container_width=True)
else:
    st.info("선택한 필터 조건에 해당하는 고위험 학교가 없습니다.")

st.caption(
    "※ **개별 학교명은 공개되지 않습니다** — 고위험 판정은 현장 검증 전 선별 지표이며, "
    "공개 대시보드에서의 학교별 식별은 지원 대상 학교에 불이익이 될 수 있습니다. "
    "실제 정책 집행은 교육청 내부 권한으로 별도 채널에서 이루어집니다."
)

# ─────────────────────────────────────────
# 05 신뢰도 — 민감도 (고급 정보로 접어두기)
# ─────────────────────────────────────────
divider()
section("05", "모델 신뢰도 (참고)",
        "가중치를 ±20% 변경해도 판정이 얼마나 바뀌지 않는지 — '이 결과를 믿어도 되는가'")
with st.expander("📊 민감도 상세 보기 (고급)", expanded=False):
    st.caption(
        "가중치를 각기 다르게 넣어봐도 고위험 학교 판정의 **85% 이상이 유지**되면 분석이 견고하다는 뜻입니다. "
        "아래 점들이 y=100 에 가까울수록 결과가 안정적입니다."
    )
    fig4 = px.scatter(sens, x="dm(%)", y="overlap(%)",
                      color="dd(%)", size="jaccard",
                      labels={"dm(%)": "미관리 가중치 변화 폭",
                               "overlap(%)": "판정 유지율(%)",
                               "dd(%)": "경과일 가중치 변화",
                               "jaccard": "자카드 일치도"})
    fig4.update_layout(height=320, margin=dict(l=20, r=20, t=20, b=20),
                        yaxis_range=[80, 102])
    st.plotly_chart(fig4, use_container_width=True)

st.divider()
st.caption(
    "※ 이 페이지는 대시보드 B — 공공데이터 기반 전국 대시보드입니다. "
    "본교 실시간 대시보드는 사이드바 **본교 현황** 메뉴에서 확인하세요. "
    "갱신 주기: 공공데이터포털 환원 주기(분기 1회)에 따름."
)
