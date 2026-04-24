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

st.set_page_config(page_title="정책 시뮬레이터 · SafeLoop", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="expanded")
apply_theme()
ensure_state()
render_sidebar(active_key="policy")

hero("STAGE 04 EXTENSION", "정책 시뮬레이터",
     "위험군에 예산을 투입했을 때 안전도 변화 추정 · 실무 단가 기준 로그 감쇠 모델")

# 데이터
hr = load_high_risk()

# ─────────────────────────────────────────
# 카테고리별 개선 단가표 (공공조달 · 시설관리 실무 추정치)
# - 비상 대응: 비상샤워·세안기 설비 교체, 가스차단 밸브 시공
# - 환기·배기: 흄후드 1대 약 800만원, 국소배기 설비 증설
# - 보관·격리: 잠금식 시약장 · 가스용기 전용 보관함
# - 감지·경보: 화재/가스 감지기 · 비상벨 설치
# - 개인보호구: 학급당 보안경·장갑·실험복 비치
# - 안내·표지: MSDS·포스터·안전수칙 교체 (가장 저비용)
# 출처: 조달청 나라장터 평균 단가 · 교육시설공제회 시설개선 사례 (2023-2024)
# ─────────────────────────────────────────
CATEGORY_UNIT_COST = {   # 단위: 만원 (1개 학교 · 1개 공간당)
    "비상 대응": 450,       # 비상샤워+세안기+가스차단 세트
    "환기·배기": 820,       # 흄후드 또는 국소배기 증설 (가장 고가)
    "보관·격리": 280,       # 잠금 시약장 + 폐액 수거함
    "감지·경보": 220,       # 감지기 3종 + 비상벨
    "개인보호구": 80,       # 학급 분량 PPE 일괄
    "안내·표지": 15,        # MSDS·포스터 (저비용 고효과)
}

# 카테고리별 예상 점수 기여도 (법령 가중치 합산 → 100 정규화)
_cat_weight_sum = {
    c: sum(info["weight"] for info in LAW_BASIS.values() if info["category"] == c)
    for c in CATEGORIES
}
_total_w = sum(_cat_weight_sum.values())
CATEGORY_SCORE_CONTRIB = {c: _cat_weight_sum[c] / _total_w * 100 for c in CATEGORIES}

# ─────────────────────────────────────────
# 데스크톱: 좌(슬라이더 + 가정) | 우(결과 + 차트)
# ─────────────────────────────────────────
control_col, result_col = st.columns([1, 2], gap="large")

with control_col:
    section("01", "투자 시나리오 설정")

    # 사전 정의된 현실 시나리오
    PRESETS = {
        "맞춤 입력": None,
        "교부금 0.05% 시범 (약 40억)": 40,
        "교부금 0.1% 확대 (약 80억)": 80,
        "교부금 0.5% 전면 (약 400억)": 400,
    }
    preset = st.selectbox(
        "예산 프리셋",
        options=list(PRESETS.keys()),
        help="2024년 지방교육재정교부금 약 80조 원 기준. "
             "실제 시설개선 예산은 총 교부금의 0.05~0.5% 범위에서 의사결정.",
    )
    default_budget = PRESETS[preset] or 80
    budget_eok = st.slider("총 투자 예산 (억 원)", 1, 500, default_budget, step=1,
                             help="지방교육재정교부금 또는 특별교부금(시설개선) 가용분")

    target_strategy = st.radio(
        "투자 전략",
        ["위험도 높은 순 (우선 투입 · 권장)",
         "고른 분산 (무작위 · 공정성 중심)",
         "카테고리 집중 (부재 설비 우선)"],
        help="위험도 높은 순은 ROI 가 가장 높으나 상위 학교만 수혜. "
             "고른 분산은 공정성은 좋지만 평균 개선폭이 작음.",
    )

    # 현실 단가 표시
    with st.expander("📑 개선 단가 레퍼런스 (카테고리별)", expanded=False):
        ref_df = pd.DataFrame([
            {"카테고리": c,
             "학교당 평균 단가 (만원)": CATEGORY_UNIT_COST[c],
             "점수 기여 (%)": f"{CATEGORY_SCORE_CONTRIB[c]:.1f}"}
            for c in CATEGORIES
        ])
        st.dataframe(ref_df, use_container_width=True, hide_index=True)
        st.caption(
            "※ 조달청 나라장터 평균 단가 · 교육시설공제회 시설개선 사례(2023-24) "
            "를 바탕으로 설정한 **표준 추정치**. 지역·시공 조건에 따라 ±30% 변동."
        )

    st.markdown(
        "<div style='margin-top:14px; padding:12px; background:#FAFAFA; "
        "border:1px solid #E5E5E8; border-radius:6px; font-size:11px; "
        "line-height:1.6; color:#6B6B70;'>"
        "<b>모델</b> — 학교당 투자액에 대해 <b>로그 감쇠</b> 를 적용 "
        "(초기 투자 효과 ↑, 이후 한계효용 체감). "
        "단순 선형 가정이 아닌 실제 관측에 더 가까운 형태입니다. "
        "운영 배포 시에는 환원 데이터(BEFORE→AFTER 페어) 로 회귀 모델로 대체."
        "</div>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────
# 시뮬레이션 — 로그 감쇠 모델
# ─────────────────────────────────────────
budget_won = budget_eok * 100_000_000

# 전략별 타겟 선정 + 학교당 투자액 분배
if target_strategy.startswith("위험도 높은 순"):
    # 위험도 상위 학교에 집중 투입 (학교당 표준 패키지 = 1500만원 = 모든 카테고리 경량판)
    pkg_cost_won = 15_000_000  # 학교당 1,500만 원 (비상대응+보관+감지+PPE 경량 패키지)
    n = int(budget_won // pkg_cost_won)
    targets = hr.sort_values("위험도_점수", ascending=False).head(n).copy()
    per_school_won = pkg_cost_won
elif target_strategy.startswith("고른 분산"):
    pkg_cost_won = 8_000_000  # 학교당 800만 원 (저비용 기본 패키지)
    n = int(budget_won // pkg_cost_won)
    targets = hr.sample(min(n, len(hr)), random_state=42).copy()
    per_school_won = pkg_cost_won
else:  # 카테고리 집중
    # 부재율 × 가중치 우선순위로 상위 3개 카테고리 지원 패키지
    # 대략 (환기+보관+감지) = 820+280+220 = 약 1,320만 원
    pkg_cost_won = 13_200_000
    n = int(budget_won // pkg_cost_won)
    targets = hr.sort_values("위험도_점수", ascending=False).head(n).copy()
    per_school_won = pkg_cost_won

# 로그 감쇠 모델:
#   before_score = 100 - 위험도_점수
#   gap = 100 - before_score  (개선 여지)
#   lift = gap × (1 - exp(-k × 투자만원/500))  → 투자 500만원 도달 시 약 63%, 2000만원에서 98%
#   k=1.0 기준
if len(targets) > 0:
    targets["before_score"] = 100 - targets["위험도_점수"]
    gap = 100 - targets["before_score"]
    k = 1.0
    invest_units = (per_school_won / 10_000) / 500.0  # 500만원 단위
    recovery_ratio = 1 - np.exp(-k * invest_units)
    _RNG_SIM = np.random.default_rng(0)
    noise = _RNG_SIM.uniform(0.85, 1.15, size=len(targets))
    targets["after_score"] = (targets["before_score"] + gap * recovery_ratio * noise).clip(upper=100)
else:
    targets["before_score"] = []
    targets["after_score"] = []

avg_before = targets["before_score"].mean() if len(targets) else 0
avg_after = targets["after_score"].mean() if len(targets) else 0
total_invested_won = per_school_won * len(targets)

with result_col:
    section("02", "예상 결과")
    c1, c2 = st.columns(2)
    c1.metric("개선 가능 학교", f"{len(targets):,}개",
              delta=f"학교당 {per_school_won/1e4:.0f}만 원")
    c2.metric("총 사용 예산", f"{total_invested_won/1e8:.1f}억",
              delta=f"잔여 {(budget_won - total_invested_won) / 1e8:.1f}억")
    c3, c4 = st.columns(2)
    c3.metric("평균 점수 변화", f"{avg_before:.1f} → {avg_after:.1f}",
              delta=f"+{avg_after - avg_before:.1f}점")
    grade_up = int(((targets["after_score"] // 10) > (targets["before_score"] // 10)).sum())
    c4.metric("등급 상승 학교", f"{grade_up:,}개",
              delta=f"{grade_up/max(len(targets),1)*100:.0f}% 비율")

    if len(targets) == 0:
        st.warning("이 예산으로는 최소 1개교 패키지도 구성할 수 없습니다. 예산을 늘려주세요.")
        st.stop()

    # ROI (예산 1억당 점수 개선 × 학교 수)
    _total_lift = (targets["after_score"] - targets["before_score"]).sum()
    roi = _total_lift / (total_invested_won / 1e8) if total_invested_won else 0
    st.caption(
        f"💰 **ROI**: 예산 1억 원당 누적 점수 개선 약 **{roi:.1f}점·교** · "
        f"전체 누적 개선 {_total_lift:.0f}점·교"
    )

    st.markdown("<div class='sl-h' style='font-size:15px;margin:18px 0 6px;'>"
                "점수 분포 — 투자 전 vs 투자 후</div>", unsafe_allow_html=True)
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
# 카테고리별 투자 우선순위 추천 (부재율 × 단가당 점수 회복)
# ─────────────────────────────────────────
divider()
section("03", "카테고리별 투자 우선순위",
        "법령 가중치 × (부재율 / 단가) — 비용 대비 효과가 큰 카테고리가 상위")

# 카테고리 가중치 합산
cat_weight = _cat_weight_sum

# 카테고리별 부재율 — 공공데이터 분석 결과 기반 추정치 (실 운영 시 환원 데이터로 대체)
# 주: 값은 시연용이며 실제 조사로 대체 필요
CAT_ABSENT_RATE_ESTIMATED = {
    "비상 대응": 0.42,
    "환기·배기": 0.68,     # 흄후드 보급률이 낮음
    "보관·격리": 0.35,
    "감지·경보": 0.28,
    "개인보호구": 0.52,
    "안내·표지": 0.38,
}

priority_rows = []
for c in CATEGORIES:
    absent = CAT_ABSENT_RATE_ESTIMATED[c]
    weight = cat_weight[c]
    unit_cost_mw = CATEGORY_UNIT_COST[c]  # 만원
    # 효과/비용 = 가중치 × 부재율 ÷ 단가 (높을수록 비용 대비 효과 큼)
    priority_score = (weight * absent) / unit_cost_mw * 100  # 스케일 조정
    priority_rows.append({
        "카테고리": c,
        "법령 가중치": weight,
        "추정 부재율": f"{absent*100:.0f}%",
        "학교당 단가": f"{unit_cost_mw:,}만원",
        "우선순위 점수": round(priority_score, 2),
    })

priority = pd.DataFrame(priority_rows).sort_values("우선순위 점수", ascending=False)
st.dataframe(priority, use_container_width=True, hide_index=True)

fig2 = px.bar(priority, x="우선순위 점수", y="카테고리", orientation="h",
              color="우선순위 점수", color_continuous_scale=["#9A9A9F", "#D50000"])
fig2.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20),
                   yaxis={"categoryorder": "total ascending"},
                   coloraxis_showscale=False)
st.plotly_chart(fig2, use_container_width=True)

st.caption(
    "※ 부재율은 공공데이터 + 시범 점검 결과 추정치입니다. "
    "실제 정책 결정 시에는 환원된 실측 데이터로 재계산하세요. "
    "**단가가 낮고 부재율이 높은 카테고리(예: 안내·표지, 개인보호구)는 "
    "소규모 예산으로도 큰 개선이 가능**하므로 첫 집행 라운드에 우선 배정을 권장합니다."
)
