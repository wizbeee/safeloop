"""
Step 6~7 — 공간별 점검 결과 확인 + AI 추천 + 이중 저장 + 교육청 이메일 발송.

[1] 공간별 결과 확인 (당일 세션 내 여러 공간 비교 가능)
[2] AI 추천 안전 설비 (부재·불량 기준, 법령 근거 + 우선순위)
[3] 이중 저장 — 사람용(PDF) + AI 가 읽는 형태(JSON) — 모바일/PC 모두 다운로드 가능
[4] 통합 PDF 다운로드 (보고서 단일 파일)
[5] 내부 결재 확인 + 교육청 담당자 이메일로 발송 (mailto)
"""
from __future__ import annotations

import datetime
import urllib.parse

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.recommend import recommend_from_scores
from modules.session import ensure_state, require_school
from modules.storage import (
    build_csv,
    build_excel,
    build_master_record,
    build_official_letter_pdf,
    build_pdf_report,
    list_recent_sessions,
    save_inspection,
    clear_draft,
    korean_font_available,
)
from modules.ui import apply_theme, divider, hero, render_sidebar, section

st.set_page_config(page_title="결과 저장·발송 · SafeLoop", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="auto")
apply_theme()
ensure_state()
render_sidebar(active_key="save")

school = require_school()
if not school:
    if st.button("← 학교 찾기로", key="save_noschool_back",
                  width="stretch"):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

# 활성 공간 가드 (이전 페이지를 거치지 않은 경우)
active_space = st.session_state.get("active_space")
if not active_space:
    st.warning("점검할 공간이 선택되지 않았습니다. 점검 시작 페이지에서 공간을 선택해 주세요.")
    if st.button("← 공간 선택으로", key="save_nospace_back",
                  width="stretch"):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

sr = st.session_state.get("score_result")
if not sr:
    st.warning("점검 결과가 아직 없습니다. AI 점검을 먼저 완료하세요.")
    if st.button("← AI 점검으로", key="save_noresult_back",
                  width="stretch"):
        st.switch_page("pages/2_AI점검.py")
    st.stop()

# 역할별 헤더 라벨 (실 담당자는 "제출" 흐름)
_role = st.session_state.get("role", "학교")
_is_space_role = (_role == "실")
_space_mgr = st.session_state.get("space_manager") or {}

if _is_space_role:
    hero(
        "단계 3 — 학교 담당자에게 제출",
        "결과 제출",
        f"{school['학교명']} · {active_space.get('type', '-')} "
        f"({active_space.get('nickname') or '-'}) "
        f"· 제출자: {_space_mgr.get('name', '실 담당자')}",
    )
    st.info(
        "👤 **실 담당자 모드** — 본 점검 결과는 **학교 담당자에게 제출**되어 검토 후 "
        "교육청에 통합 보고됩니다. 교육청 직접 발송은 학교 담당자만 가능합니다."
    )
else:
    hero(
        "단계 3 — 결과 저장",
        "결과 저장",
        f"{school['학교명']} · {active_space.get('type', '-')} "
        f"({active_space.get('nickname') or '-'})",
    )

# 미저장 경고 — 점검 진행 중인데 아직 저장 안 했으면 상단에 명확한 안내
from modules.session import has_unsaved_inspection_work
if has_unsaved_inspection_work():
    st.warning(
        "⚠ **현재 점검은 아직 저장되지 않았습니다** — 다른 페이지로 이동하기 전 "
        "아래 **'점검 결과 저장'** 버튼을 먼저 누르세요. "
        "저장 안 한 상태로 이동하면 사진·점수·결과가 사라질 수 있습니다."
    )

# ─────────────────────────────────────────
# (1) 공간별 점검 결과 확인
# ─────────────────────────────────────────
section("01", "점검 결과 확인")

col1, col2, col3, col4 = st.columns(4)
col1.metric("종합 점수", f"{sr['score']}점")
col2.metric("등급", sr["grade"])
col3.metric("카테고리", str(len(sr.get("category_scores", {}))))
col4.metric("적용 법령", "6개")

# 이번 세션과 과거 저장분
prior = [s for s in list_recent_sessions(limit=50)
         if s["school_code"] == school["정보공시 학교코드"]]
current_space = st.session_state["active_space"]["type"]

if prior:
    st.markdown("##### 본교 최근 점검 기록")
    df_prior = pd.DataFrame([{
        "점검일시": s["timestamp"][:16] if s["timestamp"] else "",
        "공간": f"{s['space_type']} ({s['space_nickname'] or '-'})",
        "점수": s["score"],
        "등급": s["grade"],
    } for s in prior[:10]])
    st.dataframe(df_prior, width="stretch", hide_index=True)
else:
    st.caption("본교의 저장된 점검 이력이 없습니다. (첫 점검)")

# 카테고리별 점수 막대
cats = sr.get("category_scores") or {}
if cats:
    st.markdown("##### 카테고리별 점수")
    cat_df = pd.DataFrame([
        {"카테고리": k, "점수": v["score"], "가중치합": v["weight_sum"]}
        for k, v in cats.items()
    ]).sort_values("점수", ascending=True)
    fig = px.bar(cat_df, x="점수", y="카테고리", orientation="h",
                 text="점수", range_x=[0, 100],
                 color="점수", color_continuous_scale=["#D50000", "#FFC107", "#4CAF50"])
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=20, b=20), coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch")

# ─────────────────────────────────────────
# (2) AI 추천
# ─────────────────────────────────────────
divider()
section("02", "AI 추천 안전 설비", "부재·불량 설비에 대한 법령 근거 + 우선순위")

# AI 점검에서 자동 생성됨 — 없으면 즉시 자동 생성. 공간/층수 필터 함께 전달.
_active_space = st.session_state.get("active_space") or {}
_space_type = _active_space.get("type")
_floor = _active_space.get("floor")

recs = st.session_state.get("recommendations")
if recs is None:
    recs = recommend_from_scores(
        sr.get("raw", {}), space_type=_space_type, floor=_floor,
    )
    st.session_state["recommendations"] = recs

if st.button("추천 재생성", help="점수를 변경했거나 새 분석 후 다시 산출"):
    st.session_state["recommendations"] = recommend_from_scores(
        sr.get("raw", {}), space_type=_space_type, floor=_floor,
    )
    st.rerun()
recs = st.session_state.get("recommendations") or []
if recs:
    rec_df = pd.DataFrame(recs)[
        ["priority", "item", "category", "law", "article", "action", "reason"]
    ].rename(columns={
        "priority": "우선순위", "item": "항목", "category": "분류",
        "law": "법령", "article": "조항", "action": "조치", "reason": "사유",
    })
    st.dataframe(rec_df, width="stretch", hide_index=True)
    st.caption(f"총 {len(recs)}건 · 비용·구매처는 향후 확장 영역")
else:
    st.info("추천 항목이 없습니다. (전체 양호)")

# ─────────────────────────────────────────
# (3) 이중 저장
# ─────────────────────────────────────────
divider()
if _is_space_role:
    section(
        "03",
        "학교 담당자에게 제출",
        "제출 시 학교 담당자에게 검토 대기 상태로 전달됩니다. "
        "(제출 후에는 학교 담당자가 승인·반려·수정할 수 있습니다.)",
    )
else:
    section("03", "점검 결과 저장", "사람이 읽는 형태와 AI 가 읽는 형태 모두 자동 생성됩니다.")

st.markdown(
    "<div class='sl-card'>"
    "<b>사람이 읽는 형태</b> — PDF 보고서 · Excel · CSV · 공문(품의서) PDF<br>"
    "<b>AI 가 읽는 형태</b> — 원본 JSON · 교육청 발송 패키지 JSON · 공공데이터 환원 패키지 JSON"
    "</div>",
    unsafe_allow_html=True,
)

col_save1, col_save2 = st.columns([2, 1])
with col_save1:
    _save_btn_label = "학교 담당자에게 제출" if _is_space_role else "점검 결과 저장"
    if st.button(_save_btn_label, type="primary", width="stretch"):
        result = save_inspection({**st.session_state, "timestamp": datetime.datetime.now().isoformat()})
        st.session_state["saved_session_id"] = result["session_id"]
        # 본저장 완료 → 드래프트 정리 (공간별)
        try:
            clear_draft(
                school.get("정보공시 학교코드", ""),
                (active_space or {}).get("space_id", ""),
            )
            st.session_state["_draft_restored"] = False
        except Exception:
            pass
        # 저장 직후 페이지 재렌더 — 상단 미저장 경고가 즉시 사라지도록.
        # st.success/expander 는 rerun 후 saved_session_id 분기에서 표시.
        st.session_state["_just_saved_files"] = result["files"]
        st.rerun()

# rerun 후 표시 — 저장된 직후 1회만
if st.session_state.get("_just_saved_files") and st.session_state.get("saved_session_id"):
    _sid_now = st.session_state["saved_session_id"]
    st.success(f"저장 완료 · 세션 ID `{_sid_now}`")
    with st.expander("생성된 파일"):
        for fn in st.session_state["_just_saved_files"]:
            st.markdown(f"- `{fn}`")
    # 한 번 표시 후 소비 — 다음 인터랙션부턴 평범한 상태
    del st.session_state["_just_saved_files"]

with col_save2:
    if st.session_state.get("saved_session_id"):
        st.success("✅ 저장됨")
        st.caption(st.session_state["saved_session_id"])

# 추가 포맷 다운로드 — 일반 사용자에겐 통합 PDF + .safeloop 두 개로 충분.
# Excel/CSV/원본 JSON 은 분석·연구·이관용이라 expander 안에 숨겨 잡음 제거.
if st.session_state.get("saved_session_id"):
    if not korean_font_available():
        st.warning(
            "⚠ 시스템에 한글 PDF 폰트가 없어 PDF의 한글이 깨질 수 있습니다. "
            "Linux 서버라면 `apt install fonts-nanum fonts-noto-cjk` 후 재시작하세요. "
            "(Streamlit Cloud는 packages.txt로 자동 처리됨)"
        )

    master = build_master_record({**st.session_state,
                                   "session_id": st.session_state.get("saved_session_id")})

    with st.expander("📊 추가 포맷 다운로드 (Excel · CSV · 원본 JSON)", expanded=False):
        st.caption(
            "일반 결재·발송에는 아래 04 섹션의 **통합 PDF + 암호화 데이터** 만으로 충분합니다. "
            "이 expander 의 포맷들은 데이터 분석·외부 시스템 이관·연구 용도입니다."
        )
        cd1, cd2, cd3, cd4 = st.columns(4)
        cd1.download_button(
            "보고서 PDF",
            build_pdf_report(master),
            file_name=f"점검결과보고서_{st.session_state['saved_session_id']}.pdf",
            mime="application/pdf",
            width="stretch",
        )
        cd2.download_button(
            "Excel",
            build_excel(master),
            file_name=f"점검결과_{st.session_state['saved_session_id']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
        cd3.download_button(
            "CSV",
            build_csv(master),
            file_name=f"점검결과_{st.session_state['saved_session_id']}.csv",
            mime="text/csv",
            width="stretch",
        )
        cd4.download_button(
            "원본 JSON",
            bytes(__import__("json").dumps(master, ensure_ascii=False, indent=2), "utf-8"),
            file_name=f"master_{st.session_state['saved_session_id']}.json",
            mime="application/json",
            width="stretch",
        )

# ─────────────────────────────────────────
# (4) 통합 PDF 생성 — 사람이 읽기 좋은 단일 보고서
# 결재 양식은 학교마다 다르므로 PDF 자체에 결재란은 두지 않음.
# 학교는 별도 결재 양식에 본 PDF 를 첨부해 결재 진행.
# ─────────────────────────────────────────
divider()
section("04", "통합 PDF 다운로드",
        "공문 + 점검 결과 보고서를 하나의 PDF 로 묶어 다운로드 (사람용)")

if not st.session_state.get("edu_package_ready"):
    if st.button("📄 통합 PDF 생성", type="primary",
                  key="build_unified_pdf", width="stretch"):
        if not st.session_state.get("saved_session_id"):
            save_inspection({**st.session_state, "timestamp": datetime.datetime.now().isoformat()})
        st.session_state["edu_package_ready"] = True
        st.session_state["_edufine_letter_cache"] = None
        st.session_state["_edufine_report_cache"] = None
        st.rerun()  # 즉시 다운로드 버튼이 같은 위치에 나타나도록 페이지 재렌더
else:
    st.success("✅ PDF 준비 완료 — 아래 다운로드 버튼을 누르세요")

# 첨부파일 — 통합 PDF (공문 + 점검 보고서 단일 PDF) 다운로드
if st.session_state.get("edu_package_ready"):
    sid = st.session_state.get("saved_session_id", "")

    # 공문 PDF
    letter_cache = st.session_state.get("_edufine_letter_cache") or {}
    if letter_cache.get("sid") != sid or letter_cache.get("bytes") is None:
        master = build_master_record({**st.session_state, "session_id": sid})
        letter_bytes = build_official_letter_pdf(master)
        st.session_state["_edufine_letter_cache"] = {"sid": sid, "bytes": letter_bytes,
                                                       "master": master}
    else:
        letter_bytes = letter_cache["bytes"]
        master = letter_cache.get("master") or build_master_record({**st.session_state, "session_id": sid})

    # 점검 결과 보고서 PDF
    report_cache = st.session_state.get("_edufine_report_cache") or {}
    if report_cache.get("sid") != sid or report_cache.get("bytes") is None:
        from modules.storage import build_pdf_report
        report_bytes = build_pdf_report(master)
        st.session_state["_edufine_report_cache"] = {"sid": sid, "bytes": report_bytes}
    else:
        report_bytes = report_cache["bytes"]

    # 두 PDF 를 결합한 통합 PDF
    try:
        from pypdf import PdfWriter, PdfReader
        import io as _io
        merger = PdfWriter()
        merger.append(PdfReader(_io.BytesIO(letter_bytes)))
        merger.append(PdfReader(_io.BytesIO(report_bytes)))
        merged_buf = _io.BytesIO()
        merger.write(merged_buf)
        merger.close()
        merged_bytes = merged_buf.getvalue()
    except Exception:
        # pypdf 없거나 실패 시 — 두 PDF 를 별도 다운로드로만 제공
        merged_bytes = None

    def _fmt_size(b: int) -> str:
        if b < 1024:
            return f"{b} B"
        if b < 1024 * 1024:
            return f"{b/1024:.1f} KB"
        return f"{b/1024/1024:.2f} MB"

    # 두 형태로 다운로드: 사람용 PDF + AI 가 읽는 데이터(.safeloop, 암호화)
    # 데이터 파일은 자동 암호화되어 평문 노출 위험 차단.
    # 같은 SafeLoop 앱끼리만 복호화 가능.
    from modules.crypto import encrypt_to_file_bytes
    try:
        from modules.storage import build_edu_package
        edu_pkg_dict = build_edu_package(master)
    except Exception:
        edu_pkg_dict = master if isinstance(master, dict) else {}
    encrypted_blob = encrypt_to_file_bytes(edu_pkg_dict)

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        if merged_bytes:
            st.download_button(
                f"📄 사람용 PDF ({_fmt_size(len(merged_bytes))})",
                merged_bytes,
                file_name=f"안전점검_보고서_{sid}.pdf",
                mime="application/pdf",
                type="primary",
                width="stretch",
                key="dl_unified_pdf",
                help="결재 첨부·인쇄용. 학교 별도 결재 양식에 첨부하세요.",
            )
    with dl_col2:
        st.download_button(
            f"🔒 암호화 데이터 ({_fmt_size(len(encrypted_blob))})",
            encrypted_blob,
            file_name=f"안전점검_데이터_{sid}.safeloop",
            mime="application/octet-stream",
            type="primary",
            width="stretch",
            key="dl_data_encrypted",
            help="자동 암호화 (AES-256). SafeLoop 앱 안에서만 복호화 가능. "
                  "모바일↔PC 동기화 + 교육청 발송용.",
        )

    st.caption(
        "🔒 **데이터 파일(.safeloop)은 자동 암호화**됩니다 — "
        "이메일·카톡 잘못 발송이나 파일 분실 시 외부인이 텍스트 에디터로 열어도 "
        "안전합니다. SafeLoop 앱끼리만 자동 복호화 됩니다.\n\n"
        "💡 **모바일에서 PC로 옮길 때** — 위 파일들을 다운로드한 뒤 "
        "**카톡 (나에게 보내기 또는 일반 채팅 공유)** · 이메일 · Google Drive · "
        "OneDrive · AirDrop 등 편한 방법으로 보내세요. PC 앱의 "
        "**📥 데이터 불러오기** 페이지에 .safeloop 파일을 업로드하면 자동 복호화 후 "
        "같은 데이터로 이어집니다."
    )

    with st.expander("개별 PDF 로 받기 (선택)", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(
                f"<div style='padding:10px 12px;border:1px solid #E5E5E8;"
                f"border-left:3px solid #D50000;border-radius:6px;background:#FFF;'>"
                f"<b>📄 공문 (품의서)</b><br>"
                f"<span style='font-size:11px;color:#6B6B70;'>결재 상신용 본문 · "
                f"{_fmt_size(len(letter_bytes))}</span></div>",
                unsafe_allow_html=True,
            )
            st.download_button(
                "다운로드", letter_bytes,
                file_name=f"공문_품의서_{sid}.pdf",
                mime="application/pdf",
                key="dl_letter_only", width="stretch",
            )
        with col_b:
            st.markdown(
                f"<div style='padding:10px 12px;border:1px solid #E5E5E8;"
                f"border-left:3px solid #D50000;border-radius:6px;background:#FFF;'>"
                f"<b>📊 점검 결과 보고서</b><br>"
                f"<span style='font-size:11px;color:#6B6B70;'>안전점수·카테고리·법령 근거 · "
                f"{_fmt_size(len(report_bytes))}</span></div>",
                unsafe_allow_html=True,
            )
            st.download_button(
                "다운로드", report_bytes,
                file_name=f"점검결과보고서_{sid}.pdf",
                mime="application/pdf",
                key="dl_report_only", width="stretch",
            )

# ─────────────────────────────────────────
# (5) 교육청 담당자 이메일로 발송 — 학교 담당자 전용
#
# 실 담당자는 본인 점검을 학교 담당자에게 제출하는 것까지만 가능.
# 교육청 발송은 학교 담당자가 우리 학교 실 담당자 제출본을 모두 검토·승인한 후
# 통합해서 한 번에 발송 (스프린트 4 통합 보고서).
# ─────────────────────────────────────────
if _is_space_role:
    divider()
    st.markdown(
        "<div style='padding:16px 18px;border:1px solid #C8E6C9;background:#F0F7F0;"
        "border-radius:6px;color:#2E7D32;font-size:13.5px;line-height:1.65;'>"
        "<b>✅ 학교 담당자 검토 대기 중</b><br>"
        "제출이 완료되면 학교 담당자가 결과를 검토합니다. "
        "수정 요청(반려)이 있으면 알림이 표시되며, 승인되면 교육청 통합 보고에 포함됩니다."
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "💡 교육청 직접 발송은 **학교 담당자**만 가능합니다. "
        "본 점검 외에도 다른 공간(다른 실 담당자) 제출이 있을 수 있으므로, "
        "학교 단위로 통합해서 한 번에 발송하는 흐름입니다."
    )
    st.stop()  # 실 담당자는 여기서 페이지 종료 — 아래 발송 흐름 미노출

divider()
section("05", "교육청 담당자 이메일로 발송",
        "내부 결재 완료 후 교육청 담당자 이메일에 점검 데이터(JSON·PDF) 첨부해 발송")

school_code = (school or {}).get("정보공시 학교코드")
school_sido = (school or {}).get("시도교육청", "")
edu_email_user = (st.session_state.get("edu_office_email") or "").strip()
my_email = st.session_state.get("my_email", "")

# 1) 발송 대상 결정 — 사용자 등록 이메일 우선, 없으면 시도교육청 공통 주소로 폴백
from modules.data_loader import get_sido_edu_email
edu_email_fallback = get_sido_edu_email(school_sido)
edu_email = edu_email_user or edu_email_fallback or ""
edu_email_source = (
    "사용자 등록" if edu_email_user
    else (f"{school_sido} 공통 주소 (자동)" if edu_email_fallback else "")
)

if not edu_email:
    st.warning(
        f"⚠ **교육청 담당자 이메일을 찾을 수 없습니다** — "
        f"학교 시도교육청({school_sido or '미상'})에 등록된 공통 주소가 없습니다. "
        f"설정 페이지에서 직접 등록해주세요."
    )
    if st.button("→ 설정 페이지에서 이메일 등록", key="goto_settings_email",
                  width="stretch"):
        st.switch_page("pages/8_설정.py")
else:
    _src_color = "#0A0A0B" if edu_email_user else "#D50000"
    st.markdown(
        f"<div style='padding:10px 14px;background:#F7F7F8;border:1px solid #E5E5E8;"
        f"border-radius:6px;font-size:13px;color:#6B6B70;'>"
        f"📬 발송 대상: <b style='color:#0A0A0B'>{edu_email}</b> "
        f"<span style='font-size:11px;color:{_src_color};'>· 출처: {edu_email_source}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if not edu_email_user and edu_email_fallback:
        st.caption(
            "💡 본교 담당 교육청 담당자의 직접 이메일을 알면 설정 페이지에 등록하세요. "
            "등록 시 그 주소가 우선 사용됩니다."
        )

    # 2) 내부 결재 확인 — 체크박스 + 결재자/일자 명시 (책임성 ↑)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown("##### 학교 내부 결재 확인")
    st.caption(
        "⚠ 본 체크는 **자기 선언** 으로, 실제 학교 결재 시스템(K-에듀파인 등)과 "
        "연동되지 않습니다. 별도 결재 양식으로 결재 진행 후 본 항목을 체크하세요. "
        "발송 데이터에는 결재자·일자가 함께 기록됩니다."
    )

    approval_done = st.checkbox(
        "**학교 내부 결재 완료** — 담당자 → 부장 → 교감 → 교장 결재(또는 등재) 완료를 확인합니다.",
        value=False,
        key="internal_approval_confirmed",
        help="결재 양식은 학교마다 다르므로, 별도 결재 진행 후 이 항목에 체크하세요.",
    )

    # 결재자·일자 입력 (선택 — 입력 시 발송 데이터에 함께 기록)
    if approval_done:
        col_app1, col_app2 = st.columns([2, 1])
        with col_app1:
            approver_name = st.text_input(
                "결재자 (선택) — 최종 결재자 이름",
                value=st.session_state.get("approver_name", ""),
                placeholder="예: 홍길동 (교장)",
                key="approver_name_input",
            )
            st.session_state["approver_name"] = approver_name
        with col_app2:
            import datetime as _dt_app
            approval_date = st.date_input(
                "결재 일자 (선택)",
                value=st.session_state.get("approval_date") or _dt_app.date.today(),
                key="approval_date_input",
            )
            st.session_state["approval_date"] = approval_date

    if not approval_done:
        st.caption("⚠ 결재 미완료 시 발송 버튼이 비활성화됩니다.")

    # 3) 발송 안내 (mailto 링크)
    saved_sid = st.session_state.get("saved_session_id")
    can_send = approval_done and bool(saved_sid)

    if not saved_sid:
        st.info("위에서 먼저 **점검 결과 저장**을 수행해야 발송 가능합니다.")

    school_name = (school or {}).get("학교명", "")
    space_type = (active_space or {}).get("type", "")
    space_nick = (active_space or {}).get("nickname", "")
    subject = f"[{school_name}] {space_type} 안전 점검 결과 제출"
    body_lines = [
        "안녕하세요, 교육청 담당자님.",
        "",
        f"{school_name}의 {space_type}"
        + (f" ({space_nick})" if space_nick else "")
        + " 안전 점검 결과를 제출합니다.",
        "",
        "첨부 파일 (2개):",
        " · 사람용 보고서 (PDF) — 결재·인쇄 용도",
        " · 암호화 데이터 파일 (.safeloop) — SafeLoop 수신함에서 자동 복호화",
        "",
        "※ .safeloop 파일은 SafeLoop 앱 안에서만 열립니다 (자동 암호화).",
        "",
        "감사합니다.",
    ]
    body = "\n".join(body_lines)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    if can_send:
        # ────────────────────────────────────────────────
        # 발송 방법 2가지 — 탭으로 명확히 분리
        # 방법 1 (권장): SafeLoop 다이렉트 전송 (1클릭, 수신 확인 추적)
        # 방법 2 (대체): 다운로드 + 본인 채널로 직접 전송
        # ────────────────────────────────────────────────
        tab_direct, tab_manual = st.tabs([
            "🚀 다이렉트 (권장)",
            "📤 다운로드 후 발송",
        ])

        # ── 방법 1: 다이렉트 전송 ──
        from modules.storage import (
            build_edu_package, submit_to_edu_inbox_direct, get_school_outbox,
        )
        with tab_direct:
            st.caption(
                "1번의 클릭으로 교육청 수신함에 직접 전송 — 학교 PC·교육청 PC 가 "
                "**같은 SafeLoop 데이터 폴더(또는 같은 클라우드 인스턴스)** 를 공유할 때 동작합니다. "
                "전송 후 교육청이 열람하면 자동으로 **수신 확인** 표시가 학교 측에 반영됩니다."
            )
            st.markdown(
                "<div style='padding:10px 14px;background:#F0F7F0;border:1px solid #C8E6C9;"
                "border-radius:6px;font-size:12px;color:#2E7D32;line-height:1.6;'>"
                "✅ 1번의 클릭 · ✅ 수신 확인 자동 추적 · ✅ 첨부 파일 누락 위험 없음<br>"
                "⚠ 단일 PC 또는 공유 데이터 폴더 환경 한정 — 분산 PC 환경은 정식 출시 시 검토."
                "</div>",
                unsafe_allow_html=True,
            )

            # 본교의 발송함에서 같은 세션·같은 공간에 대한 기존 발송 기록 조회
            _existing_subs = [
                r for r in get_school_outbox(school_code or "")
                if r.get("space_type") == (active_space or {}).get("type")
            ]
            already_sent = next(
                (r for r in _existing_subs
                 if (r.get("submitted_at", "") or "")[:10] ==
                    datetime.datetime.now().date().isoformat()),
                None,
            )

            if already_sent:
                read_at = already_sent.get("read_at")
                if read_at:
                    st.success(
                        f"✅ **교육청 수신 확인 완료** — "
                        f"발송: {already_sent.get('submitted_at','')[:16].replace('T',' ')} · "
                        f"열람: {(read_at or '')[:16].replace('T',' ')}"
                    )
                else:
                    st.info(
                        f"⏳ **발송 완료 · 수신 대기 중** — "
                        f"발송 시각: {already_sent.get('submitted_at','')[:16].replace('T',' ')} · "
                        f"발송 ID: `{already_sent.get('submit_id','-')}`"
                    )
                if st.button("🔄 다시 발송 (수정본)", key="resubmit_direct",
                              width="stretch"):
                    pass  # 아래 발송 버튼 흐름으로 떨어짐
                else:
                    # 같은 날짜 발송 기록이 있으면 추가 발송 차단 (사용자가 다시 발송 클릭 시 재전송)
                    pass

            # 발송 버튼
            if st.button("🚀 SafeLoop 수신함으로 다이렉트 전송",
                          type="primary", width="stretch",
                          key="submit_direct_btn"):
                try:
                    master = build_master_record({
                        **st.session_state,
                        "session_id": st.session_state.get("saved_session_id"),
                    })
                    edu_pkg = build_edu_package(master)
                    res = submit_to_edu_inbox_direct(edu_pkg)
                    if res.get("ok"):
                        st.success(
                            f"✅ 전송 완료 — 발송 ID `{res['submit_id']}` · "
                            f"수신 시도교육청: {res.get('sido')}\n\n"
                            f"교육청 담당자가 수신함에서 열람하면 이 화면에 "
                            f"**수신 확인** 이 자동 반영됩니다."
                        )
                        st.rerun()
                    else:
                        st.error("전송 실패 — 다시 시도하거나 방법 2를 사용하세요.")
                except Exception as e:
                    st.error(f"전송 중 오류: {e.__class__.__name__} — {e}")

        # ── 방법 2: 다운로드 + 직접 전송 ──
        with tab_manual:
            st.caption(
                "위에서 다운로드한 **PDF + .safeloop** 두 파일을 본인의 메일·카톡·드라이브로 "
                "직접 전송. 분산 환경(학교/교육청 PC 가 SafeLoop 을 공유 안 함)에서는 이 방법만 가능합니다. "
                "단, 수신 확인은 자동 반영되지 않습니다 (교육청 담당자가 받아 수신함에 업로드해야 추적 시작)."
            )
            st.markdown("##### 발송 정보 — 복사해서 사용")

            # ── 발송 정보 텍스트 박스 (복사 친화) ──
            col_send_a, col_send_b = st.columns([1, 1])
            with col_send_a:
                st.text_input("받는사람", value=edu_email, key="send_to_box",
                               help="클릭 후 Ctrl+A → Ctrl+C 로 복사")
                st.text_input("제목", value=subject, key="send_subject_box")
            with col_send_b:
                st.text_area("본문", value=body, height=170, key="send_body_box",
                              help="클릭 후 Ctrl+A → Ctrl+C 로 복사. 첨부 파일은 위에서 다운로드한 PDF + .safeloop")

            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

            # ── 한국 주요 웹메일·메신저 직접 열기 버튼 ──
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
            mailto = (
                f"mailto:{urllib.parse.quote(edu_email)}"
                f"?subject={urllib.parse.quote(subject)}"
                f"&body={urllib.parse.quote(body)}"
            )

            c1, c2, c3, c4 = st.columns(4)
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
            with c4:
                st.markdown(
                    f"<a href='{mailto}' target='_blank' style='display:block;"
                    f"padding:8px 0;background:#6B6B70;color:white;text-decoration:none;"
                    f"border-radius:6px;font-weight:600;text-align:center;font-size:13px;'>"
                    f"기본 메일 앱</a>", unsafe_allow_html=True,
                )

            st.caption(
                "💡 **카톡 공유** — 위 본문을 복사해 카톡 채팅에 붙여넣고 PDF·.safeloop "
                "파일을 함께 첨부 전송하세요."
            )
    else:
        st.button(
            "📤 발송하기 (결재 완료 후 활성화)",
            disabled=True, width="stretch", key="mailto_disabled",
        )

divider()
# 3-6: 저장 이후에만 다음 액션 버튼 노출
if st.session_state.get("saved_session_id"):
    colX, colY = st.columns(2)
    if colX.button("다른 공간 이어서 점검", width="stretch"):
        from modules.session import reset_inspection
        reset_inspection()
        st.switch_page("pages/1_점검시작.py")
    if colY.button("홈으로", width="stretch"):
        st.switch_page("app.py")
