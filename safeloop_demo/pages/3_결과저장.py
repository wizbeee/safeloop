"""
Step 6~7 — 공간별 점검 결과 확인 + AI 추천 + 이중 저장 + 에듀파인/앱 발송.

[1] 공간별 결과 확인 (당일 세션 내 여러 공간 비교 가능)
[2] AI 추천 안전 설비 (부재·불량 기준, 법령 근거 + 우선순위)
[3] 이중 저장 — Human-readable(PDF·Excel·CSV) + Machine-readable(JSON 3종)
[4] 에듀파인 발송 준비 (결재라인 지정 → 공문 품의서 + 첨부 ZIP 생성)
[5] 앱 직접 발송 (결재 완료 증빙 후에만 활성화 → 교육청 수신함으로 JSON 전송)
"""
from __future__ import annotations

import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.recommend import recommend_from_scores
from modules.session import ensure_state, require_school
from modules.storage import (
    build_csv,
    build_edufine_zip,
    build_excel,
    build_master_record,
    build_official_letter_pdf,
    build_pdf_report,
    list_recent_sessions,
    save_inspection,
    send_to_edu_app,
    clear_draft,
    korean_font_available,
)
from modules.ui import apply_theme, divider, hero, render_sidebar, section

st.set_page_config(page_title="결과 저장·발송 · SafeLoop", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="expanded")
apply_theme()
ensure_state()
render_sidebar(active_key="save")

school = require_school()
if not school:
    if st.button("← 학교 찾기로", key="save_noschool_back",
                  use_container_width=True):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

# 활성 공간 가드 (이전 페이지를 거치지 않은 경우)
active_space = st.session_state.get("active_space")
if not active_space:
    st.warning("점검할 공간이 선택되지 않았습니다. 점검 시작 페이지에서 공간을 선택해 주세요.")
    if st.button("← 공간 선택으로", key="save_nospace_back",
                  use_container_width=True):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

sr = st.session_state.get("score_result")
if not sr:
    st.warning("점검 결과가 아직 없습니다. AI 점검을 먼저 완료하세요.")
    if st.button("← AI 점검으로", key="save_noresult_back",
                  use_container_width=True):
        st.switch_page("pages/2_AI점검.py")
    st.stop()

hero(
    "STEP 03",
    "결과 저장",
    f"{school['학교명']} · {active_space.get('type', '-')} "
    f"({active_space.get('nickname') or '-'}) · 에듀파인/교육청 발송 포함",
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
    st.dataframe(df_prior, use_container_width=True, hide_index=True)
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
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────
# (2) AI 추천
# ─────────────────────────────────────────
divider()
section("02", "AI 추천 안전 설비", "부재·불량 설비에 대한 법령 근거 + 우선순위")

# AI 점검에서 자동 생성됨 — 없으면 즉시 자동 생성
recs = st.session_state.get("recommendations")
if recs is None:
    recs = recommend_from_scores(sr.get("raw", {}))
    st.session_state["recommendations"] = recs

if st.button("추천 재생성", help="점수를 변경했거나 새 분석 후 다시 산출"):
    st.session_state["recommendations"] = recommend_from_scores(sr.get("raw", {}))
    st.rerun()
recs = st.session_state.get("recommendations") or []
if recs:
    rec_df = pd.DataFrame(recs)[
        ["priority", "item", "category", "law", "article", "action", "reason"]
    ].rename(columns={
        "priority": "우선순위", "item": "항목", "category": "분류",
        "law": "법령", "article": "조항", "action": "조치", "reason": "사유",
    })
    st.dataframe(rec_df, use_container_width=True, hide_index=True)
    st.caption(f"총 {len(recs)}건 · 비용·구매처는 향후 확장 영역")
else:
    st.info("추천 항목이 없습니다. (전체 양호)")

# ─────────────────────────────────────────
# (3) 이중 저장
# ─────────────────────────────────────────
divider()
section("03", "학교 클라우드 저장", "사람이 읽는 형태와 기계가 읽는 형태 모두 자동 생성됩니다.")

st.markdown(
    "<div class='sl-card'>"
    "<b>사람이 읽는 형태</b> — PDF 보고서 · Excel · CSV · 공문(품의서) PDF<br>"
    "<b>기계가 읽는 형태</b> — 원본 JSON · 교육청 발송 패키지 JSON · 공공데이터 환원 패키지 JSON"
    "</div>",
    unsafe_allow_html=True,
)

col_save1, col_save2 = st.columns([2, 1])
with col_save1:
    if st.button("학교 클라우드에 저장", type="primary", use_container_width=True):
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
        st.success(f"저장 완료 · 세션 ID `{result['session_id']}`")
        with st.expander("생성된 파일"):
            for fn in result["files"]:
                st.markdown(f"- `{fn}`")

with col_save2:
    if st.session_state.get("saved_session_id"):
        st.success("✅ 저장됨")
        st.caption(st.session_state["saved_session_id"])

# 사용자 추가 다운로드
if st.session_state.get("saved_session_id"):
    st.markdown("##### 사용자 다운로드 (원하는 포맷 개별 선택)")
    if not korean_font_available():
        st.warning(
            "⚠ 시스템에 한글 PDF 폰트가 없어 PDF의 한글이 깨질 수 있습니다. "
            "Linux 서버라면 `apt install fonts-nanum fonts-noto-cjk` 후 재시작하세요. "
            "(Streamlit Cloud는 packages.txt로 자동 처리됨)"
        )

    master = build_master_record({**st.session_state,
                                   "session_id": st.session_state.get("saved_session_id")})

    cd1, cd2, cd3, cd4 = st.columns(4)
    cd1.download_button(
        "보고서 PDF",
        build_pdf_report(master),
        file_name=f"점검결과보고서_{st.session_state['saved_session_id']}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
    cd2.download_button(
        "Excel",
        build_excel(master),
        file_name=f"점검결과_{st.session_state['saved_session_id']}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    cd3.download_button(
        "CSV",
        build_csv(master),
        file_name=f"점검결과_{st.session_state['saved_session_id']}.csv",
        mime="text/csv",
        use_container_width=True,
    )
    cd4.download_button(
        "원본 JSON",
        bytes(__import__("json").dumps(master, ensure_ascii=False, indent=2), "utf-8"),
        file_name=f"master_{st.session_state['saved_session_id']}.json",
        mime="application/json",
        use_container_width=True,
    )

# ─────────────────────────────────────────
# (4) 에듀파인 업로드용 PDF 생성
# 결재라인·공식 경로 안내·ZIP·결재 시뮬은 모두 제거 — 실제 결재는 K-에듀파인에서.
# 본 앱은 결재 첨부용 통합 PDF 만 제공.
# ─────────────────────────────────────────
divider()
section("04", "에듀파인 업로드용 PDF",
        "공문 + 점검 결과 보고서를 하나의 PDF 로 묶어 다운로드 → 에듀파인에 첨부")

if st.button("📄 통합 PDF 생성", type="primary",
              key="build_edufine_pdf", use_container_width=True):
    if not st.session_state.get("saved_session_id"):
        save_inspection({**st.session_state, "timestamp": datetime.datetime.now().isoformat()})
    st.session_state["edu_package_ready"] = True
    st.session_state["_edufine_letter_cache"] = None
    st.session_state["_edufine_report_cache"] = None
    st.success("PDF 가 준비되었습니다. 아래에서 다운로드하세요.")

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

    if merged_bytes:
        st.download_button(
            f"📄 통합 PDF 다운로드 ({_fmt_size(len(merged_bytes))})",
            merged_bytes,
            file_name=f"안전점검_결재첨부_{sid}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
            key="dl_edufine_merged",
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
                key="dl_letter_only", use_container_width=True,
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
                key="dl_report_only", use_container_width=True,
            )

# ─────────────────────────────────────────
# (5) 교육청 수신함 전송 — 본교 점검 이력에서 다중 선택
# ─────────────────────────────────────────
divider()
section("05", "교육청 수신함 전송",
        "본교에 누적된 점검 이력 중 보낼 항목을 선택해 일괄 전송 (현재 점검만 또는 여러 건 동시)")

# 본교 점검 이력 로드
from modules.storage import list_recent_sessions
all_sessions = list_recent_sessions(limit=200)
school_code = (school or {}).get("정보공시 학교코드")
school_sessions = [s for s in all_sessions
                    if s.get("school_code") == school_code]

if not school_sessions:
    st.info(
        "본교에 저장된 점검 이력이 없습니다. 위에서 '학교 클라우드에 저장' 을 먼저 수행해주세요."
    )
else:
    # 현재 세션을 기본 선택, 나머지는 사용자 선택
    cur_sid = st.session_state.get("saved_session_id")
    options = []
    labels: dict[str, str] = {}
    for s in school_sessions:
        sid = s.get("session_id")
        if not sid:
            continue
        ts = (s.get("timestamp") or "")[:16].replace("T", " ")
        space_label = s.get("space_type") or "-"
        nick = s.get("space_nickname") or ""
        score = s.get("score")
        score_part = f" · {score:.1f}점" if isinstance(score, (int, float)) else ""
        labels[sid] = f"{ts} · {space_label}{(' (' + nick + ')') if nick else ''}{score_part}"
        options.append(sid)

    default_selected = [cur_sid] if cur_sid in options else (options[:1] if options else [])
    selected_sids = st.multiselect(
        "전송할 점검 세션 (여러 건 선택 가능)",
        options=options,
        default=default_selected,
        format_func=lambda s: labels.get(s, s),
        key="edu_send_select",
    )

    n_sel = len(selected_sids)
    sent_label = f"교육청 수신함으로 전송 ({n_sel}건)" if n_sel else "전송 대상을 선택하세요"
    if st.button(sent_label, type="primary",
                  disabled=(n_sel == 0),
                  use_container_width=True,
                  key="send_to_edu_app_multi"):
        results = []
        # 선택한 세션 각각에 대해 master.json 을 다시 로드해 send_to_edu_app 실행
        from pathlib import Path as _P
        from modules.storage import STORAGE_DIR as _STO
        for sid in selected_sids:
            # storage 폴더에서 해당 세션 master.json 찾기
            master_path = _P(_STO) / school_code / sid / "master.json"
            if not master_path.exists():
                results.append((sid, False, "master.json 없음"))
                continue
            try:
                import json as _json
                master = _json.loads(master_path.read_text(encoding="utf-8"))
                # send_to_edu_app 은 session(dict) 받음 — master 구조로 합성
                synth_session = {
                    "school": {
                        "정보공시 학교코드": school_code,
                        "학교명": (master.get("school") or {}).get("name"),
                    },
                    "active_space": {
                        "type": (master.get("space") or {}).get("type"),
                        "nickname": (master.get("space") or {}).get("nickname"),
                    },
                    "score_result": (master.get("inspection") or {}).get("score_result"),
                    "stage2_confirmed": (master.get("inspection") or {}).get("stage2_confirmed"),
                    "edufine_approved": True,  # 사용자가 전송 의사 표명 시 결재 완료 가정
                    "session_id": sid,
                    "timestamp": master.get("timestamp"),
                }
                r = send_to_edu_app(synth_session)
                results.append((sid, r.get("ok", False), r.get("reason") or r.get("path", "")))
            except Exception as e:
                results.append((sid, False, str(e)[:80]))

        ok_count = sum(1 for _, ok, _ in results if ok)
        fail_count = n_sel - ok_count
        if ok_count:
            st.session_state["edu_app_sent"] = True
            st.success(f"전송 완료 — 성공 {ok_count}건 / 실패 {fail_count}건")
            if fail_count == 0:
                st.balloons()
        else:
            st.error("모든 전송이 실패했습니다.")

        with st.expander("전송 상세 보기", expanded=(fail_count > 0)):
            for sid, ok, info in results:
                ico = "✅" if ok else "❌"
                st.markdown(f"- {ico} `{sid}` — {info}")

if st.session_state.get("edu_app_sent"):
    st.info(
        "교육청 수신함에서 검증·익명화 후 KEIIS 업로드 → 공공데이터 환원이 이어집니다. "
        "진행 상황은 **🔁 내 제출 추적** 페이지에서 확인할 수 있습니다."
    )
    colN1, colN2 = st.columns(2)
    if colN1.button("내 제출 추적 보기", use_container_width=True):
        st.switch_page("pages/6_데이터순환.py")
    if colN2.button("본교 현황 보기", use_container_width=True):
        st.switch_page("pages/4_본교현황.py")

divider()
# 3-6: 저장 이후에만 다음 액션 버튼 노출
if st.session_state.get("saved_session_id"):
    colX, colY = st.columns(2)
    if colX.button("다른 공간 이어서 점검", use_container_width=True):
        from modules.session import reset_inspection
        reset_inspection()
        st.switch_page("pages/1_점검시작.py")
    if colY.button("홈으로", use_container_width=True):
        st.switch_page("app.py")
