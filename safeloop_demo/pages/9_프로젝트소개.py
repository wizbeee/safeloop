"""
프로젝트 소개 — 팀·대회·법령·기술스택·로드맵.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.laws import CORE_LAWS, LAW_BASIS
from modules.session import ensure_state
from modules.ui import apply_theme, divider, hero, render_sidebar, section

st.set_page_config(page_title="프로젝트 소개 · SafeLoop", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="auto")
apply_theme()
ensure_state()
render_sidebar(active_key="about")

hero("ABOUT", "세이프루프 (SafeLoop)",
     "공공데이터로 시작해, 공공데이터로 돌아옵니다. 학교 안전의 순환 구조.")

st.markdown(
    "<div class='sl-card sl-card-accent' style='margin-bottom:20px;'>"
    "공공데이터로 학교 안전도를 평가하고, AI 맞춤 점검으로 신뢰할 만한 데이터를 수집해, "
    "그 데이터가 다시 공공데이터로 환원되어 대시보드를 더 정교하게 만드는 <b>순환 구조</b>."
    "</div>",
    unsafe_allow_html=True,
)

# 프로젝트 정보
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("프로젝트", "세이프루프 SafeLoop")
with c2:
    st.metric("적용 분야", "학교 시설 안전 점검")
with c3:
    st.metric("기술 스택", "Streamlit + Python + Claude API")

divider()

# 차별점
section("01", "차별점")
cc1, cc2 = st.columns(2)
with cc1:
    st.markdown("### 공간 맞춤 점검표\n일률 점검표 **공간별 법령에 부합하는 맞춤표**를 AI가 자동 설계. 담당자의 다중 법령 매핑 부담 제거.")
with cc2:
    st.markdown("### 3단 검토 흐름\n실 담당자 점검 → 학교 담당자 수합·검토 → 교육청 발송. 권한 분리와 책임성 강화.")

divider()

# 법령 근거
section("02", "6개 핵심 법령")
st.caption("AI 점검표의 모든 항목은 아래 법령의 구체 조항에 매핑되어 출력됩니다.")
for law in CORE_LAWS:
    st.markdown(f"- **{law}**")

with st.expander("27 표준 항목 × 법령 매핑"):
    rows = []
    for name, info in LAW_BASIS.items():
        rows.append({
            "항목": name,
            "카테고리": info["category"],
            "가중치": info["weight"],
            "법령": info["law"],
            "조항": info["article"],
            "비고": info["note"],
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

divider()

# 데이터 흐름 (제도 관점)
section("03", "제도 관점 데이터 흐름")
st.markdown(
    """
    | 단계 | 시스템 | 역할 |
    |:---:|---|---|
    | 1 | 학교 점검 앱 (SafeLoop) | 현장 점검·AI 맞춤 점검표·이중 저장 |
    | 2 | 에듀파인 / K-에듀파인 | 내부 결재라인 (담당자부장교감교장) |
    | 3 | 교육청 담당자 모듈 | 결재 완료 데이터 수신·검증 (옵션 2) |
    | 4 | **교육시설통합정보망 (KEIIS)** | 교육시설법 제10조 3항 자체 점검 결과 집적 (2024 개통) |
    | 5 | 공공데이터포털 | 익명화·집계 후 2차 개방 (업무 부산물 개방 원칙) |
    | 6 | 대시보드 B (SafeLoop) | 환원 데이터로 Stage 1 고도화 순환 완성 |
    """
)

# ─────────────────────────────────────────
# 04 교육청 정책 활용 프레임
# ─────────────────────────────────────────
section("04", "교육청 정책 활용 프레임",
        "수집된 데이터로 위험군 학교에 일관된 개선 지원 효과 모니터링")

st.markdown(
    """
    <div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap:14px; margin:8px 0;'>
      <div style='border:1px solid #E5E5E8; border-radius:8px; padding:18px 20px; background:#FFF;'>
        <div style='font-size:11px; letter-spacing:0.32em; color:#D50000; font-weight:600; margin-bottom:8px;'>STEP 01</div>
        <div style='font-size:17px; font-weight:700; color:#0A0A0B; margin-bottom:10px;'>위험군 식별</div>
        <div style='font-size:13px; color:#0A0A0B; line-height:1.7;'>
          공공데이터 + 환원 데이터로 위험도 산출. 동일 기준으로 모든 학교에 적용.
        </div>
      </div>
      <div style='border:1px solid #E5E5E8; border-radius:8px; padding:18px 20px; background:#FFF;'>
        <div style='font-size:11px; letter-spacing:0.32em; color:#D50000; font-weight:600; margin-bottom:8px;'>STEP 02</div>
        <div style='font-size:17px; font-weight:700; color:#0A0A0B; margin-bottom:10px;'>차등 개선 지원</div>
        <div style='font-size:13px; color:#0A0A0B; line-height:1.7;'>
          부재 핵심 설비 우선 보완 · 지방교육재정교부금 활용 · 매칭 지원 검토. 설립 구분에 따라 적용 방식만 조정.
        </div>
      </div>
      <div style='border:1px solid #E5E5E8; border-radius:8px; padding:18px 20px; background:#FFF;'>
        <div style='font-size:11px; letter-spacing:0.32em; color:#D50000; font-weight:600; margin-bottom:8px;'>STEP 03</div>
        <div style='font-size:17px; font-weight:700; color:#0A0A0B; margin-bottom:10px;'>효과 모니터링</div>
        <div style='font-size:13px; color:#0A0A0B; line-height:1.7;'>
          개선 전/후 안전점수 비교 · 대시보드 B의 AFTER 해상도로 학교×공간 단위 추적 · 다음 분기 정책 보완.
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

divider()
st.caption("세이프루프 SafeLoop · 학교 시설 안전 점검 시스템")
