"""
정책 시뮬레이터 — Stage 4 보강.

위험군 526개교에 예산을 X억 투입하면:
  - 몇 개교가 등급 상승 가능한가
  - 평균 안전 점수가 얼마나 오르나
  - 카테고리별 우선 투자 순위는

핵심서사상 예산은 부수 요소이지만, 교육청 의사결정용 도구로 갖춰두면 완성도가 올라간다.
모델은 가정 기반 단순 근사식 — 실제 운영 시 회귀 모델로 교체.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.data_loader import load_high_risk
from modules.laws import LAW_BASIS, CATEGORIES
from modules.session import ensure_state
from modules.ui import apply_theme, divider, hero, render_sidebar, section

st.set_page_config(page_title="정책 시뮬레이터 · SafeLoop", page_icon="/",
                   layout="wide", initial_sidebar_state="expanded")
apply_theme()
ensure_state()
render_sidebar(active_key="policy")

hero("STAGE 04 EXTENSION", "정책 시뮬레이터",
     "위험군에 예산을 투입했을 때 안전도 변화를 추정합니다. (가정 기반 단순 근사)")

# 데이터
hr = load_high_risk()

# ─────────────────────────────────────────
# 가정 파라미터
# ─────────────────────────────────────────
# ─────────────────────────────────────────
# 데스크톱: 좌(슬라이더 + 가정) | 우(결과 + 차트)
# ─────────────────────────────────────────
control_col, result_col = st.columns([1, 2], gap="large")

with control_col:
    section("01", "투자 가정", "조정 가능한 파라미터")

    budget_eok = st.slider("총 투자 예산 (억 원)", 1, 500, 50, step=1)
    cost_per_school = st.number_input(
        "학교당 평균 개선 비용 (만 원)",
        min_value=100, max_value=10000, value=1500, step=100,
    )
    score_lift_per_unit = st.number_input(
        "1천만 원당 안전 점수 상승 (점)",
        min_value=0.1, max_value=5.0, value=1.2, step=0.1,
    )

    target_pool = st.radio(
        "투자 대상",
        ["S1 위험군 526교 우선 (위험도 높은 순)",
         "S1 위험군 무작위",
         "S1 + 일반 학교 전체 무작위"],
    )

    st.markdown(
        "<div style='margin-top:14px; padding:12px; background:#FAFAFA; "
        "border:1px solid #E5E5E8; border-radius:6px; font-size:11px; "
        "line-height:1.5; color:#6B6B70;'>"
        "단순 선형 가정 모델입니다. 실제 운영 시 환원 데이터로 회귀 분석 모델로 대체."
        "</div>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────
# 시뮬레이션 (control_col 입력 → 우측에서 결과 렌더)
# ─────────────────────────────────────────
budget_won = budget_eok * 100_000_000
cost_won = cost_per_school * 10_000
n_schools_eligible = int(budget_won // cost_won)

if target_pool.startswith("S1 위험군 526교 우선"):
    targets = hr.sort_values("위험도_점수", ascending=False).head(n_schools_eligible)
elif target_pool.startswith("S1 위험군 무작위"):
    targets = hr.sample(min(n_schools_eligible, len(hr)), random_state=42)
else:
    pool = hr.copy()
    targets = pool.sample(min(n_schools_eligible, len(pool)), random_state=42)

lift_per_school = (cost_won / 10_000_000) * score_lift_per_unit
_RNG_SIM = np.random.default_rng(0)
noise = _RNG_SIM.uniform(0.7, 1.2, size=len(targets))
targets = targets.copy()
targets["before_score"] = 100 - targets["위험도_점수"]
targets["after_score"] = (targets["before_score"] + lift_per_school * noise).clip(upper=100)
targets["등급_변화"] = targets["after_score"] // 10 * 10 - targets["before_score"] // 10 * 10

avg_before = targets["before_score"].mean() if len(targets) else 0
avg_after = targets["after_score"].mean() if len(targets) else 0

with result_col:
    section("02", "예상 결과")
    c1, c2 = st.columns(2)
    c1.metric("개선 가능 학교", f"{len(targets):,}개")
    c2.metric("총 사용 예산", f"{cost_won * len(targets) / 1e8:.1f}억",
              delta=f"잔여 {(budget_won - cost_won * len(targets)) / 1e8:.1f}억")
    c3, c4 = st.columns(2)
    c3.metric("평균 점수 변화", f"{avg_before:.1f} → {avg_after:.1f}",
              delta=f"+{avg_after - avg_before:.1f}")
    grade_up = int(((targets["after_score"] // 10) > (targets["before_score"] // 10)).sum())
    c4.metric("등급 상승 학교", f"{grade_up:,}개")

    if len(targets) == 0:
        st.warning("이 예산으로는 개선이 불가합니다. 예산을 늘리거나 학교당 비용을 낮춰주세요.")
        st.stop()

    st.markdown("<div class='sl-h' style='font-size:15px;margin:18px 0 6px;'>"
                "점수 분포 — Before vs After</div>", unsafe_allow_html=True)
    hist = pd.DataFrame({
        "Before": targets["before_score"],
        "After": targets["after_score"],
    })
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=hist["Before"], name="투자 전", marker_color="#9A9A9F",
                                opacity=0.7, nbinsx=30))
    fig.add_trace(go.Histogram(x=hist["After"], name="투자 후", marker_color="#D50000",
                                opacity=0.7, nbinsx=30))
    fig.update_layout(barmode="overlay", height=300,
                      xaxis_title="안전 점수", yaxis_title="학교 수",
                      margin=dict(l=20, r=20, t=10, b=20),
                      paper_bgcolor="#FFF", plot_bgcolor="#FFF")
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────
# 카테고리별 투자 우선순위 추천
# ─────────────────────────────────────────
divider()
section("04", "카테고리별 투자 우선순위", "법령 가중치 + 평균 부재율을 결합한 단순 우선순위")

# 카테고리 가중치 합산
cat_weight = {}
for c in CATEGORIES:
    cat_weight[c] = sum(info["weight"] for info in LAW_BASIS.values() if info["category"] == c)

# 가상의 카테고리별 부재율 (시드 고정으로 매 렌더 동일)
_RNG = np.random.default_rng(42)
cat_absent_rate = {c: float(_RNG.uniform(0.2, 0.7)) for c in CATEGORIES}

priority = pd.DataFrame([
    {"카테고리": c,
     "가중치 합계": cat_weight[c],
     "평균 부재율": f"{cat_absent_rate[c]*100:.0f}%",
     "우선순위 점수": cat_weight[c] * cat_absent_rate[c]}
    for c in CATEGORIES
]).sort_values("우선순위 점수", ascending=False)

st.dataframe(priority, use_container_width=True, hide_index=True)

fig2 = px.bar(priority, x="우선순위 점수", y="카테고리", orientation="h",
              color="우선순위 점수", color_continuous_scale=["#9A9A9F", "#D50000"])
fig2.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20),
                   yaxis={"categoryorder": "total ascending"},
                   coloraxis_showscale=False)
st.plotly_chart(fig2, use_container_width=True)

# ─────────────────────────────────────────
# 면책
# ─────────────────────────────────────────
divider()
st.caption(
    "본 시뮬레이터는 단순 선형 가정에 기반한 시범 모델입니다. "
    "실제 운영 시 환원된 점검 데이터로 회귀 분석·정책 효과 측정 모델로 대체됩니다. "
    "예산 편성은 핵심서사상 부수 요소이며, 메인은 데이터 순환·맞춤 점검입니다."
)
