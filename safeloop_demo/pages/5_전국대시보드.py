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
# 17개 시도 대표 좌표 (정부 행정구역 중심 근사값) — 지도 시각화용
# ─────────────────────────────────────────
SIDO_COORDS = {
    "서울특별시교육청": (37.5665, 126.9780),
    "부산광역시교육청": (35.1796, 129.0756),
    "대구광역시교육청": (35.8714, 128.6014),
    "인천광역시교육청": (37.4563, 126.7052),
    "광주광역시교육청": (35.1595, 126.8526),
    "대전광역시교육청": (36.3504, 127.3845),
    "울산광역시교육청": (35.5384, 129.3114),
    "세종특별자치시교육청": (36.4800, 127.2890),
    "경기도교육청":       (37.4138, 127.5183),
    "강원특별자치도교육청": (37.8228, 128.1555),
    "충청북도교육청":     (36.6357, 127.4917),
    "충청남도교육청":     (36.5184, 126.8000),
    "전북특별자치도교육청": (35.7175, 127.1530),
    "전라남도교육청":     (34.8679, 126.9910),
    "경상북도교육청":     (36.4919, 128.8889),
    "경상남도교육청":     (35.4606, 128.2132),
    "제주특별자치도교육청": (33.4996, 126.5312),
}

# ─────────────────────────────────────────
# 01 어떤 학교를 볼까? — 시도 다중선택 + 학교급/설립
# ─────────────────────────────────────────
divider()
section("01", "필터",
        "시도는 2~5개까지 비교 가능 · 선택 없으면 전국 집계")

f_col_a, f_col_b = st.columns([2, 1])
with f_col_a:
    all_sidos = sorted(master["시도교육청"].dropna().unique().tolist())
    sel_sidos = st.multiselect(
        "시도교육청 (최대 5개까지 비교)",
        options=all_sidos,
        max_selections=5,
        key="flt_sidos",
        help="1개: 상세 보기 · 2~5개: 나란히 비교",
    )
with f_col_b:
    levels = ["(전체)"] + sorted(master["학교급"].dropna().unique().tolist())
    sel_level = st.selectbox("학교급", levels, key="flt_level")

# 필터 적용
subset = master.copy()
hr_filtered = hr.copy()
if sel_sidos:
    subset = subset[subset["시도교육청"].isin(sel_sidos)]
    hr_filtered = hr_filtered[hr_filtered["시도교육청"].isin(sel_sidos)]
if sel_level != "(전체)":
    subset = subset[subset["학교급"] == sel_level]
    hr_filtered = hr_filtered[hr_filtered["학교급"] == sel_level]

# 필터 요약
if sel_sidos:
    sido_desc = " · ".join(f"**{s.replace('교육청','')}**" for s in sel_sidos)
else:
    sido_desc = "**전국**"
filter_desc = sido_desc + (f" · **{sel_level}**" if sel_level != "(전체)" else "")
ratio_now = (len(hr_filtered) / len(subset) * 100) if len(subset) else 0

st.markdown(
    f"<div style='border:1px solid #E5E5E8;border-left:3px solid #D50000;"
    f"background:#FAFAFA;border-radius:6px;padding:12px 16px;margin:10px 0;"
    f"font-size:14px;line-height:1.7;'>"
    f"현재 보고 있는 데이터: {filter_desc} 과학실 보유 학교 "
    f"<b>{len(subset):,}개교</b> 중 "
    f"<b style='color:#D50000;'>{len(hr_filtered):,}개교 ({ratio_now:.1f}%)</b> "
    f"가 고위험군입니다."
    f"</div>",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────
# 02 시도별 고위험 비율 — 항상 17개 시도 가로 막대 + 선택 시도 강조
# ─────────────────────────────────────────
divider()
section("02", "시도별 고위험 비율 비교",
        "선택한 시도는 빨간색 · 나머지는 회색 (필터 조건 반영)")

# 학교급 필터 적용한 상태에서 시도별 재계산 (시도 멀티셀렉트는 강조용으로만 사용)
subset_level = master.copy()
hr_level = hr.copy()
if sel_level != "(전체)":
    subset_level = subset_level[subset_level["학교급"] == sel_level]
    hr_level = hr_level[hr_level["학교급"] == sel_level]

by_sido = (
    subset_level.groupby("시도교육청").size().reset_index(name="전체")
    .merge(hr_level.groupby("시도교육청").size().reset_index(name="고위험"),
            on="시도교육청", how="left").fillna(0)
)
by_sido["고위험 비율(%)"] = (
    by_sido["고위험"] / by_sido["전체"].replace(0, 1) * 100
).round(1)
by_sido["선택"] = by_sido["시도교육청"].isin(sel_sidos) if sel_sidos else True
by_sido = by_sido.sort_values("고위험 비율(%)", ascending=True)

fig_bar = px.bar(
    by_sido, x="고위험 비율(%)", y="시도교육청", orientation="h",
    text="고위험 비율(%)",
    color="선택" if sel_sidos else None,
    color_discrete_map={True: "#D50000", False: "#D1D1D4"} if sel_sidos else None,
    hover_data=["전체", "고위험"],
)
fig_bar.update_traces(texttemplate="%{text:.1f}%")
fig_bar.update_layout(
    height=460, margin=dict(l=20, r=20, t=10, b=20),
    yaxis_title=None, showlegend=False,
    paper_bgcolor="#FFF", plot_bgcolor="#FFF",
)
st.plotly_chart(fig_bar, use_container_width=True)

# ─────────────────────────────────────────
# 03 지도 시각화 — 17개 시도 버블 지도 (고위험 비율=색, 고위험 수=크기)
# ─────────────────────────────────────────
divider()
section("03", "지도에서 한눈에 보기",
        "버블 크기 = 고위험 학교 수 · 색 = 고위험 비율(%) · 호버로 상세")

map_df = by_sido.copy()
map_df["lat"] = map_df["시도교육청"].map(lambda s: SIDO_COORDS.get(s, (None, None))[0])
map_df["lon"] = map_df["시도교육청"].map(lambda s: SIDO_COORDS.get(s, (None, None))[1])
map_df = map_df.dropna(subset=["lat", "lon"])

fig_map = px.scatter_mapbox(
    map_df,
    lat="lat", lon="lon",
    size="고위험",
    color="고위험 비율(%)",
    color_continuous_scale=["#4CAF50", "#FFC107", "#D50000"],
    size_max=45,
    zoom=5.8,
    center={"lat": 36.3, "lon": 127.8},
    hover_name="시도교육청",
    hover_data={"전체": True, "고위험": True, "고위험 비율(%)": True,
                  "lat": False, "lon": False},
    mapbox_style="open-street-map",
    height=520,
)
fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0))
st.plotly_chart(fig_map, use_container_width=True)
st.caption(
    "※ 좌표는 각 시도 행정구역 중심 근사값 · 클러스터링이 아닌 시도 단위 요약입니다. "
    "지도 상단의 + / − 또는 드래그로 확대·이동 가능."
)

# ─────────────────────────────────────────
# 04 선택 시도 비교 테이블 (2개 이상 선택 시)
# ─────────────────────────────────────────
if sel_sidos and len(sel_sidos) >= 2:
    divider()
    section("04", "선택 시도 비교 테이블",
            f"{len(sel_sidos)}개 시도 — 숫자로 한 번 더 확인")
    cmp_df = by_sido[by_sido["시도교육청"].isin(sel_sidos)].copy()
    cmp_df = cmp_df[["시도교육청", "전체", "고위험", "고위험 비율(%)"]]
    cmp_df.columns = ["시도교육청", "전체 학교 수", "고위험 학교 수", "고위험 비율(%)"]
    cmp_df = cmp_df.sort_values("고위험 비율(%)", ascending=False).reset_index(drop=True)
    st.dataframe(cmp_df, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────
# 풀폭: 고위험군 통계 요약 (개별 학교 리스트는 제거 — 공공 대시보드 취지상 부적절)
# ─────────────────────────────────────────
divider()
_risk_sec = "05" if (sel_sidos and len(sel_sidos) >= 2) else "04"
section(_risk_sec, "고위험군 위험도 분포",
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
_sens_sec = "06" if (sel_sidos and len(sel_sidos) >= 2) else "05"
section(_sens_sec, "모델 신뢰도 (참고)",
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
