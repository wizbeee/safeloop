"""
데이터 불러오기 — 모바일↔PC 동기화의 핵심 페이지.

모바일에서 점검 후 받은 .safeloop (암호화) 또는 .json (평문) 파일을 업로드하면
앱이 자동 복호화 → 상세 미리보기 → 사람용 PDF 즉시 다운로드 + 세션 복원 → 후속 작업.

지원 형식:
- .safeloop : SafeLoop 앱이 자동 암호화한 파일 (AES-256-GCM)
- .json     : 평문 JSON (이전 버전 호환)
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from modules.crypto import decrypt_payload, is_encrypted
from modules.session import ensure_state
from modules.ui import apply_theme, divider, hero, render_sidebar, section

st.set_page_config(page_title="데이터 불러오기 · SafeLoop",
                    page_icon="static/icon-192.png",
                    layout="wide", initial_sidebar_state="expanded")
apply_theme()
ensure_state()
render_sidebar(active_key="load")

hero("LOAD", "데이터 불러오기",
     "모바일 → PC 동기화 + 받은 파일 상세 보기 + 결재용 PDF 즉시 다운로드.")

st.markdown(
    "<div style='padding:14px 18px;background:#F7F7F8;border:1px solid #E5E5E8;"
    "border-radius:8px;margin-bottom:16px;'>"
    "<b>📱 → 💻 모바일에서 PC로 옮기는 흐름</b><br>"
    "<span style='font-size:13px;color:#6B6B70;line-height:1.7;'>"
    "1. 모바일에서 점검 완료 → <b>🔒 암호화 데이터 (.safeloop)</b> 다운로드<br>"
    "2. 카톡 (나에게 / 일반 채팅) · 이메일 · Google Drive · OneDrive · AirDrop 등으로 PC에 전송<br>"
    "3. PC 에서 이 페이지에 .safeloop 파일 업로드 → <b>자동 복호화</b><br>"
    "4. 상세 미리보기 + 결재용 PDF 다운로드 + 본교 현황·이력 페이지로 이동"
    "</span></div>",
    unsafe_allow_html=True,
)

divider()
section("01", "파일 업로드", ".safeloop 또는 .json")

uploaded = st.file_uploader(
    "안전점검 데이터 파일",
    type=["safeloop", "json"],
    accept_multiple_files=False,
    key="data_load_uploader",
)

if uploaded is None:
    st.info("👆 위에 파일을 업로드하세요.")
    st.stop()

# 자동 복호화 (또는 평문 JSON 파싱)
try:
    raw = uploaded.read()
    data = decrypt_payload(raw)
    encrypted = is_encrypted(raw)
except Exception as e:
    st.error(
        f"⚠ 파일을 읽을 수 없습니다: {e}\n\n"
        "이 파일이 SafeLoop 앱이 만든 .safeloop 또는 .json 인지 확인하세요."
    )
    st.stop()

# 두 형식 호환 — master 형식 / edu_package 형식
school_info = data.get("school") or data.get("school_identified") or {}
space_info = data.get("space") or {}
inspection = data.get("inspection") or {}
score_result = (
    inspection.get("score_result")
    or {
        "score": data.get("safety_score"),
        "grade": data.get("grade"),
        "category_scores": data.get("category_scores", {}),
    }
)
recommendations = data.get("recommendations") or []
checklist_items = data.get("checklist_items") or (
    (inspection.get("stage3") or {}).get("items", [])
)
detected_eq = data.get("detected_equipment") or []
absent_eq = data.get("absent_equipment") or []

school_name = school_info.get("name") or school_info.get("학교명") or "(불명)"
school_code = school_info.get("code") or school_info.get("정보공시 학교코드") or "(불명)"
sido = school_info.get("sido") or "(불명)"
space_type = space_info.get("type") or "(불명)"
space_nick = space_info.get("nickname") or ""
score = score_result.get("score") or "-"
grade = score_result.get("grade") or "-"
timestamp = data.get("timestamp") or data.get("submission_timestamp") or "-"

# 파일 형식 안내 — 톤 통일
if encrypted:
    st.success(
        "🔒 **SafeLoop 암호화 파일 (.safeloop)** — 자동 복호화 성공. 안전하게 읽었습니다."
    )
else:
    st.info(
        "📄 **평문 JSON 파일** — 이전 버전 호환으로 정상 처리합니다."
    )

# ─────────────────────────────────────────
# (02) 미리보기 — 핵심 메트릭
# ─────────────────────────────────────────
divider()
section("02", "미리보기", "받은 데이터의 핵심 정보")

m_col1, m_col2, m_col3, m_col4 = st.columns(4)
m_col1.metric("학교", school_name)
m_col2.metric("공간", f"{space_type}{(' (' + space_nick + ')') if space_nick else ''}")
m_col3.metric("안전 점수", f"{score}점" if score != "-" else "-")
m_col4.metric("등급", grade)
st.caption(f"🏫 {school_code} · {sido} · 📅 {timestamp}")

# 카테고리별 점수
cat_scores = score_result.get("category_scores") or {}
if cat_scores:
    st.markdown("##### 카테고리별 점수")
    cat_rows = [
        {"카테고리": k, "점수": (v or {}).get("score", 0),
         "가중치합": (v or {}).get("weight_sum", 0)}
        for k, v in cat_scores.items()
    ]
    cat_df = pd.DataFrame(cat_rows)
    st.dataframe(cat_df, width="stretch", hide_index=True)

# 탐지·부재 설비
if detected_eq or absent_eq:
    eq_col1, eq_col2 = st.columns(2)
    with eq_col1:
        if detected_eq:
            st.markdown("##### ✓ 탐지된 설비")
            st.dataframe(pd.DataFrame(detected_eq), width="stretch",
                          hide_index=True)
    with eq_col2:
        if absent_eq:
            st.markdown("##### ✗ 부재 설비")
            st.dataframe(pd.DataFrame(absent_eq), width="stretch",
                          hide_index=True)

# 점검표 항목
if checklist_items:
    with st.expander(f"📋 점검표 항목 전체 ({len(checklist_items)}개)", expanded=False):
        st.dataframe(pd.DataFrame(checklist_items),
                      width="stretch", hide_index=True)

# AI 추천
if recommendations:
    with st.expander(f"🎯 AI 추천 안전 설비 ({len(recommendations)}건)", expanded=False):
        st.dataframe(pd.DataFrame(recommendations),
                      width="stretch", hide_index=True)

# ─────────────────────────────────────────
# (03) 즉시 다운로드 — 사람용 PDF (결재·인쇄용)
# ─────────────────────────────────────────
divider()
section("03", "즉시 다운로드", "결재·인쇄용 PDF — 결과 저장 페이지로 이동 안 해도 됨")

try:
    from modules.storage import build_pdf_report
    # 데이터 형식이 master 와 다를 수 있어 합성
    synth_master = {
        "school": {
            "name": school_name,
            "code": school_code,
            "sido": sido,
            "region": school_info.get("region", ""),
            "level": school_info.get("level", ""),
            "establishment": school_info.get("establishment", ""),
        },
        "space": {
            "type": space_type,
            "nickname": space_nick,
            "floor": space_info.get("floor"),
        },
        "ai_pipeline": {
            "stage1": {"space_type_primary": space_type, "confidence": 1.0},
        },
        "inspection": {
            "score_result": score_result,
        },
        "recommendations": recommendations,
        "approval": {"eduline": {}, "internal_approval_confirmed": True},
        "timestamp": timestamp,
    }
    pdf_bytes = build_pdf_report(synth_master)
    st.download_button(
        f"📄 결재용 PDF 다운로드 ({len(pdf_bytes) // 1024} KB)",
        pdf_bytes,
        file_name=f"안전점검_보고서_{school_code}_{timestamp[:10]}.pdf",
        mime="application/pdf",
        type="primary",
        width="stretch",
        key="dl_pdf_from_load",
    )
    st.caption(
        "💡 PC에서 인쇄 → 학교 별도 결재 양식에 첨부 → 결재 진행."
    )
except Exception as e:
    st.warning(f"PDF 생성 실패: {e}")

# ─────────────────────────────────────────
# (04) 세션 복원 + 페이지 이동
# ─────────────────────────────────────────
divider()
section("04", "세션 복원 + 다음 작업", "복원 후 어디로 갈지 선택")

dest_label_to_page = {
    "본교 현황 (누적 통계·차트)": "pages/4_본교현황.py",
    "결과 저장 (다시 다운로드·교육청 발송)": "pages/3_결과저장.py",
    "점검 이력 (시계열 추이)": "pages/10_점검이력.py",
    "현재 페이지 유지": None,
}
dest_choice = st.radio(
    "복원 후 이동할 페이지",
    options=list(dest_label_to_page.keys()),
    index=0,
    key="data_load_dest_choice",
    horizontal=False,
)

if st.button("✅ 이 데이터로 세션 복원 + 이동",
              type="primary", width="stretch",
              key="apply_loaded_data"):
    if school_code != "(불명)":
        st.session_state["school"] = {
            "정보공시 학교코드": school_code,
            "학교명": school_name,
            "시도교육청": sido,
            "지역": school_info.get("region", ""),
            "학교급": school_info.get("level", ""),
            "설립구분": school_info.get("establishment", ""),
        }
        st.session_state["auth_verified"] = True
    if space_type != "(불명)":
        st.session_state["active_space"] = {
            "space_id": space_info.get("space_id", "loaded"),
            "school_code": school_code,
            "type": space_type,
            "nickname": space_nick or None,
            "floor": space_info.get("floor"),
        }
    # ─── 점검 파이프라인 전체 복원 (Stage 1/2/3 + 점수 + 추천) ───
    # master 형식과 edu_package 형식 모두 호환.
    if isinstance(inspection, dict):
        # Stage 1 (공간 1차 추정 — 사용자 등록 정보 우선이지만 백업으로 복원)
        stage1 = inspection.get("stage1") or inspection.get("stage1_result")
        if stage1:
            st.session_state["stage1_result"] = stage1
        # Stage 2 (탐지된 설비)
        stage2 = inspection.get("stage2") or inspection.get("stage2_result")
        if stage2:
            st.session_state["stage2_result"] = stage2
        if inspection.get("stage2_confirmed"):
            st.session_state["stage2_confirmed"] = inspection["stage2_confirmed"]
        # Stage 3 (점검표)
        stage3 = inspection.get("stage3") or inspection.get("stage3_result")
        if stage3:
            st.session_state["stage3_result"] = stage3
        # 사용자 입력 점검표 점수 + 종합 점수
        if inspection.get("item_scores"):
            st.session_state["item_scores"] = inspection["item_scores"]
        if inspection.get("score_result"):
            st.session_state["score_result"] = inspection["score_result"]
    elif score_result:
        st.session_state["score_result"] = score_result

    # 추천 — inspection 안 또는 최상위 키 모두 시도
    recs = (
        (inspection.get("recommendations") if isinstance(inspection, dict) else None)
        or recommendations
    )
    if recs:
        st.session_state["recommendations"] = recs

    # 결재라인·내부결재 상태
    approval = data.get("approval") or {}
    if approval.get("eduline"):
        st.session_state["eduline"] = approval["eduline"]
    if approval.get("internal_approval_confirmed"):
        st.session_state["internal_approval_confirmed"] = True

    # 저장 세션 ID — "이미 저장된 점검을 다시 불러온 것"임을 명시
    sid = (
        data.get("session_id")
        or (inspection.get("session_id") if isinstance(inspection, dict) else None)
    )
    if sid:
        st.session_state["saved_session_id"] = sid
        # 점검 이력에서 같은 점검으로 인지 — 미저장 경고도 사라짐
        st.session_state.setdefault("_recent_saved_ids", [])
        if sid not in st.session_state["_recent_saved_ids"]:
            st.session_state["_recent_saved_ids"].insert(0, sid)
            st.session_state["_recent_saved_ids"] = st.session_state["_recent_saved_ids"][:10]

    # 드래프트 복원 플래그 — 위저드 모드 진입 시 처음부터 시작
    st.session_state["_draft_restored"] = True
    st.session_state["wizard_step"] = "result" if sid else "shoot_1"

    target_page = dest_label_to_page[dest_choice]
    st.toast("세션 복원 완료 — Stage 1/2/3 + 점수 + 추천 모두 적용", icon="🔄")
    if target_page:
        st.switch_page(target_page)
    else:
        st.success("복원 완료 — 사이드바에서 이동하세요.")

divider()
st.caption(
    "💡 **참고** — 사진은 데이터 파일에 포함되지 않습니다 (용량 문제). "
    "사진까지 옮기려면 모바일 갤러리에서 직접 카톡·드라이브 등으로 보내세요."
)
