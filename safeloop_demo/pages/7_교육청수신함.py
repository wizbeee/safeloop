"""
교육청 담당자 수신함 (옵션 2).

학교 앱이 에듀파인 결재 완료 증빙 후 직접 발송한 구조화 JSON을 수신.
교육청 담당자는 여기서 데이터를 검토·승인 후 KEIIS에 업로드(수동).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from modules.session import ensure_state
from modules.storage import EDU_RECEIPT_DIR, list_edu_inbox
from modules.ui import apply_theme, divider, hero, render_sidebar, section

st.set_page_config(page_title="교육청 수신함 · SafeLoop", page_icon="/",
                   layout="wide", initial_sidebar_state="expanded")
apply_theme()
ensure_state()
render_sidebar(active_key="edu_inbox")

hero("EDU OFFICE", "교육청 담당자 수신함",
     "학교에서 에듀파인 결재 완료 후 직접 발송한 구조화 JSON 수신 — KEIIS 업로드 지원.")

# 역할 안내
if st.session_state.get("role") != "교육청":
    st.warning("현재 역할이 **학교 담당자**로 설정되어 있습니다. 홈에서 '교육청 담당자'로 전환하면 본 수신함이 주 화면이 됩니다.")

# 수신함 리스트
inbox = list_edu_inbox()

c1, c2, c3 = st.columns(3)
c1.metric("총 수신 건수", f"{len(inbox)}건")
c2.metric("관할 시도", f"{len(set(x['sido'] for x in inbox))}개")
avg_score = (sum(x.get("score") or 0 for x in inbox) / len(inbox)) if inbox else 0
c3.metric("평균 안전 점수", f"{avg_score:.1f}점")

divider()

# 필터
sidos = sorted({x["sido"] for x in inbox})
sel_sido = st.selectbox("시도 필터", ["(전체)"] + sidos)

filtered = inbox if sel_sido == "(전체)" else [x for x in inbox if x["sido"] == sel_sido]

if not filtered:
    st.info("수신된 데이터가 없습니다. 학교에서 결재 완료 후 '앱 직접 발송'을 수행하면 여기에 표시됩니다.")
    st.stop()

# ─────────────────────────────────────────
# 마스터-디테일 레이아웃 (좌 리스트 / 우 상세)
# ─────────────────────────────────────────
master_col, detail_col = st.columns([2, 3], gap="large")

with master_col:
    section("01", "수신 목록", f"{len(filtered)}건")
    df = pd.DataFrame(filtered)[["received_at", "sido", "school", "space_type",
                                  "score", "grade", "file"]]
    df.columns = ["수신일시", "시도", "학교명", "공간", "점수", "등급", "파일"]
    df["수신일시"] = df["수신일시"].astype(str).str[:16]
    st.dataframe(df.drop(columns=["파일"]), use_container_width=True,
                  hide_index=True, height=520)

# 상세 보기
files = [f"{x['sido']} / {x['file']}" for x in filtered]
with detail_col:
    section("02", "상세 조회")
    picked = st.selectbox("건 선택", files, label_visibility="collapsed")
    if picked:
        sido_name, fname = picked.split(" / ", 1)
        target = EDU_RECEIPT_DIR / sido_name / fname
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except Exception as e:
            st.error(f"파일 로드 실패: {e}")
            st.stop()

        st.markdown("##### 기본 정보")
        school = data.get("school_identified") or {}
        space = data.get("space") or {}
        st.markdown(f"- **학교**: {school.get('name','-')}")
        st.markdown(f"- **코드**: `{school.get('code','-')}`")
        st.markdown(f"- **소재**: {school.get('sido','-')} · {school.get('region','-')}")
        st.markdown(f"- **공간**: {space.get('type','-')} ({space.get('nickname') or '-'})")
        st.markdown(f"- **종합점수**: **{data.get('safety_score','-')}점** "
                    f"/ 등급 **{data.get('grade','-')}**")
        st.markdown(f"- **근거 법령**: {data.get('basis_law','-')}")

        with st.expander("카테고리 점수 / 설비 / 점검표 / 추천", expanded=False):
            cat = data.get("category_scores") or {}
            cat_df = pd.DataFrame([
                {"카테고리": k, "점수": v.get("score", 0),
                 "가중치합": v.get("weight_sum", 0)} for k, v in cat.items()
            ])
            if not cat_df.empty:
                st.markdown("**카테고리 점수**")
                st.dataframe(cat_df, use_container_width=True, hide_index=True)

            det = data.get("detected_equipment") or []
            if det:
                st.markdown("**탐지된 설비**")
                st.dataframe(pd.DataFrame(det), use_container_width=True, hide_index=True)

            absent = data.get("absent_equipment") or []
            if absent:
                st.markdown("**부재 설비**")
                st.dataframe(pd.DataFrame(absent), use_container_width=True, hide_index=True)

            recs = data.get("recommendations") or []
            if recs:
                st.markdown("**AI 추천**")
                st.dataframe(pd.DataFrame(recs), use_container_width=True, hide_index=True)

            items = data.get("checklist_items") or []
            if items:
                st.markdown("**점검표**")
                st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)

        # 검토 액션
        st.markdown("##### 검토 처리")
        action = st.radio(
            "검토 결과",
            ["대기", "승인 (KEIIS 업로드 준비)", "반려 (학교에 수정 요청)"],
            horizontal=True,
        )
        memo = st.text_area("검토 메모", placeholder="품질 이슈·보완 요청 사항 등",
                            height=80)

        col_x, col_y = st.columns(2)
        with col_x:
            if st.button("처리 저장 (시연 Mock)", use_container_width=True):
                log_path = target.with_suffix(".review.json")
                log_path.write_text(
                    json.dumps({"action": action, "memo": memo}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                st.success(f"저장됨: `{log_path.name}`")
        with col_y:
            st.download_button(
                "KEIIS JSON 다운로드",
                json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=fname,
                mime="application/json",
                use_container_width=True,
            )

divider()
st.info(
    "**앱 포지셔닝**: 본 수신함은 교육부·교육청과의 공식 협력 전 단계의 **Mock 수신 모듈**입니다. "
    "향후 KEIIS API 직접 연동으로 확장되며, 그 전까지는 교육청 담당자가 수신 데이터를 KEIIS에 수동 이관합니다."
)
