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
    pseudo_school_name,
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
     "공공데이터포털에 환원된 학교 안전 지표 — 학교명은 가명 처리.")

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
# 요약 카드
# ─────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("분석 대상 학교", f"{len(master):,}개교")
c2.metric("고위험군 (S1)", f"{len(hr):,}개교")
c3.metric("시도교육청", f"{master['시도교육청'].nunique()}개")
c4.metric(
    "고위험 비율",
    f"{len(hr) / len(master) * 100:.1f}%",
)

# ─────────────────────────────────────────
# BEFORE / AFTER 토글 (순환 효과 시연)
# ─────────────────────────────────────────
section("01", "순환 고도화 효과", "환원 전/후 해상도 비교")
mode = st.radio(
    "데이터 해상도",
    ["BEFORE — 학교 단위 1지표 (기존 공공데이터)",
     "AFTER — 학교 × 공간 × 항목 세부 (순환 환원 후)"],
    horizontal=True,
    key="before_after",
)

if mode.startswith("BEFORE"):
    st.info(
        "기존 공공데이터는 **학교 단위의 위험도 점수 1개** 수준. "
        "점검 세부 항목·공간별 상태·법령 준수 여부는 파악 불가."
    )
else:
    st.success(
        "AI 점검 결과가 환원되면 **학교 × 공간 유형 × 설비 항목 × 법령 근거**의 "
        "4차원 해상도로 확장. 정책 결정에 활용 가능한 단위로 고도화."
    )

# ─────────────────────────────────────────
# 데스크톱: 좌(필터·요약) | 우(메인 차트들)
# ─────────────────────────────────────────
filter_col, main_col = st.columns([1, 3], gap="large")

with filter_col:
    section("02", "필터")
    sidos = ["(전체)"] + sorted(master["시도교육청"].dropna().unique().tolist())
    sel_sido = st.selectbox("시도교육청", sidos)
    levels = ["(전체)"] + sorted(master["학교급"].dropna().unique().tolist())
    sel_level = st.selectbox("학교급", levels)
    establishment = ["(전체)"] + sorted(master["설립구분"].dropna().unique().tolist())
    sel_est = st.selectbox("설립구분", establishment)

    subset = master.copy()
    if sel_sido != "(전체)":
        subset = subset[subset["시도교육청"] == sel_sido]
    if sel_level != "(전체)":
        subset = subset[subset["학교급"] == sel_level]
    if sel_est != "(전체)":
        subset = subset[subset["설립구분"] == sel_est]

    st.markdown(
        f"<div style='margin-top:14px; padding:12px; background:#FAFAFA; "
        f"border:1px solid #E5E5E8; border-radius:6px;'>"
        f"<div style='font-size:11px; letter-spacing:0.16em; color:#6B6B70;'>"
        f"필터 결과</div>"
        f"<div style='font-size:22px; font-weight:800; color:#0A0A0B;'>"
        f"{len(subset):,}개교</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

with main_col:
    is_after = mode.startswith("AFTER")
    section("03", "시도별 위험도 분포",
            "필터 적용 결과 기반"
            + (" — AFTER: 학교×공간×항목 4차원 가상 시뮬" if is_after else ""))

    # 필터된 subset에서 시도별 집계 재계산
    if sel_sido != "(전체)":
        # 단일 시도면 시도별 분포 무의미 → 시군구별로 표시
        st.caption(f"필터: {sel_sido} — 단일 시도이므로 학교급별 분포로 대체")
        sido_view = subset.groupby("학교급").size().reset_index(name="학교수")
        fig1 = px.bar(sido_view, x="학교급", y="학교수", text="학교수",
                      color="학교수", color_continuous_scale=["#4CAF50", "#D50000"])
    else:
        sido_filtered = sido_sum.copy()
        if sel_level != "(전체)":
            # 학교급 필터는 sido_sum에 반영 어려움 → master 기반 재집계
            level_grouped = subset.groupby("시도교육청").size().reset_index(name="학교수")
            high_risk_filtered = hr.copy()
            if sel_level != "(전체)":
                high_risk_filtered = high_risk_filtered[high_risk_filtered["학교급"] == sel_level]
            if sel_est != "(전체)":
                high_risk_filtered = high_risk_filtered[high_risk_filtered["설립구분"] == sel_est]
            risk_grouped = high_risk_filtered.groupby("시도교육청").size().reset_index(name="고위험_학교수")
            merged_sido = level_grouped.merge(risk_grouped, on="시도교육청", how="left").fillna(0)
            merged_sido["고위험_비율"] = (merged_sido["고위험_학교수"] / merged_sido["학교수"] * 100).round(1)
            sido_filtered = merged_sido.sort_values("고위험_비율", ascending=False)
        else:
            sido_filtered = sido_sum.sort_values("고위험_비율", ascending=False)

        # AFTER 모드: 차트 제목/색상 강조로 차이 표현
        bar_scale = (["#1B8A3A", "#FFC107", "#D50000"] if is_after
                     else ["#4CAF50", "#FFC107", "#D50000"])
        fig1 = px.bar(
            sido_filtered, x="시도교육청", y="고위험_학교수",
            color="고위험_비율",
            color_continuous_scale=bar_scale,
            text="고위험_학교수",
            labels={"고위험_학교수": "고위험 학교 수", "고위험_비율": "고위험 비율(%)"},
        )
    fig1.update_layout(height=320, margin=dict(l=20, r=20, t=10, b=40),
                       xaxis_tickangle=-35,
                       paper_bgcolor="#FFF", plot_bgcolor="#FFF")
    st.plotly_chart(fig1, use_container_width=True)

    sub_a, sub_b = st.columns(2, gap="medium")
    with sub_a:
        st.markdown("<div class='sl-h' style='font-size:15px;margin:18px 0 6px;'>"
                    "학교급별 위험군 구성 (필터 적용)</div>", unsafe_allow_html=True)
        # 필터된 hr 사용
        hr_filtered = hr.copy()
        if sel_sido != "(전체)":
            hr_filtered = hr_filtered[hr_filtered["시도교육청"] == sel_sido]
        if sel_est != "(전체)":
            hr_filtered = hr_filtered[hr_filtered["설립구분"] == sel_est]
        level_risk = hr_filtered.groupby("학교급").size().reset_index(name="고위험 수")
        level_total = subset.groupby("학교급").size().reset_index(name="전체")
        merged = level_risk.merge(level_total, on="학교급", how="outer").fillna(0)
        merged["비율(%)"] = (merged["고위험 수"] / merged["전체"].replace(0, 1) * 100).round(1)
        fig2 = px.bar(merged, x="학교급", y=["고위험 수", "전체"], barmode="group",
                      color_discrete_map={"고위험 수": "#D50000", "전체": "#C0C0C0"})
        fig2.update_layout(height=240, margin=dict(l=20, r=20, t=10, b=20))
        st.plotly_chart(fig2, use_container_width=True)

    with sub_b:
        title = ("학교×공간 클러스터 (AFTER)" if is_after else "K-Means 3 클러스터")
        st.markdown(f"<div class='sl-h' style='font-size:15px;margin:18px 0 6px;'>"
                    f"{title}</div>", unsafe_allow_html=True)
        if is_after:
            # AFTER: 가상의 공간×설비 카테고리 시뮬
            after_data = pd.DataFrame([
                {"카테고리": "비상 대응 부재", "건수": int(len(hr) * 0.42)},
                {"카테고리": "환기·배기 미흡", "건수": int(len(hr) * 0.31)},
                {"카테고리": "보관·격리 부적합", "건수": int(len(hr) * 0.27)},
                {"카테고리": "감지·경보 누락", "건수": int(len(hr) * 0.18)},
            ])
            fig3 = px.bar(after_data, x="카테고리", y="건수", text="건수",
                          color="건수", color_continuous_scale=["#FFC107", "#D50000"])
        else:
            fig3 = px.bar(cluster, x="위험군", y="학교수", text="학교수",
                          color="위험군",
                          color_discrete_map={"고위험": "#D50000", "주의": "#FFC107",
                                              "양호": "#4CAF50"})
        fig3.update_layout(height=240, margin=dict(l=20, r=20, t=10, b=20),
                           coloraxis_showscale=False)
        st.plotly_chart(fig3, use_container_width=True)

# ─────────────────────────────────────────
# 고위험군 테이블 (익명화)
# ─────────────────────────────────────────
st.subheader("고위험군 학교 리스트 (공개용 익명 이름)")
st.caption("공공데이터 환원 원칙에 따라 학교명은 가명 처리됩니다.")

display = hr.copy()
if sel_sido != "(전체)":
    display = display[display["시도교육청"] == sel_sido]
display["가명"] = display["정보공시 학교코드"].astype(str).apply(pseudo_school_name)
display = display[["가명", "시도교육청", "학교급", "설립구분", "위험도_점수", "위험군", "지역분류"]]\
    .rename(columns={"위험도_점수": "위험도"})
st.dataframe(display.head(100), use_container_width=True, hide_index=True)
st.caption(f"총 {len(display):,}개교 (상위 100개 표시)")

# ─────────────────────────────────────────
# 민감도
# ─────────────────────────────────────────
st.subheader("가중치 민감도 (±20%)")
st.caption("가중치 변경에도 고위험군 판정의 85% 이상이 유지됨 — 분석의 견고성")
fig4 = px.scatter(sens, x="dm(%)", y="overlap(%)",
                  color="dd(%)", size="jaccard",
                  labels={"dm(%)": "미관리 가중치 변화", "overlap(%)": "중복률",
                          "dd(%)": "경과일 가중치 변화"})
fig4.update_layout(height=340, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig4, use_container_width=True)

st.divider()
st.caption(
    "※ 이 페이지는 **대시보드 B — 공공데이터 기반 전국 대시보드**입니다. "
    "본교 실시간 대시보드는 사이드바 **📊 본교 현황**에서 확인하세요. "
    "갱신 주기: 공공데이터포털 환원 주기(분기 1회)에 따름."
)
