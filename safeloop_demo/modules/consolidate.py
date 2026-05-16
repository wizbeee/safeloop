"""
학교 단위 통합 보고서 생성 — Sprint 3 일부 + Sprint 4.

학교 담당자가 본교의 승인(approved)된 점검 제출본들을 한 묶음으로 묶어
교육청에 통합 발송하기 위한 산출물 생성:

- 학교 단위 통합 master (모든 공간 한 묶음)
- 통합 PDF (학교 요약 + 공간별 점수 표)
- 통합 Excel (요약 시트 + 공간별 점검표 시트)
- 교육청 발송용 JSON (record_type=safeloop_consolidated_submission)
- 발송 후 상태 일괄 consolidated 로 갱신

운영 흐름:
1. 학교 담당자가 [수합·검토] 페이지에서 실 담당자 제출들 검토·승인
2. 같은 페이지 하단 [본교 통합 발송] 섹션에서 승인된 항목들 선택
3. 통합 PDF + Excel + JSON 미리보기·다운로드
4. 교육청 발송 (이메일 또는 다이렉트) 상태 일괄 consolidated 로
"""
from __future__ import annotations

import datetime
import io
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from modules.storage import (
    _ensure_font,
    list_school_submissions,
    load_master_record,
    update_submission_status,
)


# ─────────────────────────────────────────
# 1. 통합 가능한 제출본 조회
# ─────────────────────────────────────────
def list_consolidatable(school_code: str) -> list[dict]:
    """통합 가능한 제출본 — 상태가 approved (학교 담당자 승인 완료)인 것만.

    consolidated(이미 통합 발송됨) / submitted(검토 대기) / returned(반려) 는
    포함하지 않는다. 학교 담당자가 [수합·검토] 에서 승인한 항목만 통합 대상.
    """
    return list_school_submissions(school_code, status_filter="approved")


# ─────────────────────────────────────────
# 2. 통합 record 생성
# ─────────────────────────────────────────
def build_consolidated_record(
    school_code: str,
    session_ids: list[str],
    school_admin_name: str = "",
) -> dict:
    """여러 세션을 묶은 학교 단위 통합 마스터 (교육청 발송용).

    Args:
        school_code: 학교 코드
        session_ids: 통합할 세션 ID 리스트 (모두 approved 상태여야 의미 있음)
        school_admin_name: 학교 담당자 이름 (PDF/공문에 노출)

    Returns:
        dict — record_type=safeloop_consolidated_submission
    """
    spaces: list[dict] = []
    details: list[dict] = []
    school_info: dict = {}

    for sid in session_ids:
        master = load_master_record(school_code, sid)
        if not master:
            continue

        if not school_info:
            school_info = master.get("school") or {}

        score_result = (
            (master.get("inspection") or {}).get("score_result") or {}
        )
        submitter = master.get("submitter") or {}

        # status_history 에서 가장 최근 approved 항목의 타임스탬프
        approved_at = None
        for h in (master.get("status_history") or []):
            if h.get("status") == "approved":
                approved_at = h.get("at") # 최신값으로 덮어씀 — loop 끝에서 가장 최근

        items_count = len(
            ((master.get("ai_pipeline") or {}).get("stage3") or {}).get("items")
            or []
        )

        spaces.append({
            "session_id": sid,
            "space_id": (master.get("space") or {}).get("id"),
            "space_type": (master.get("space") or {}).get("type"),
            "space_nickname": (master.get("space") or {}).get("nickname"),
            "score": score_result.get("score"),
            "grade": score_result.get("grade"),
            "category_scores": score_result.get("category_scores"),
            "submitter_name": submitter.get("name"),
            "submitter_role": submitter.get("role"),
            "submitter_manager_id": submitter.get("manager_id"),
            "items_count": items_count,
            "approved_at": approved_at,
        })
        details.append(master)

    # 평균 점수
    avg_score = None
    if spaces:
        valid = [s["score"] for s in spaces
                 if isinstance(s.get("score"), (int, float))]
        if valid:
            avg_score = round(sum(valid) / len(valid), 1)

    return {
        "schema_version": "1.0",
        "record_type": "safeloop_consolidated_submission",
        "basis_law": (
            "교육시설법 제10조 제3항 — 안전·유지관리기준 자체 점검 "
            "(학교 단위 통합 보고)"
        ),
        "submission_timestamp": datetime.datetime.now().isoformat(),
        "school": school_info,
        "school_admin": school_admin_name,
        "spaces_count": len(spaces),
        "average_score": avg_score,
        "spaces": spaces,
        # details 는 무거우니 옵션 (교육청에서 세부 확인 필요 시 사용)
        "details": details,
    }


# ─────────────────────────────────────────
# 3. 통합 Excel 생성 — 학교 요약 시트 + 공간별 점검표 시트
# ─────────────────────────────────────────
def build_consolidated_excel(consolidated: dict) -> bytes:
    """통합 Excel.

    시트 구성:
    1. "학교 요약" — 공간별 점수·등급·제출자 한 줄씩
    2. "공간_<유형>" — 각 공간의 점검표 항목 (양호/불량/부재)

    교육청 담당자가 KEIIS 등에 빠르게 입력하기 좋은 형식.
    """
    buf = io.BytesIO()

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # 시트 1: 학교 요약
        spaces = consolidated.get("spaces") or []
        if spaces:
            summary_df = pd.DataFrame([{
                "번호": i + 1,
                "공간 유형": s.get("space_type") or "",
                "별칭": s.get("space_nickname") or "",
                "안전 점수": s.get("score"),
                "등급": s.get("grade"),
                "제출자": s.get("submitter_name") or "",
                "제출자 역할": s.get("submitter_role") or "",
                "점검 항목 수": s.get("items_count"),
                "승인 일시": (s.get("approved_at") or "").replace("T", " ")[:19],
                "세션 ID": s.get("session_id"),
            } for i, s in enumerate(spaces)])
            summary_df.to_excel(writer, sheet_name="학교 요약", index=False)

        # 시트 2~: 공간별 점검표
        for i, master in enumerate(consolidated.get("details") or []):
            space_type = (master.get("space") or {}).get("type") or f"공간{i+1}"
            space_nick = (master.get("space") or {}).get("nickname") or ""

            stage3 = ((master.get("ai_pipeline") or {}).get("stage3") or {})
            items = stage3.get("items") or []
            item_scores = (
                (master.get("inspection") or {}).get("item_scores") or {}
            )

            rows = []
            for it in items:
                no = it.get("no")
                # 점수 키 후보 (저장 패턴 다양)
                raw = (
                    item_scores.get(str(no))
                    or item_scores.get(no)
                    or item_scores.get(it.get("title", ""))
                )
                try:
                    raw_f = float(raw) if raw is not None else None
                except Exception:
                    raw_f = None
                label = {
                    1.0: "양호", 0.5: "불량", 0.0: "부재",
                }.get(raw_f, "미입력")

                rows.append({
                    "번호": no,
                    "분류": it.get("category"),
                    "점검 제목": it.get("title"),
                    "점검 방법": it.get("method"),
                    "합격 기준": it.get("criterion"),
                    "법적 근거": it.get("basis"),
                    "우선순위": it.get("priority"),
                    "점검 결과": label,
                })

            if rows:
                df = pd.DataFrame(rows)
                # Excel 시트명은 31자 + 일부 문자 제한 안전화
                sheet_label = f"{i+1}.{space_type}"
                if space_nick:
                    sheet_label += f"_{space_nick}"
                safe = "".join(
                    c if c.isalnum() or c in " _-" else "_"
                    for c in sheet_label
                )[:31]
                df.to_excel(writer, sheet_name=safe or f"공간{i+1}", index=False)

    return buf.getvalue()


# ─────────────────────────────────────────
# 4. 통합 PDF 생성 — 학교 요약 표지 + 공간별 점수 표
# ─────────────────────────────────────────
def build_consolidated_pdf(consolidated: dict) -> bytes:
    """통합 PDF — 학교 요약 + 공간별 점수 표 (1~2장 분량).

    상세 점검표는 동봉 Excel/JSON 참조. PDF 는 결재·인쇄·열람용.
    """
    font_name = _ensure_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )

    elements: list[Any] = []

    title_style = ParagraphStyle(
        "Title", fontName=font_name, fontSize=18,
        alignment=1, spaceAfter=14, leading=22,
    )
    h2 = ParagraphStyle(
        "H2", fontName=font_name, fontSize=13,
        spaceBefore=12, spaceAfter=8, leading=16,
    )
    body = ParagraphStyle(
        "Body", fontName=font_name, fontSize=10, leading=14,
    )
    small = ParagraphStyle(
        "Small", fontName=font_name, fontSize=9, leading=12,
        textColor=colors.HexColor("#6B6B70"),
    )

    school = consolidated.get("school") or {}
    school_name = school.get("name") or "학교"
    spaces_count = consolidated.get("spaces_count", 0)
    avg_score = consolidated.get("average_score")
    ts = (consolidated.get("submission_timestamp") or "")[:10]

    # 표지
    elements.append(Paragraph(
        f"{school_name} — 안전 점검 통합 보고서",
        title_style,
    ))
    elements.append(Paragraph(
        f"기준일 {ts} · 공간 {spaces_count}개 · "
        f"평균 점수 {avg_score if avg_score is not None else '-'}",
        body,
    ))
    if consolidated.get("school_admin"):
        elements.append(Paragraph(
            f"학교 담당자: {consolidated['school_admin']}",
            body,
        ))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(
        f"근거: {consolidated.get('basis_law', '')}",
        small,
    ))
    elements.append(Spacer(1, 0.5 * cm))

    # 공간별 요약 표
    elements.append(Paragraph("공간별 안전 점수 요약", h2))
    spaces = consolidated.get("spaces") or []
    if spaces:
        table_data: list[list[str]] = [
            ["#", "공간 유형", "별칭", "점수", "등급", "제출자"]
        ]
        for i, s in enumerate(spaces):
            disp_submitter = (
                f"{s.get('submitter_name', '-')} "
                f"({s.get('submitter_role', '?')})"
            )
            table_data.append([
                str(i + 1),
                str(s.get("space_type") or ""),
                str(s.get("space_nickname") or "-"),
                str(s.get("score") if s.get("score") is not None else "-"),
                str(s.get("grade") or "-"),
                disp_submitter,
            ])
        tbl = Table(
            table_data,
            colWidths=[1 * cm, 3 * cm, 3.5 * cm, 1.5 * cm, 1.2 * cm, 6 * cm],
            repeatRows=1,
        )
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E2761")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#999999")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F7F7F8")]),
        ]))
        elements.append(tbl)
    else:
        elements.append(Paragraph("(승인된 점검이 없습니다)", body))

    # 등급 분포 요약
    if spaces:
        grade_dist: dict[str, int] = {}
        for s in spaces:
            g = s.get("grade") or "-"
            grade_dist[g] = grade_dist.get(g, 0) + 1
        if grade_dist:
            elements.append(Spacer(1, 0.5 * cm))
            elements.append(Paragraph("등급 분포", h2))
            dist_str = " · ".join(
                f"{g}: {n}개" for g, n in sorted(grade_dist.items())
            )
            elements.append(Paragraph(dist_str, body))

    elements.append(Spacer(1, 0.8 * cm))
    elements.append(Paragraph(
        "본 보고서는 SafeLoop 시스템이 자동 생성한 통합본입니다. "
        "각 공간별 상세 점검표(항목·법령 근거)는 동봉된 Excel 또는 "
        "JSON 첨부를 참조해주세요. 결재는 K-에듀파인 등 별도 양식에서 진행합니다.",
        small,
    ))

    doc.build(elements)
    return buf.getvalue()


# ─────────────────────────────────────────
# 5. 상태 일괄 변경 (consolidated)
# ─────────────────────────────────────────
def mark_consolidated(
    school_code: str,
    session_ids: list[str],
    by: str,
    note: str = "통합 발송",
) -> int:
    """approved 제출본들을 consolidated 상태로 일괄 변경.

    Returns: 성공한 개수
    """
    n = 0
    for sid in session_ids:
        if update_submission_status(
            school_code, sid, "consolidated",
            by=by, by_role="학교", note=note,
        ):
            n += 1
    return n
