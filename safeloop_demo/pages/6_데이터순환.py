"""
내 제출 추적 — 학교 담당자 전용.

이 페이지는 학교가 제출한 한 번의 점검 세션이 에듀파인·KEIIS·공공데이터포털을
거쳐 어디까지 진행됐는지 확인하는 **추적(tracking) 도구**입니다.

이전 버전의 'Sankey 순환 구조' 와 '교육청 정책 활용 3단계 카드' 는 기능이 아닌
**설명·학습 콘텐츠** 성격이므로 '프로젝트 소개' 페이지로 이관되었습니다.
"""
from __future__ import annotations

import datetime

import streamlit as st

from modules.session import ensure_state
from modules.ui import apply_theme, empty_state, hero, render_sidebar, section

st.set_page_config(page_title="내 제출 추적 · SafeLoop", page_icon="static/icon-192.png",
                   layout="centered", initial_sidebar_state="expanded")
apply_theme()
ensure_state()
render_sidebar(active_key="my_submission")

# 역할 가드 — 교육청 담당자는 '내 제출' 개념이 없으므로 수신함으로 안내
if st.session_state.get("role") == "교육청":
    st.warning(
        "🏛 **교육청 담당자 모드** — '내 제출 추적' 은 학교 담당자의 개별 제출 세션을 "
        "따라가는 도구입니다. 교육청 관점의 전체 수신 목록은 '교육청 수신함'에서 확인하세요."
    )
    if st.button("→ 교육청 수신함으로 이동", type="primary"):
        st.switch_page("pages/7_교육청수신함.py")
    st.stop()

hero("TRACKING",
     "내 제출 추적",
     "내가 저장·발송한 한 번의 점검이 에듀파인·KEIIS·공공데이터포털 중 어디까지 갔는지 실시간 추적")

# ─────────────────────────────────────────
# 내 제출 데이터 타임라인
# ─────────────────────────────────────────
section("01", "제출 여정 타임라인",
        "세션 저장 → 에듀파인 결재 → 교육청 수신 → KEIIS 이관 → 공공데이터 환원")

saved = st.session_state.get("saved_session_id")
school = st.session_state.get("school")
if not saved:
    empty_state(
        title="추적할 제출 데이터가 없습니다",
        description="먼저 점검을 완료하고 '결과 저장' 페이지에서 저장·발송해 주세요.",
        action_label="결과 저장으로",
        action_target="pages/3_결과저장.py",
    )
    st.stop()

# 결재 진행도 ◯/◐/✅ 계산 (결과저장 페이지와 상태 동기화)
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

st.caption(
    "💡 **순환 구조·교육청 정책 활용 프레임 등 학습용 내용**은 "
    "사이드바 '프로젝트 소개' 페이지로 이관되었습니다."
)
