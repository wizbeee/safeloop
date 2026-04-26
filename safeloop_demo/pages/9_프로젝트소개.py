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
                   layout="wide", initial_sidebar_state="expanded")
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

# 팀 / 대회
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("팀명", "세이프루프 SafeLoop")
with c2:
    st.metric("대회", "제8회 교육 공공데이터 AI 활용대회")
with c3:
    st.metric("마감", "2026-05-31")

divider()

# 4단계 + 순환
section("01", "4단계 + 순환 구조")
st.markdown(
    """
    | Stage | 내용 | 역할 |
    |:---:|---|---|
    | **Stage 1** | 전국 위험도 분석 (11,841개교 → 526개교 식별) | 진단 |
    | **Stage 2** | AI 맞춤 점검표 자동 생성 (3단계 AI 비전) | 정밀 점검 도구 |
    | **Stage 3** | 실질 점검 + 안전 점수 + 데이터 수집 | 데이터 축적 |
    | **Stage 4** | 에듀파인 결재 → KEIIS → 공공데이터 환원 → 정책 활용 | 의사결정 지원 |
    | **순환** | Stage 4 환원 → Stage 1 정교화 (자가 개선) | 시스템 진화 |
    """
)

divider()

# 차별점
section("02", "차별점 3가지")
cc1, cc2, cc3 = st.columns(3)
with cc1:
    st.markdown("### 1. 공간 맞춤 점검표\n일률 점검표 → **공간별 법령에 부합하는 맞춤표**를 AI가 자동 설계. 담당자의 다중 법령 매핑 부담 제거.")
with cc2:
    st.markdown("### 2. 데이터 순환\n단발 분석 → **환원 피드백 루프**. 점검 결과가 KEIIS·공공데이터포털로 흐르며 대시보드 자체가 진화.")
with cc3:
    st.markdown("### 3. 기존 제도 존중\n에듀파인·KEIIS·공공데이터포털을 **대체하지 않고 가교**. 결재라인·법적 효력 유지, 품질만 AI로 혁신.")

divider()

# 법령 근거
section("03", "6개 핵심 법령")
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
section("04", "제도 관점 데이터 흐름")
st.markdown(
    """
    | 단계 | 시스템 | 역할 |
    |:---:|---|---|
    | 1 | 학교 점검 앱 (SafeLoop) | 현장 점검·AI 맞춤 점검표·이중 저장 |
    | 2 | 에듀파인 / K-에듀파인 | 내부 결재라인 (담당자→부장→교감→교장) |
    | 3 | 교육청 담당자 모듈 | 결재 완료 데이터 수신·검증 (옵션 2) |
    | 4 | **교육시설통합정보망 (KEIIS)** | 교육시설법 제10조 3항 자체 점검 결과 집적 (2024 개통) |
    | 5 | 공공데이터포털 | 익명화·집계 후 2차 개방 (업무 부산물 개방 원칙) |
    | 6 | 대시보드 B (SafeLoop) | 환원 데이터로 Stage 1 고도화 → 순환 완성 |
    """
)

divider()

# ─────────────────────────────────────────
# 05 순환 구조 Sankey (구 데이터순환 페이지에서 이관)
# ─────────────────────────────────────────
section("05", "순환 구조 Sankey",
        "학교 → 에듀파인 → 교육청 → KEIIS → 공공데이터 → 대시보드 → 다시 위험군 재평가")

_sankey_labels = [
    "공공데이터 (기존 BEFORE)",     # 0
    "위험군 526개교",                # 1
    "학교 · SafeLoop 점검",          # 2
    "에듀파인 결재",                 # 3
    "교육청 수신·검증",              # 4
    "KEIIS · 환원",                  # 5
    "AFTER 고도화 · 정책 결정",      # 6
]
_sankey_sources = [0, 1, 2, 3, 4, 5]
_sankey_targets = [1, 2, 3, 4, 5, 6]
_sankey_values  = [100, 80, 80, 80, 55, 55]

_sankey_fig = go.Figure(data=[go.Sankey(
    arrangement="snap",
    node=dict(
        pad=40, thickness=22,
        line=dict(color="#0A0A0B", width=0.6),
        label=_sankey_labels,
        color=[
            "#8BC34A", "#FFC107", "#D50000",
            "#5C6BC0", "#29B6F6", "#26C6DA", "#2E7D32",
        ],
    ),
    link=dict(source=_sankey_sources, target=_sankey_targets, value=_sankey_values,
              color=["rgba(200,200,200,0.35)"] * len(_sankey_sources))
)])
_sankey_fig.update_layout(height=420, margin=dict(l=20, r=20, t=10, b=10),
                           font=dict(size=13, color="#0A0A0B"))
st.plotly_chart(_sankey_fig, width="stretch")

st.caption(
    "※ **순환의 핵심** — 6단계의 AFTER 고도화 결과는 다음 분기에 0단계 BEFORE 에 "
    "추가되어 위험군 재평가에 사용됩니다. (매 분기 반복 → '순환'의 의미)"
)

divider()

# ─────────────────────────────────────────
# 06 교육청 정책 활용 프레임 (구 데이터순환 페이지에서 이관)
# ─────────────────────────────────────────
section("06", "교육청 정책 활용 프레임",
        "수집된 데이터로 위험군 학교에 일관된 개선 지원 → 효과 모니터링")

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

st.markdown(
    "<div style='margin-top:16px;padding:16px 20px; background:#FAFAFA; border:1px solid #E5E5E8; "
    "border-radius:8px; font-size:13px; color:#0A0A0B; line-height:1.8;'>"
    "<b style='color:#D50000;'>기존 제도 존중 원칙</b> — SafeLoop은 에듀파인·KEIIS·공공데이터포털을 "
    "대체하지 않습니다. 법적 근거(공공데이터법 · 교육시설법 제10조 3항 · "
    "<i>공공데이터는 업무 부산물 개방</i>)를 그대로 두고, 학교의 업무 부산물이 더 정확하게·구조화되어 "
    "기존 경로로 흘러가도록 돕는 역할만 합니다."
    "</div>",
    unsafe_allow_html=True,
)

divider()

# 확장 로드맵
section("07", "확장 로드맵")
st.markdown(
    """
    | 단계 | 내용 | 시기 |
    |:---:|---|:---:|
    | MVP | 앱 · 에듀파인 패키지 · Mock 수신함 | 2026 상반기 |
    | Phase 2 | 교육청 수신 모듈 실제 운영 · 결재 증빙 자동 파싱 | 6~12개월 |
    | Phase 3 | KEIIS API 직접 연동 · 공공데이터포털 자동 등록 | 1~3년 |
    | 확장 1 | 학교 → 도서관 · 복지관 · 공공 문화·체육 시설 일반화 | 중기 |
    | 확장 2 | 법령 RAG(국가법령정보센터 API) 구축 — 맞춤 점검표 범위 자동 확장 | 중장기 |
    """
)

divider()

# 기술 스택
section("08", "기술 스택")
c_a, c_b, c_c = st.columns(3)
with c_a:
    st.markdown("**Frontend**\n- Streamlit\n- Plotly · Altair")
with c_b:
    st.markdown("**AI**\n- Claude Opus 4.5 (Vision 단계 1·2)\n- Claude Haiku 4.5 (단계 3)")
with c_c:
    st.markdown("**Backend · 데이터**\n- Python 3.10+\n- pandas · ReportLab · openpyxl")

divider()
st.caption("© 2026 세이프루프 · 제8회 교육 공공데이터 AI 활용대회")
