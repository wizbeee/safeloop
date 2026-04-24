"""
Stage 4 — 데이터 순환 + 정책 활용 흐름도.

[1] Sankey 다이어그램 — 학교 → 에듀파인 결재 → 교육청 → KEIIS → 공공데이터포털 → 대시보드 B
[2] 내 제출 데이터 타임라인 — 현재 진행 단계 시각화 (Mock)
[3] 정책 활용 시나리오 — 공립 재정지원 / 사립 권고 / 매칭 지원
"""
from __future__ import annotations

import datetime

import plotly.graph_objects as go
import streamlit as st

from modules.session import ensure_state
from modules.ui import apply_theme, divider, empty_state, hero, render_sidebar, section

st.set_page_config(page_title="데이터 순환 · SafeLoop", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="expanded")
apply_theme()
ensure_state()
render_sidebar(active_key="cycle")

hero("STAGE 04",
     "데이터 순환 · 정책 활용",
     "기존 제도(에듀파인·KEIIS·공공데이터포털)를 존중하며 데이터 품질만 AI로 혁신합니다.")

# ─────────────────────────────────────────
# [1] Sankey 순환 구조
# ─────────────────────────────────────────
section("01", "데이터 흐름 (Sankey)")

# Sankey 구조 — 좌→우 선형 흐름 + 환원 루프
# 라벨 겹침 방지를 위해 (1) 노드를 7개로 더 축약 (2) 세로 간격 충분히 확보
# (3) 환원 루프(AFTER → BEFORE)는 caption 으로 설명하고 다이어그램에선 단방향 표기
labels = [
    "공공데이터 (기존 BEFORE)",     # 0
    "위험군 526개교",                # 1
    "학교 · SafeLoop 점검",          # 2
    "에듀파인 결재",                 # 3
    "교육청 수신·검증",              # 4
    "KEIIS · 환원",                  # 5
    "AFTER 고도화 · 정책 결정",      # 6
]
# 좌→우 흐름
sources = [0, 1, 2, 3, 4, 5]
targets = [1, 2, 3, 4, 5, 6]
values  = [100, 80, 80, 80, 55, 55]

fig = go.Figure(data=[go.Sankey(
    arrangement="snap",
    node=dict(
        pad=40, thickness=22,
        line=dict(color="#0A0A0B", width=0.6),
        label=labels,
        color=[
            "#8BC34A", "#FFC107", "#D50000",
            "#5C6BC0", "#29B6F6", "#26C6DA", "#2E7D32",
        ],
    ),
    link=dict(source=sources, target=targets, value=values,
              color=["rgba(200,200,200,0.35)"] * len(sources))
)])
fig.update_layout(height=420, margin=dict(l=20, r=20, t=10, b=10),
                  font=dict(size=13, color="#0A0A0B"))
st.plotly_chart(fig, use_container_width=True)

st.caption(
    "※ **순환의 핵심** — 6단계의 **AFTER 고도화** 결과는 다음 분기에 0단계 **BEFORE** 에 "
    "추가되어 위험군 재평가에 사용됩니다. (매 분기 반복 → '순환' 의 의미)"
)

# ─────────────────────────────────────────
# [2] 내 제출 데이터 타임라인
# ─────────────────────────────────────────
divider()
section("02", "내 제출 데이터 여정")

saved = st.session_state.get("saved_session_id")
school = st.session_state.get("school")
if not saved:
    empty_state(
        title="내 제출 데이터가 없습니다",
        description="결과 저장·발송 페이지에서 저장을 마치면 이 자리에 여정이 표시됩니다.",
        action_label="결과 저장으로",
        action_target="pages/3_결과저장.py",
    )
else:
    # 6-3 수정: _approval_demo_stage 와 edufine_approved 를 함께 사용해
    # 결재 진행도(0/5) 를 여정 타임라인에도 반영 (결과저장 페이지와 상태 동기화).
    _stage = int(st.session_state.get("_approval_demo_stage", 0))
    _approved = bool(st.session_state.get("edufine_approved"))
    if _approved or _stage >= 4:
        _edufine_mark = "✅"
        _edufine_done = True
        _edufine_note = f"결재 완료 · 단계 {min(_stage, 5)}/5"
    elif _stage > 0:
        _edufine_mark = "◐"
        _edufine_done = False
        _edufine_note = f"결재 진행 중 · 단계 {_stage}/5"
    else:
        _edufine_mark = "◯"
        _edufine_done = False
        _edufine_note = "결재 대기 · 1~3일 소요"

    stages = [
        ("✅", "학교 클라우드 저장 완료", True, "오늘"),
        ("✅", "결재용 공문 패키지 생성", True, "오늘"),
        (
            _edufine_mark,
            "에듀파인 결재 진행/완료",
            _edufine_done,
            _edufine_note,
        ),
        (
            "✅" if st.session_state.get("edu_app_sent") else "◯",
            "교육청 수신함 직접 전송",
            st.session_state.get("edu_app_sent", False),
            "결재 직후",
        ),
        ("◯", "교육청 검증·취합", False, "1~2주"),
        ("◯", "KEIIS 업로드 (시설 점검 통합)", False, "교육청 재량"),
        ("◯", "익명화·집계 처리", False, "자동"),
        ("◯", "공공데이터포털 등록", False, "분기"),
        ("◯", "대시보드 B 반영 (AFTER 고도화)", False, "등록 후 즉시"),
    ]

    for mark, label, done, note in stages:
        color = "#4CAF50" if done else ("#FFC107" if mark == "◐" else "#BDBDBD")
        st.markdown(
            f"<div style='padding:8px 12px;margin:4px 0;border-left:4px solid {color};"
            f"background:{'#F0F7F0' if done else '#FAFAFA'};border-radius:6px;'>"
            f"<span style='font-size:18px'>{mark}</span> "
            f"<b>{label}</b> "
            f"<span style='color:#888;font-size:12px;margin-left:8px'>· {note}</span></div>",
            unsafe_allow_html=True,
        )

    if school:
        st.caption(
            f"학교: {school.get('학교명')} · 세션 ID: `{saved}` · "
            f"조회 시각: {datetime.datetime.now():%Y-%m-%d %H:%M}"
        )

# ─────────────────────────────────────────
# [3] 정책 활용 시나리오
# ─────────────────────────────────────────
divider()
section("03", "교육청 정책 활용",
        "수집된 데이터로 위험군 학교에 일관된 개선 지원 → 효과 모니터링")

# 통합 카드 (공립/사립 분리하지 않음 · 짙은 글자색으로 가독성 확보)
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
st.markdown(
    "<div style='padding:16px 20px; background:#FAFAFA; border:1px solid #E5E5E8; "
    "border-radius:8px; font-size:13px; color:#0A0A0B; line-height:1.8;'>"
    "<b style='color:#D50000;'>기존 제도 존중 원칙</b> — SafeLoop은 에듀파인·KEIIS·공공데이터포털을 "
    "대체하지 않습니다. 법적 근거(공공데이터법 · 교육시설법 제10조 3항 · "
    "<i>공공데이터는 업무 부산물 개방</i>)를 그대로 두고, 학교의 업무 부산물이 더 정확하게·구조화되어 "
    "기존 경로로 흘러가도록 돕는 역할만 합니다."
    "</div>",
    unsafe_allow_html=True,
)
