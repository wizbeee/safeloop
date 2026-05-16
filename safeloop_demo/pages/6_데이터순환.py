"""
데이터 전송 — 학교 담당자용 통합 발송 화면.

이 페이지에서 가능한 작업:
  ① 본교의 저장된 점검 중 발송할 건 선택
  ② 두 가지 방법으로 발송:
     - 방법 1 (권장): SafeLoop 다이렉트 전송 (1클릭, 수신 확인 자동)
     - 방법 2 (대체): PDF + .safeloop 다운로드 본인이 메일·카톡으로 직접 전송
  ③ 발송 기록 + 수신 확인 상태 추적

결과 저장 페이지의 발송 섹션은 "방금 저장한 점검을 즉시 발송" 단축 흐름을 위해
유지됩니다. 본 페이지는 "이전에 저장한 건도 발송할 수 있는 종합 화면"입니다.
"""
from __future__ import annotations

import datetime
import json
import urllib.parse
from pathlib import Path

import streamlit as st

from modules.crypto import encrypt_to_file_bytes
from modules.data_loader import get_sido_edu_email
from modules.session import ensure_state
from modules.storage import (
    build_edu_package, build_pdf_report,
    get_school_outbox, list_recent_sessions,
    submit_to_edu_inbox_direct,
)
from modules.ui import apply_theme, divider, empty_state, hero, render_sidebar, section

st.set_page_config(page_title="데이터 전송 · SafeLoop",
                   page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="auto")
apply_theme()
ensure_state()
render_sidebar(active_key="my_submission")

# 역할 가드
if st.session_state.get("role") == "교육청":
    st.warning(
        "**교육청 담당자 모드** — '데이터 전송' 은 학교 담당자 화면입니다. "
        "전체 수신 목록은 '교육청 수신함'에서 확인하세요."
    )
    if st.button("교육청 수신함으로 이동", key="track_guard_inbox",
                  type="primary", width="stretch"):
        st.switch_page("pages/7_교육청수신함.py")
    st.stop()

hero("SUBMISSION", "데이터 전송",
     "본교 점검 결과를 교육청 담당자에게 발송 + 발송 기록·수신 확인 추적")

school = st.session_state.get("school")
if not school:
    empty_state(
        title="학교 인증이 필요합니다",
        description="먼저 학교를 검색·인증한 뒤 점검 결과를 저장해주세요.",
        action_label="점검 시작으로",
        action_target="pages/1_점검시작.py",
    )
    st.stop()

school_code = school.get("정보공시 학교코드", "")
school_name = school.get("학교명", "")
school_sido = school.get("시도교육청", "")

# 본교의 모든 저장 세션
recent: list[dict] = [s for s in list_recent_sessions(limit=50)
                       if s.get("school_code") == school_code]

if not recent:
    empty_state(
        title="아직 저장된 점검이 없습니다",
        description="'결과 저장' 페이지에서 점검 결과를 저장하면 이곳에서 발송할 수 있습니다.",
        action_label="결과 저장으로",
        action_target="pages/3_결과저장.py",
    )
    st.stop()

# ─────────────────────────────────────────
# 01 발송할 점검 선택
# ─────────────────────────────────────────
section("01", "발송할 점검 선택",
        f"본교 저장 점검 {len(recent)}건 — 발송할 건을 골라주세요")

# 라디오로 단일 선택 — 큰 라벨로 가독성
def _label(s: dict) -> str:
    ts = (s.get("timestamp", "") or "")[:16].replace("T", " ")
    sp = s.get("space_type", "-")
    nick = s.get("space_nickname") or ""
    sp_label = f"{sp}" + (f" ({nick})" if nick else "")
    sc = s.get("score", "-")
    gr = s.get("grade", "-")
    return f"{ts} · {sp_label} · {sc}점 ({gr}) · {s.get('session_id','-')[:14]}"

# 발송 기록과 매칭 — 이미 발송한 세션 표시 (중복 방지)
outbox = get_school_outbox(school_code) if school_code else []
sent_session_keys = {
    f"{r.get('school_code')}|{r.get('space_type')}|{(r.get('submitted_at') or '')[:10]}"
    for r in outbox
}

picked_idx = st.radio(
    "발송할 점검",
    options=list(range(len(recent))),
    format_func=lambda i: _label(recent[i]),
    label_visibility="collapsed",
    key="data_send_pick_idx",
)
picked_session = recent[picked_idx]
picked_sid = picked_session.get("session_id")
picked_path = Path(picked_session.get("path", "")) / "master.json" if picked_session.get("path") else None

# 발송 데이터 준비 — master.json 로드
if not picked_path or not picked_path.exists():
    st.error(f"점검 데이터 파일을 찾을 수 없습니다: {picked_path}")
    st.stop()

try:
    master = json.loads(picked_path.read_text(encoding="utf-8"))
except Exception as e:
    st.error(f"점검 데이터 로드 실패: {e}")
    st.stop()

edu_pkg = build_edu_package(master)

# 선택한 점검 요약 카드
sp = picked_session.get("space_type", "-")
nick = picked_session.get("space_nickname") or ""
sp_label = f"{sp}" + (f" ({nick})" if nick else "")
ts_short = (picked_session.get("timestamp", "") or "")[:16].replace("T", " ")
st.markdown(
    f"<div style='padding:14px 18px;border:1px solid #E5E5E8;"
    f"border-left:4px solid #D50000;border-radius:6px;background:#FFF;'>"
    f"<div style='font-size:11px;letter-spacing:0.28em;color:#6B6B70;font-weight:600;"
    f"margin-bottom:6px;'>SELECTED</div>"
    f"<div style='font-size:18px;font-weight:700;color:#0A0A0B;margin-bottom:4px;'>"
    f"{sp_label} · {picked_session.get('score', '-')}점 "
    f"({picked_session.get('grade', '-')}등급)</div>"
    f"<div style='font-size:13px;color:#6B6B70;'>"
    f"저장: {ts_short} · 🆔 세션 ID: <code>{picked_sid}</code>"
    f"</div></div>",
    unsafe_allow_html=True,
)

# 이미 같은 날짜 발송한 건이면 안내
sent_key = f"{school_code}|{sp}|{(picked_session.get('timestamp') or '')[:10]}"
already_today = any(
    r.get("school_code") == school_code
    and r.get("space_type") == sp
    and (r.get("submitted_at") or "")[:10] ==
        datetime.datetime.now().date().isoformat()
    for r in outbox
)

# ─────────────────────────────────────────
# 02 발송 방법 선택 — 탭
# ─────────────────────────────────────────
divider()
section("02", "발송 방법 선택")

# 발송 대상 이메일 결정
edu_email_user = (st.session_state.get("edu_office_email") or "").strip()
edu_email_fallback = get_sido_edu_email(school_sido)
edu_email = edu_email_user or edu_email_fallback or ""

if not edu_email:
    st.warning(
        f"교육청 담당자 이메일이 등록되지 않았습니다 (시도: {school_sido or '미상'}). "
        f"설정 페이지에서 등록하거나, 방법 1 (다이렉트 전송)만 사용 가능합니다."
    )

tab_direct, tab_manual = st.tabs([
    "다이렉트 (권장)",
    "다운로드 후 발송",
])

# ── 방법 1: 다이렉트 전송 ──
with tab_direct:
    st.caption(
        "1번의 클릭으로 교육청 수신함에 직접 전송 — 학교 PC·교육청 PC 가 "
        "**같은 SafeLoop 데이터 폴더(또는 같은 클라우드 인스턴스)** 를 공유할 때 동작합니다. "
        "전송 후 교육청이 열람하면 자동으로 **수신 확인** 표시가 아래 발송 기록에 반영됩니다."
    )
    st.markdown(
        "<div style='padding:10px 14px;background:#F0F7F0;border:1px solid #C8E6C9;"
        "border-radius:6px;font-size:12px;color:#2E7D32;line-height:1.6;'>"
        "1번의 클릭 · 수신 확인 자동 추적 · 첨부 파일 누락 위험 없음<br>"
        "단일 PC 또는 공유 데이터 폴더 환경 한정 — 분산 PC 환경은 정식 출시 시 검토."
        "</div>",
        unsafe_allow_html=True,
    )

    if already_today:
        st.info(
            "오늘 같은 점검을 이미 한 번 발송했습니다. 아래 버튼을 누르면 추가 "
            "발송이 됩니다 (수정본 재발송 시 사용)."
        )

    if st.button("SafeLoop 수신함으로 다이렉트 전송",
                  type="primary", width="stretch", key="send_direct_now"):
        try:
            res = submit_to_edu_inbox_direct(edu_pkg)
            if res.get("ok"):
                st.success(
                    f"전송 완료 — 발송 ID `{res['submit_id']}` · "
                    f"수신 시도교육청: {res.get('sido')}"
                )
                st.rerun()
            else:
                st.error("전송 실패 — 다시 시도하거나 방법 2를 사용하세요.")
        except Exception as e:
            st.error(f"전송 중 오류: {e.__class__.__name__} — {e}")

# ── 방법 2: 다운로드 + 본인 채널 ──
with tab_manual:
    st.caption(
        "PDF + .safeloop 두 파일을 다운로드한 뒤 본인의 메일·카톡·드라이브로 직접 "
        "전송. 분산 환경(학교/교육청 PC 가 SafeLoop 을 공유 안 함)에서도 가능합니다. "
        "단, 수신 확인은 자동 반영되지 않습니다."
    )

    # 다운로드 버튼
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        try:
            pdf_bytes = build_pdf_report(master)
            st.download_button(
                f"PDF 보고서 다운로드 ({len(pdf_bytes) // 1024} KB)",
                pdf_bytes,
                file_name=f"안전점검_{sp}_{(picked_session.get('timestamp','')[:10])}.pdf",
                mime="application/pdf",
                width="stretch",
                key="dl_pdf_send",
            )
        except Exception as e:
            st.warning(f"PDF 생성 실패: {e}")
    with col_dl2:
        try:
            blob = encrypt_to_file_bytes(edu_pkg)
            st.download_button(
                f"암호화 데이터 다운로드 ({len(blob) // 1024} KB)",
                blob,
                file_name=f"안전점검_{sp}_{(picked_session.get('timestamp','')[:10])}.safeloop",
                mime="application/octet-stream",
                width="stretch",
                key="dl_safeloop_send",
            )
        except Exception as e:
            st.warning(f"암호화 실패: {e}")

    if edu_email:
        # 발송 정보 — 본인 메일/카톡 등에 붙여넣을 수 있도록
        st.markdown("##### 발송 정보 — 복사해서 사용")
        subject = f"[{school_name}] {sp} 안전 점검 결과 제출"
        body_lines = [
            "안녕하세요, 교육청 담당자님.",
            "",
            f"{school_name}의 {sp} 안전 점검 결과를 제출합니다.",
            "",
            "첨부 파일 (2개):",
            " · 사람용 보고서 (PDF) — 결재·인쇄 용도",
            " · 암호화 데이터 파일 (.safeloop) — SafeLoop 수신함에서 자동 복호화",
            "",
            "감사합니다.",
        ]
        body = "\n".join(body_lines)

        col_a, col_b = st.columns([1, 1])
        with col_a:
            st.text_input("받는사람", value=edu_email, key="send_to_box_b",
                           help="클릭 후 Ctrl+A Ctrl+C 로 복사")
            st.text_input("제목", value=subject, key="send_subject_box_b")
        with col_b:
            st.text_area("본문", value=body, height=150, key="send_body_box_b",
                          help="첨부 파일은 위에서 다운로드한 PDF + .safeloop")

        gmail_url = (
            f"https://mail.google.com/mail/?view=cm&fs=1"
            f"&to={urllib.parse.quote(edu_email)}"
            f"&su={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(body)}"
        )
        naver_url = (
            f"https://mail.naver.com/write/popup?to={urllib.parse.quote(edu_email)}"
            f"&subject={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(body)}"
        )
        daum_url = (
            f"https://mail.daum.net/?compose=true"
            f"&to={urllib.parse.quote(edu_email)}"
            f"&subject={urllib.parse.quote(subject)}"
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                f"<a href='{gmail_url}' target='_blank' style='display:block;"
                f"padding:8px 0;background:#EA4335;color:white;text-decoration:none;"
                f"border-radius:6px;font-weight:600;text-align:center;font-size:13px;'>"
                f"Gmail 웹</a>", unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"<a href='{naver_url}' target='_blank' style='display:block;"
                f"padding:8px 0;background:#03C75A;color:white;text-decoration:none;"
                f"border-radius:6px;font-weight:600;text-align:center;font-size:13px;'>"
                f"Naver 메일</a>", unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f"<a href='{daum_url}' target='_blank' style='display:block;"
                f"padding:8px 0;background:#0066FF;color:white;text-decoration:none;"
                f"border-radius:6px;font-weight:600;text-align:center;font-size:13px;'>"
                f"Daum 메일</a>", unsafe_allow_html=True,
            )

        st.caption(
            "카톡 공유 — 본문 복사해 카톡 채팅에 붙여넣고 PDF·.safeloop 함께 첨부 전송."
        )

# ─────────────────────────────────────────
# 03 발송 기록 + 수신 확인 상태
# ─────────────────────────────────────────
divider()
section("03", "발송 기록 + 수신 확인",
        "방법 1로 보낸 건의 수신 상태 자동 추적 (방법 2 발송은 미추적)")

# 최신 발송함 다시 로드 (방금 발송했을 수 있음)
outbox = get_school_outbox(school_code) if school_code else []

if not outbox:
    st.caption(
        "아직 SafeLoop 다이렉트 전송 기록이 없습니다. 위 **방법 1** 으로 발송하면 "
        "여기에 발송 기록과 수신 확인 상태가 표시됩니다."
    )
else:
    n_total = len(outbox)
    n_read = sum(1 for r in outbox if r.get("read_at"))
    n_pending = n_total - n_read
    k1, k2, k3 = st.columns(3)
    k1.metric("다이렉트 발송", f"{n_total}건")
    k2.metric("교육청 수신 확인", f"{n_read}건")
    k3.metric("수신 대기", f"{n_pending}건",
              delta=("미확인 있음" if n_pending else "모두 확인"),
              delta_color=("inverse" if n_pending else "normal"))

    for r in outbox[:30]:
        sub_at = (r.get("submitted_at", "") or "")[:16].replace("T", " ")
        read_at = r.get("read_at")
        if read_at:
            border_color = "#4CAF50"
            status_html = (
                f"<span style='color:#2E7D32;font-weight:700;'>"
                f"수신 확인 완료 — {(read_at or '')[:16].replace('T', ' ')}"
                f"</span>"
            )
        else:
            try:
                sub_dt = datetime.datetime.fromisoformat(r.get("submitted_at"))
                elapsed_days = (datetime.datetime.now() - sub_dt).days
            except Exception:
                elapsed_days = 0
            color = "#D50000" if elapsed_days >= 3 else "#F57C00"
            border_color = color
            status_html = (
                f"<span style='color:{color};font-weight:700;'>"
                f"수신 대기 중 (발송 후 {elapsed_days}일 경과)"
                f"</span>"
            )

        st.markdown(
            f"<div style='padding:12px 16px;border:1px solid #E5E5E8;"
            f"border-left:4px solid {border_color};border-radius:6px;background:#FFF;"
            f"margin-bottom:8px;'>"
            f"<div style='font-size:14px;font-weight:600;color:#0A0A0B;margin-bottom:4px;'>"
            f"{r.get('space_type', '-')} · {r.get('score', '-')}점 ({r.get('grade', '-')}) "
            f"<span style='font-size:11px;color:#6B6B70;font-weight:400;'>"
            f"· 발송 ID `{r.get('submit_id', '-')}`</span></div>"
            f"<div style='font-size:12px;color:#6B6B70;line-height:1.7;'>"
            f"발송 시각: {sub_at} · 시도: {r.get('sido', '-')}<br>"
            f"{status_html}"
            f"</div></div>",
            unsafe_allow_html=True,
        )

st.caption(
    f"학교: **{school_name}** · 조회 시각: "
    f"{datetime.datetime.now():%Y-%m-%d %H:%M}\n\n"
    "메일·카톡(방법 2)으로 발송한 건은 SafeLoop 가 추적할 수 없으므로 본인의 발송함을 "
    "직접 확인하세요."
)
