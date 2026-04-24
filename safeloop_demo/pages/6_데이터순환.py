"""
내 제출 상태 — 학교 담당자용.

SafeLoop 은 에듀파인·KEIIS 와 별도 시스템이므로, 이 페이지에서 실시간으로 확인 가능한
상태는 **앱 내부에 남는 3가지**뿐입니다:
  ① 학교 클라우드 저장 완료
  ② 공문 패키지 생성 완료
  ③ 앱에서의 교육청 직접 전송 (Mock) 완료

그 이후 단계 (에듀파인 결재, 교육청 검증, KEIIS 이관, 공공데이터 환원)는 **앱 밖**에서
일어나므로 여기서 추적 불가 → '별도 확인' 안내로 분리 표시.
"""
from __future__ import annotations

import datetime

import streamlit as st

from modules.session import ensure_state
from modules.ui import apply_theme, empty_state, hero, render_sidebar, section

st.set_page_config(page_title="내 제출 상태 · SafeLoop", page_icon="static/icon-192.png",
                   layout="centered", initial_sidebar_state="expanded")
apply_theme()
ensure_state()
render_sidebar(active_key="my_submission")

# 역할 가드 — 교육청 담당자는 '내 제출' 개념 없음
if st.session_state.get("role") == "교육청":
    st.warning(
        "🏛 **교육청 담당자 모드** — '내 제출 상태' 는 학교 담당자의 개별 제출 세션을 "
        "확인하는 도구입니다. 교육청 관점의 전체 수신 목록은 '교육청 수신함'에서 확인하세요."
    )
    if st.button("→ 교육청 수신함으로 이동", key="track_guard_inbox",
                  type="primary", use_container_width=True):
        st.switch_page("pages/7_교육청수신함.py")
    st.stop()

hero("SUBMISSION",
     "내 제출 상태",
     "SafeLoop 앱 내부에서 확인 가능한 단계만 표시 — 에듀파인·KEIIS 는 별도 시스템")

# ─────────────────────────────────────────
# 안내 — 이 페이지의 한계를 솔직하게 명시
# ─────────────────────────────────────────
st.markdown(
    "<div style='border:1px solid #E5E5E8;border-left:3px solid #D50000;"
    "background:#FFF;border-radius:6px;padding:14px 18px;margin-bottom:20px;"
    "font-size:13px;line-height:1.75;color:#0A0A0B;'>"
    "<b style='color:#D50000;'>⚠ 알림</b> — SafeLoop 은 에듀파인·K-에듀파인·KEIIS·"
    "공공데이터포털과 <b>연동되지 않은 별도 시스템</b>입니다. 따라서 이 페이지는 "
    "<b>앱 내부에 기록된 단계</b>만 정확히 보여줍니다.<br><br>"
    "에듀파인 결재 진행 여부·교육청 검증·KEIIS 이관·공공데이터 환원 단계는 각 시스템에서 "
    "직접 확인하셔야 합니다. 아래 '앱 외부 단계' 섹션은 <b>예상 소요 기간</b>을 참고용으로만 "
    "제공합니다."
    "</div>",
    unsafe_allow_html=True,
)

saved = st.session_state.get("saved_session_id")
school = st.session_state.get("school")

if not saved:
    empty_state(
        title="확인할 제출이 없습니다",
        description="먼저 '결과 저장' 페이지에서 저장·발송을 완료해주세요.",
        action_label="결과 저장으로",
        action_target="pages/3_결과저장.py",
    )
    st.stop()

# ─────────────────────────────────────────
# 01 앱 내부 상태 (실시간 확인 가능)
# ─────────────────────────────────────────
section("01", "앱에서 확인 가능한 단계",
        "세션 저장 · 공문 패키지 · 앱 발송 — 모두 실제 값")

app_stages = [
    ("✅", "학교 클라우드에 저장됨", True,
     f"세션 ID: {saved}"),
    (
        "✅" if st.session_state.get("edu_package_ready") else "◯",
        "공문 패키지(ZIP) 생성",
        st.session_state.get("edu_package_ready", False),
        "생성 시 저장 폴더에 영구 보관",
    ),
    (
        "✅" if st.session_state.get("edu_app_sent") else "◯",
        "앱 내 교육청 직접 전송 (Mock)",
        st.session_state.get("edu_app_sent", False),
        "실 운영 시 교육청 수신 API 로 대체",
    ),
]

for mark, label, done, note in app_stages:
    color = "#4CAF50" if done else "#BDBDBD"
    bg = "#F0F7F0" if done else "#FAFAFA"
    st.markdown(
        f"<div style='padding:10px 14px;margin:4px 0;border-left:4px solid {color};"
        f"background:{bg};border-radius:6px;'>"
        f"<span style='font-size:18px'>{mark}</span> "
        f"<b>{label}</b> "
        f"<span style='color:#6B6B70;font-size:12px;margin-left:8px'>· {note}</span></div>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────
# 02 앱 외부 단계 (별도 확인 필요)
# ─────────────────────────────────────────
st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
section("02", "앱 외부 단계 (참고용)",
        "이 단계들은 각 시스템에서 직접 확인하셔야 합니다")

external_stages = [
    ("🔹", "에듀파인/K-에듀파인 결재 진행",
     "에듀파인 시스템에서 직접 확인",
     "기관별 결재라인 · 1~3 일 소요"),
    ("🔹", "교육청 담당자 검증·취합",
     "교육청 문의",
     "1~2 주"),
    ("🔹", "KEIIS 이관 (교육시설통합정보망)",
     "KEIIS 시스템 또는 교육청 문의",
     "교육청 재량"),
    ("🔹", "공공데이터포털 환원",
     "공공데이터포털 직접 확인",
     "분기 단위 갱신"),
]

for mark, label, how, when in external_stages:
    st.markdown(
        f"<div style='padding:10px 14px;margin:4px 0;border-left:4px solid #9A9A9F;"
        f"background:#F7F7F9;border-radius:6px;'>"
        f"<span style='font-size:16px'>{mark}</span> "
        f"<b>{label}</b><br>"
        f"<span style='color:#6B6B70;font-size:12px;margin-left:22px;'>"
        f"확인 경로: {how} · 예상 기간: {when}</span></div>",
        unsafe_allow_html=True,
    )

if school:
    st.caption(
        f"학교: {school.get('학교명')} · 세션 ID: `{saved}` · "
        f"조회 시각: {datetime.datetime.now():%Y-%m-%d %H:%M}"
    )

st.caption(
    "💡 **전체 순환 구조**(학교 → 에듀파인 → 교육청 → KEIIS → 공공데이터 → 대시보드)는 "
    "'프로젝트 소개' 페이지의 Sankey 다이어그램에서 시각화로 확인할 수 있습니다."
)
