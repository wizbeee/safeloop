"""
이중 저장 모듈 — Human-readable + Machine-readable 동시 생성.

Human-readable: PDF, Excel(.xlsx), CSV
Machine-readable: 원본 JSON + 교육청 발송 패키지 JSON + 공공데이터 환원 패키지 JSON

저장 경로: school_storage/{학교코드}/{점검ID}/
"""
from __future__ import annotations

import datetime
import io
import json
import uuid
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, SimpleDocTemplate, PageBreak,
)

from modules.data_loader import anonymize_code

ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = ROOT / "school_storage"
EDU_RECEIPT_DIR = ROOT / "mock_edu_receipt"
STORAGE_DIR.mkdir(exist_ok=True)
EDU_RECEIPT_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────
# 한글 폰트 등록 (ReportLab)
# ─────────────────────────────────────────
_FONT_REGISTERED = False


_FONT_FALLBACK_USED = False


def _ensure_font() -> str:
    """시스템 폰트를 찾아 PDF에 한글 지원. 실패 시 Helvetica fallback."""
    global _FONT_REGISTERED, _FONT_FALLBACK_USED
    if _FONT_REGISTERED:
        return "KoreanFont"

    candidates = [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
        "C:/Windows/Fonts/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("KoreanFont", path))
                _FONT_REGISTERED = True
                return "KoreanFont"
            except Exception:
                continue
    _FONT_FALLBACK_USED = True
    return "Helvetica"


def korean_font_available() -> bool:
    """한글 폰트 사용 가능 여부 (PDF 생성 호출 후 정확)."""
    _ensure_font()
    return not _FONT_FALLBACK_USED


# ─────────────────────────────────────────
# 저장 경로
# ─────────────────────────────────────────
# 드래프트 폴더 패턴(_drafts)은 list_recent_sessions에서 제외
def session_dir(school_code: str, session_id: str) -> Path:
    safe_code = str(school_code).replace("/", "_")
    path = STORAGE_DIR / safe_code / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_session_id() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


# ─────────────────────────────────────────
# Machine-readable: JSON 3종
# ─────────────────────────────────────────
def build_master_record(session: dict, prior_history: list | None = None) -> dict:
    """세션 상태 전체를 원본 JSON으로 직렬화.

    schema_version 1.1 (2026-05): submitter + status + status_history 필드 추가
    - submitter: 누가 이 점검을 수행/제출했는지 (실 담당자 vs 학교 담당자)
    - status: 현재 제출·검토 상태 (submitted/approved/returned/consolidated)
      실 담당자 제출 학교 담당자 검토 교육청 발송의 3단 흐름 추적용
    - status_history: 상태 변경 이력 누적 (감사·추적)

    Args:
        session: Streamlit 세션 상태
        prior_history: 기존 master.json 의 status_history (재저장 시 누적용).
                       None 이면 빈 리스트로 시작 (새 점검).
    """
    school = session.get("school") or {}
    active_space = session.get("active_space") or {}
    role = session.get("role") or "학교"
    space_manager = session.get("space_manager") or {}

    # submitter — 누가 이 점검을 시스템에 등록했나
    if role == "실" and space_manager:
        submitter = {
            "role": "실",
            "manager_id": space_manager.get("manager_id"),
            "name": space_manager.get("name"),
            "email": space_manager.get("email", ""),
            "phone": space_manager.get("phone", ""),
        }
        # 실 담당자 제출 학교 담당자 검토 대기
        status = "submitted"
    else:
        submitter = {
            "role": "학교",
            "manager_id": None,
            "name": session.get("approver_name", ""),
            "email": session.get("my_email", ""),
            "phone": "",
        }
        # 학교 담당자가 직접 점검·저장 자체 승인 상태 (스프린트 1 호환)
        status = "approved"

    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    new_history_entry = {
        "status": status,
        "by": submitter.get("manager_id") or submitter.get("name") or "(unknown)",
        "by_role": submitter.get("role"),
        "at": now_iso,
        "note": "재저장 (수정)" if prior_history else "초기 저장",
    }
    # 기존 이력에 같은 timestamp 항목 중복 방지 (1초 미만 연쇄 저장 시)
    base_history = list(prior_history or [])
    if base_history and base_history[-1].get("at") == now_iso \
            and base_history[-1].get("status") == status \
            and base_history[-1].get("by") == new_history_entry["by"]:
        accumulated_history = base_history # 중복 — 그대로 사용
    else:
        accumulated_history = base_history + [new_history_entry]

    return {
        "schema_version": "1.1",
        "record_type": "safeloop_inspection_master",
        "session_id": session.get("session_id"),
        "timestamp": datetime.datetime.now().isoformat(),
        "school": {
            "code": school.get("정보공시 학교코드"),
            "name": school.get("학교명"),
            "sido": school.get("시도교육청"),
            "region": school.get("지역"),
            "level": school.get("학교급"),
            "establishment": school.get("설립구분"),
        },
        "space": {
            "id": active_space.get("space_id"),
            "type": active_space.get("type"),
            "nickname": active_space.get("nickname"),
        },
        "submitter": submitter,
        "status": status,
        "status_history": accumulated_history,
        "ai_pipeline": {
            "stage1": session.get("stage1_result"),
            "stage2_raw": session.get("stage2_result"),
            "stage2_confirmed": session.get("stage2_confirmed"),
            "stage3": session.get("stage3_result"),
        },
        "inspection": {
            "item_scores": session.get("item_scores"),
            "score_result": session.get("score_result"),
        },
        "recommendations": session.get("recommendations"),
        "approval": {
            "eduline": session.get("eduline"),
            "internal_approval_confirmed": session.get("internal_approval_confirmed", False),
            "approver_name": session.get("approver_name", ""),
            "approval_date": str(session.get("approval_date", "")) if session.get("approval_date") else "",
        },
    }


def load_prior_history(school_code: str, session_id: str) -> list:
    """같은 session_id 의 기존 master.json 에서 status_history 추출.

    재저장 시 누적 보존을 위해 사용. 파일 없거나 깨지면 빈 리스트.
    """
    if not school_code or not session_id:
        return []
    try:
        master_path = session_dir(school_code, session_id) / "master.json"
        if not master_path.exists():
            return []
        data = json.loads(master_path.read_text(encoding="utf-8"))
        history = data.get("status_history")
        return list(history) if isinstance(history, list) else []
    except Exception:
        return []


def build_edu_package(master: dict) -> dict:
    """교육청 발송용 패키지 — 식별 유지·구조화 (이메일 첨부 .safeloop).

    record_type 은 `safeloop_edu_submission` (KEIIS 미연동 — SafeLoop 자체 포맷).
    """
    score = (master.get("inspection") or {}).get("score_result") or {}
    return {
        "schema_version": "1.1",
        "record_type": "safeloop_edu_submission",
        "submission_timestamp": datetime.datetime.now().isoformat(),
        "basis_law": "교육시설법 제10조 제3항 — 안전·유지관리기준 자체 점검",
        "school_identified": master.get("school"),
        "space": master.get("space"),
        "safety_score": score.get("score"),
        "grade": score.get("grade"),
        "category_scores": score.get("category_scores"),
        "detected_equipment": ((master.get("ai_pipeline") or {}).get("stage2_confirmed") or {}).get("detected_equipment"),
        "absent_equipment": ((master.get("ai_pipeline") or {}).get("stage2_confirmed") or {}).get("likely_absent_equipment"),
        "checklist_items": ((master.get("ai_pipeline") or {}).get("stage3") or {}).get("items"),
        "recommendations": master.get("recommendations"),
        "approval_trail": master.get("approval"),
    }


def build_opendata_package(master: dict) -> dict:
    """공공데이터 환원용 패키지 — 완전 익명화 + 집계 친화."""
    school = master.get("school") or {}
    score = (master.get("inspection") or {}).get("score_result") or {}
    s2_conf = ((master.get("ai_pipeline") or {}).get("stage2_confirmed") or {})
    stage3 = ((master.get("ai_pipeline") or {}).get("stage3") or {})

    return {
        "schema_version": "1.0",
        "record_type": "opendata_anonymous_inspection",
        "release_timestamp": datetime.datetime.now().isoformat(),
        "basis_law": "공공데이터법 — 업무 부산물 개방",
        "school_anonymous_id": anonymize_code(school.get("code") or ""),
        "sido": school.get("sido"),
        "school_level": school.get("level"),
        "establishment": school.get("establishment"),
        "space_type": (master.get("space") or {}).get("type"),
        "safety_score": score.get("score"),
        "grade": score.get("grade"),
        "category_scores": score.get("category_scores"),
        "detected_count": len((s2_conf.get("detected_equipment") or [])),
        "absent_count": len((s2_conf.get("likely_absent_equipment") or [])),
        "checklist_item_count": len((stage3.get("items") or [])),
    }


# ─────────────────────────────────────────
# Human-readable: CSV · Excel · PDF
# ─────────────────────────────────────────
def build_checklist_dataframe(master: dict) -> pd.DataFrame:
    items = (((master.get("ai_pipeline") or {}).get("stage3") or {}).get("items")) or []
    scores = ((master.get("inspection") or {}).get("item_scores")) or {}
    rows = []
    for itm in items:
        no = itm.get("no")
        title = itm.get("title", "")
        val = scores.get(str(no)) or scores.get(no) or scores.get(title) or ""
        label = {1.0: "양호", 0.5: "불량", 0.0: "부재"}.get(float(val), "미입력") if val != "" else "미입력"
        rows.append({
            "번호": no,
            "카테고리": itm.get("category"),
            "점검 제목": title,
            "점검 방법": itm.get("method"),
            "합격 기준": itm.get("criterion"),
            "법적 근거": itm.get("basis"),
            "항목 유형": itm.get("item_type"),
            "우선순위": itm.get("priority"),
            "점검 결과": label,
        })
    return pd.DataFrame(rows)


def build_csv(master: dict) -> bytes:
    df = build_checklist_dataframe(master)
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def build_excel(master: dict) -> bytes:
    df_checklist = build_checklist_dataframe(master)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # 시트 1: 요약
        school = master.get("school") or {}
        space = master.get("space") or {}
        score = (master.get("inspection") or {}).get("score_result") or {}
        summary = pd.DataFrame([
            ["학교명", school.get("name", "")],
            ["학교코드", school.get("code", "")],
            ["지역", school.get("region", "")],
            ["학교급", school.get("level", "")],
            ["공간 유형", space.get("type", "")],
            ["공간 별칭", space.get("nickname", "")],
            ["안전 점수", score.get("score", "")],
            ["등급", score.get("grade", "")],
            ["점검 일시", master.get("timestamp", "")],
            ["근거 법령", "교육시설법 제10조 3항 자체 점검"],
        ], columns=["항목", "값"])
        summary.to_excel(writer, sheet_name="요약", index=False)

        # 시트 2: 점검표
        df_checklist.to_excel(writer, sheet_name="점검표", index=False)

        # 시트 3: 카테고리별 점수
        cat_scores = (score.get("category_scores") or {})
        cat_df = pd.DataFrame([
            {"카테고리": k, "점수(%)": v.get("score"), "가중치 합계": v.get("weight_sum")}
            for k, v in cat_scores.items()
        ])
        if not cat_df.empty:
            cat_df.to_excel(writer, sheet_name="카테고리점수", index=False)

        # 시트 4: 추천
        recs = master.get("recommendations") or []
        if recs:
            rec_df = pd.DataFrame(recs)
            rec_df.to_excel(writer, sheet_name="안전설비추천", index=False)

    buf.seek(0)
    return buf.read()


def build_pdf_report(master: dict) -> bytes:
    """점검 결과 보고서(PDF) — 결재·첨부용 공식 문서 스타일."""
    font = _ensure_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    h_style = ParagraphStyle("H", parent=styles["Heading1"], fontName=font, fontSize=16,
                             alignment=1, spaceAfter=10)
    sub_style = ParagraphStyle("Sub", parent=styles["Heading2"], fontName=font, fontSize=12,
                               spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#0A0A0B"))
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontName=font, fontSize=10, leading=14)
    # 한글 폰트 fallback 안내용 — 빨간 강조 스타일
    warn_style = ParagraphStyle(
        "FontWarn", parent=body, fontName=font, fontSize=9,
        textColor=colors.HexColor("#D50000"), leading=12,
    )

    school = master.get("school") or {}
    space = master.get("space") or {}
    score = (master.get("inspection") or {}).get("score_result") or {}
    stage1 = (master.get("ai_pipeline") or {}).get("stage1") or {}

    flow = []
    # 한글 폰트 fallback 발생 시 — PDF 첫 페이지 상단에 빨간 경고 줄
    # (사용자가 PDF 출력 후에 한글 깨진 것을 발견하기 전 미리 인지)
    if _FONT_FALLBACK_USED:
        flow.append(Paragraph(
            "[FONT WARNING] Korean font not found on this system. "
            "Some Korean characters may render as blank boxes. "
            "Please install fonts-nanum or fonts-noto-cjk and regenerate.",
            warn_style,
        ))
        flow.append(Spacer(1, 3 * mm))
    flow.append(Paragraph("학교 안전 점검 결과 보고서", h_style))
    flow.append(Paragraph(
        f"세이프루프(SafeLoop) · 교육시설법 제10조 3항 자체 점검 · 생성일 {datetime.datetime.now():%Y-%m-%d}",
        body))
    flow.append(Spacer(1, 6 * mm))

    # 기본 정보
    flow.append(Paragraph("기본 정보", sub_style))
    basic = [
        ["학교명", school.get("name", "") or ""],
        ["학교코드", school.get("code", "") or ""],
        ["소재지", school.get("region", "") or ""],
        ["학교급/설립", f"{school.get('level','') or ''} / {school.get('establishment','') or ''}"],
        ["점검 공간", f"{space.get('type','') or ''} ({space.get('nickname') or '-'})"],
        ["AI 공간 식별", f"{stage1.get('space_type_primary','')} (신뢰도 {float(stage1.get('confidence',0))*100:.0f}%)"],
        ["점검 일시", str(master.get("timestamp", ""))],
    ]
    t = Table(basic, colWidths=[40 * mm, 120 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font, 10),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F7F7F8")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    flow.append(t)

    # 안전 점수
    flow.append(Paragraph("안전 점수", sub_style))
    sc_rows = [
        ["종합 점수", f"{score.get('score', 0)}점"],
        ["등급", f"{score.get('grade', '-')}"],
        ["등급 설명", score.get("grade_description", "")],
    ]
    for cat, info in (score.get("category_scores") or {}).items():
        sc_rows.append([f"[{cat}] 점수", f"{info.get('score', 0)}점"])
    t2 = Table(sc_rows, colWidths=[40 * mm, 120 * mm])
    t2.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font, 10),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F7F7F8")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
    ]))
    flow.append(t2)

    # 점검표
    flow.append(PageBreak())
    flow.append(Paragraph("AI 맞춤 점검표", sub_style))
    df = build_checklist_dataframe(master)
    if df.empty:
        flow.append(Paragraph("점검 항목이 없습니다.", body))
    else:
        header = ["No", "분류", "점검 제목", "법적 근거", "결과"]
        data = [header]
        for _, r in df.iterrows():
            data.append([
                str(r["번호"] or ""),
                str(r["카테고리"] or "")[:10],
                Paragraph(str(r["점검 제목"] or "")[:80], body),
                Paragraph(str(r["법적 근거"] or "-")[:60], body),
                str(r["점검 결과"] or ""),
            ])
        t3 = Table(data, colWidths=[12 * mm, 22 * mm, 72 * mm, 40 * mm, 18 * mm], repeatRows=1)
        t3.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), font, 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A0A0B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        flow.append(t3)

    # 추천
    recs = master.get("recommendations") or []
    if recs:
        flow.append(PageBreak())
        flow.append(Paragraph("안전 설비 추천 (부재·불량 기준)", sub_style))
        data = [["우선순위", "항목", "분류", "법적 근거", "조치"]]
        for r in recs:
            data.append([
                r.get("priority", ""),
                r.get("item", ""),
                r.get("category", ""),
                Paragraph(f"{r.get('law','')} {r.get('article','')}", body),
                r.get("action", ""),
            ])
        t4 = Table(data, colWidths=[18 * mm, 30 * mm, 24 * mm, 66 * mm, 26 * mm], repeatRows=1)
        t4.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), font, 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A0A0B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ]))
        flow.append(t4)

    # 결재란은 PDF 에 두지 않음 — 결재 양식은 학교마다 다르므로 학교 자체 양식에 맡김.
    # 본 PDF 는 데이터(점수·점검표·추천)만 담고, 학교가 별도 결재 문서에 첨부.
    flow.append(Spacer(1, 10 * mm))
    flow.append(Paragraph(
        "※ 본 보고서는 데이터 부분만 담고 있습니다. 결재는 학교 자체 양식으로 별도 진행하세요.",
        ParagraphStyle("Note", parent=styles["BodyText"], fontName=font,
                        fontSize=9, textColor=colors.grey, alignment=1),
    ))

    doc.build(flow)
    buf.seek(0)
    return buf.read()


def build_official_letter_pdf(master: dict) -> bytes:
    """결재 첨부용 공문 (품의서 양식) — 학교 자체 결재 양식에 첨부 가능."""
    font = _ensure_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=25 * mm, rightMargin=25 * mm,
                            topMargin=22 * mm, bottomMargin=22 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("T", parent=styles["Heading1"], fontName=font, fontSize=18,
                           alignment=1, spaceAfter=14)
    body = ParagraphStyle("B", parent=styles["BodyText"], fontName=font, fontSize=11,
                          leading=17, spaceBefore=6, spaceAfter=6)
    small = ParagraphStyle("S", parent=styles["BodyText"], fontName=font, fontSize=9,
                           leading=13, textColor=colors.grey)

    school = master.get("school") or {}
    space = master.get("space") or {}
    score = (master.get("inspection") or {}).get("score_result") or {}

    flow = []
    flow.append(Paragraph("학교 안전 점검 결과 보고(공문)", title))

    flow.append(Paragraph(f"수신: {school.get('sido','') or '관할 교육청'} (시설안전 담당)", body))
    flow.append(Paragraph(f"참조: 교육시설안전과", body))
    flow.append(Paragraph(f"제목: {school.get('name','')} {space.get('type','')} 안전·유지관리기준 자체 점검 결과 제출", body))
    flow.append(Spacer(1, 6 * mm))

    flow.append(Paragraph(
        "1. 관련: 「교육시설 등의 안전 및 유지관리 등에 관한 법률」 제10조 제3항 "
        "(안전·유지관리기준 준수 여부 자체 점검 의무)",
        body,
    ))
    flow.append(Paragraph(
        f"2. 우리 학교는 위 법령에 따라 {space.get('type','')} 공간에 대해 AI 비전 기반 "
        f"맞춤형 점검을 실시하였으며, 그 결과를 붙임과 같이 제출합니다.",
        body,
    ))
    flow.append(Paragraph(
        f"3. 점검 결과 종합 점수는 <b>{score.get('score','-')}점(등급 {score.get('grade','-')})</b>이며, "
        "세부 내역 및 안전 설비 추천 사항은 첨부 문서를 참조하시기 바랍니다.",
        body,
    ))
    flow.append(Paragraph(
        "4. 본 결과는 익명화 후 공공데이터 환원 대상임을 알려드립니다.",
        body,
    ))
    flow.append(Spacer(1, 10 * mm))

    flow.append(Paragraph("<b>붙임</b>", body))
    flow.append(Paragraph("1. 점검 결과 보고서 (PDF) 1부", body))
    flow.append(Paragraph("2. 점검 데이터 (XLSX) 1부", body))
    flow.append(Paragraph("3. AI 가 읽는 데이터 (JSON) 1부", body))
    flow.append(Paragraph("4. 교육청 발송 패키지 (JSON) 1부", body))
    flow.append(Paragraph("5. 공공데이터 환원 패키지 (JSON, 익명화 적용) 1부. 끝.", body))
    flow.append(Spacer(1, 14 * mm))

    # 발신 학교 + 결재선
    flow.append(Paragraph(f"{school.get('name','')}장", body))
    flow.append(Spacer(1, 4 * mm))
    flow.append(Paragraph(
        "※ 본 문서는 SafeLoop AI 점검 시스템이 생성한 초안이며, "
        "공식 결재는 K-에듀파인 등 외부 결재 시스템에서 진행합니다. "
        "본 PDF 는 학교 자체 결재 양식 첨부 또는 교육청 발송 시 참고용으로 사용하세요.",
        small,
    ))
    doc.build(flow)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────
# 메인 저장 함수
# ─────────────────────────────────────────
def save_inspection(session: dict) -> dict:
    """세션 데이터를 학교 클라우드(모의)에 저장하고 생성된 파일 경로를 반환.

    같은 session_id 로 재저장 시 status_history 가 누적됨 (감사 이력 보존).
    """
    session_id = session.get("session_id") or new_session_id()
    session["session_id"] = session_id
    school = session.get("school") or {}
    school_code = school.get("정보공시 학교코드") or "UNKNOWN"
    out_dir = session_dir(school_code, session_id)

    # 재저장 시 기존 master.json 의 status_history 누적 (감사 이력 보존)
    prior_history = load_prior_history(school_code, session_id)
    master = build_master_record(session, prior_history=prior_history)
    edu_pkg = build_edu_package(master)
    open_pkg = build_opendata_package(master)

    # Machine-readable
    (out_dir / "master.json").write_text(
        json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "edu_package.json").write_text(
        json.dumps(edu_pkg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "opendata_package.json").write_text(
        json.dumps(open_pkg, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Human-readable
    (out_dir / "점검결과.csv").write_bytes(build_csv(master))
    (out_dir / "점검결과.xlsx").write_bytes(build_excel(master))
    (out_dir / "점검결과보고서.pdf").write_bytes(build_pdf_report(master))
    # 결재첨부_공문.pdf — 결재자 이름이 입력된 경우에만 자동 생성.
    # 결재는 에듀파인 등 외부 시스템에서 진행되므로 SafeLoop 은 강제하지 않음.
    # 학교가 SafeLoop 에도 기록을 남기고자 결재자 이름을 입력한 경우만 첨부 공문 PDF 생성.
    _approval = (master.get("approval") or {})
    if (_approval.get("approver_name") or "").strip():
        (out_dir / "결재첨부_공문.pdf").write_bytes(build_official_letter_pdf(master))

    return {
        "session_id": session_id,
        "directory": str(out_dir),
        "files": sorted(p.name for p in out_dir.iterdir()),
    }


def save_uploaded_edu_inbox(file_bytes: bytes, file_name: str) -> dict:
    """교육청 담당자가 이메일로 받은 .safeloop 또는 .json 첨부를 수신함에 저장.

    파일이 암호화되어 있으면 자동 복호화. 평문 JSON 도 호환.
    저장은 평문 JSON 으로 (수신함 페이지에서 빠르게 표시 가능).
    """
    from modules.crypto import decrypt_payload
    try:
        data = decrypt_payload(file_bytes)
    except Exception as e:
        return {"ok": False, "reason": f"파일 읽기 실패: {e}"}

    school = data.get("school_identified") or data.get("school") or {}
    sido = school.get("sido") or "미상"
    school_code = school.get("code") or school.get("정보공시 학교코드") or "UNKNOWN"

    target_dir = EDU_RECEIPT_DIR / sido
    target_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    # 확장자를 .json 으로 통일 — 수신함은 복호화된 평문 보관 (빠른 검색·필터)
    base = file_name.replace("/", "_").replace("\\", "_")
    if base.endswith(".safeloop"):
        base = base[:-len(".safeloop")] + ".json"
    elif not base.endswith(".json"):
        base = base + ".json"
    out_name = f"{ts}_{school_code}_{base}"
    out_path = target_dir / out_name
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"ok": True, "path": str(out_path), "sido": sido,
            "school_code": school_code,
            "school_name": school.get("name", "")}


def list_edu_inbox(sido: str | None = None) -> list[dict]:
    """교육청 수신함 리스트."""
    items = []
    roots = [EDU_RECEIPT_DIR / sido] if sido else list(EDU_RECEIPT_DIR.iterdir())
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for p in sorted(root.glob("*.json"), reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            items.append({
                "file": p.name,
                "sido": root.name,
                "path": str(p),
                "school": (data.get("school_identified") or {}).get("name"),
                "school_code": (data.get("school_identified") or {}).get("code"),
                "space_type": (data.get("space") or {}).get("type"),
                "space_nickname": (data.get("space") or {}).get("nickname"),
                "score": data.get("safety_score"),
                "grade": data.get("grade"),
                "received_at": data.get("submission_timestamp"),
            })
    return items


def delete_edu_inbox_item(sido: str, file_name: str) -> bool:
    """교육청 수신함 개별 파일 삭제. 성공 시 True."""
    try:
        target = EDU_RECEIPT_DIR / sido / file_name
        if target.exists() and target.is_file():
            target.unlink()
            return True
    except Exception:
        pass
    return False


def bulk_delete_edu_inbox(items: list[dict]) -> int:
    """수신함 항목 일괄 삭제. 반환: 실제 삭제된 개수."""
    n = 0
    for item in items:
        if delete_edu_inbox_item(item.get("sido", ""), item.get("file", "")):
            n += 1
    return n


# ─────────────────────────────────────────
# 학교 교육청 다이렉트 전송 + 수신 확인
# (같은 SafeLoop 인스턴스 / 공유 데이터 폴더 환경에서만 동작.
# 분산 환경은 정식 출시 시 별도 백엔드 검토.)
# ─────────────────────────────────────────
def submit_to_edu_inbox_direct(edu_pkg: dict) -> dict:
    """학교 담당자가 SafeLoop 안에서 교육청 수신함으로 직접 발송.

    - 평문 JSON 으로 mock_edu_receipt/{sido}/ 에 저장
      (수신함 인덱싱·검색 효율 위해 평문 보관 — 디스크 권한으로 보호)
    - 학교 측 발송함(_outbox) 에도 발송 기록을 남겨 "전송 완료 / 수신 대기" 추적
    """
    school = edu_pkg.get("school_identified") or {}
    sido = school.get("sido") or "미상"
    school_code = school.get("code") or "UNKNOWN"
    target_dir = EDU_RECEIPT_DIR / sido
    target_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    file_name = f"{school_code}_{ts}.json"
    target = target_dir / file_name
    target.write_text(json.dumps(edu_pkg, ensure_ascii=False, indent=2),
                      encoding="utf-8")

    # 학교 측 발송함 기록
    outbox_dir = STORAGE_DIR / str(school_code) / "_outbox"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    submit_id = uuid.uuid4().hex[:10]
    record = {
        "submit_id": submit_id,
        "sido": sido,
        "school_code": school_code,
        "school_name": school.get("name", ""),
        "space_type": (edu_pkg.get("space") or {}).get("type"),
        "file_name": file_name,
        "submitted_at": datetime.datetime.now().isoformat(),
        "score": edu_pkg.get("safety_score"),
        "grade": edu_pkg.get("grade"),
        "channel": "safeloop_direct",
    }
    (outbox_dir / f"{submit_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"ok": True, "submit_id": submit_id, "file_name": file_name,
            "sido": sido}


def _read_marker_path(sido: str, file_name: str) -> Path:
    """교육청 열람 확인 마커 경로."""
    p = EDU_RECEIPT_DIR / sido / "_read"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{file_name}.read.json"


def mark_edu_inbox_read(sido: str, file_name: str) -> bool:
    """교육청 담당자가 해당 건을 열람할 때 호출 — 1회만 기록.

    이미 마커가 있으면 그대로 두어 첫 열람 시각을 보존.
    """
    if not sido or not file_name:
        return False
    marker = _read_marker_path(sido, file_name)
    if marker.exists():
        return True
    try:
        marker.write_text(
            json.dumps({
                "sido": sido,
                "file_name": file_name,
                "read_at": datetime.datetime.now().isoformat(),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def is_edu_inbox_read(sido: str, file_name: str) -> str | None:
    """해당 건의 첫 열람 시각 (ISO). 없으면 None."""
    if not sido or not file_name:
        return None
    marker = _read_marker_path(sido, file_name)
    if not marker.exists():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        return data.get("read_at")
    except Exception:
        return None


def _starred_marker_path(sido: str, file_name: str) -> Path:
    p = EDU_RECEIPT_DIR / sido / "_starred"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{file_name}.star"


def is_edu_inbox_starred(sido: str, file_name: str) -> bool:
    if not sido or not file_name:
        return False
    return _starred_marker_path(sido, file_name).exists()


def toggle_edu_inbox_star(sido: str, file_name: str) -> bool:
    """별표 토글. 반환: 토글 후 별표 상태(True=별표 있음)."""
    p = _starred_marker_path(sido, file_name)
    if p.exists():
        try:
            p.unlink()
            return False
        except Exception:
            return True
    try:
        p.write_text(datetime.datetime.now().isoformat(), encoding="utf-8")
        return True
    except Exception:
        return False


def bulk_mark_edu_inbox_read(items: list[dict]) -> int:
    """수신함 항목들을 일괄 읽음 처리. 반환: 새로 읽음 처리된 개수."""
    n = 0
    for item in items:
        sido = item.get("sido", "")
        fname = item.get("file", "")
        if not sido or not fname:
            continue
        if is_edu_inbox_read(sido, fname) is None:
            if mark_edu_inbox_read(sido, fname):
                n += 1
    return n


def bulk_toggle_edu_inbox_star(items: list[dict], target: bool) -> int:
    """일괄 별표 설정 또는 해제. target=True 면 별표 부착, False 면 해제.
    반환: 상태가 바뀐 항목 수."""
    n = 0
    for item in items:
        sido = item.get("sido", "")
        fname = item.get("file", "")
        if not sido or not fname:
            continue
        cur = is_edu_inbox_starred(sido, fname)
        if cur != target:
            toggle_edu_inbox_star(sido, fname)
            n += 1
    return n


def get_school_outbox(school_code: str) -> list[dict]:
    """학교 발송함 — 다이렉트 전송 기록 + 수신 확인 상태 결합.

    각 항목에 `read_at` 키 추가 (None 이면 미열람).
    최신 발송순 정렬.
    """
    if not school_code:
        return []
    outbox_dir = STORAGE_DIR / str(school_code) / "_outbox"
    if not outbox_dir.exists():
        return []
    items: list[dict] = []
    for p in sorted(outbox_dir.glob("*.json"), reverse=True):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        rec["read_at"] = is_edu_inbox_read(
            rec.get("sido", ""), rec.get("file_name", "")
        )
        items.append(rec)
    items.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
    return items


# ─────────────────────────────────────────
# 드래프트(촬영 진행 중) — 새로고침 복구용
# ─────────────────────────────────────────
def _draft_dir(school_code: str, space_id: str = "") -> Path:
    """드래프트 폴더 경로. space_id 가 있으면 공간별, 없으면 학교 공통 (이전 호환)."""
    base = STORAGE_DIR / str(school_code or "_unknown") / "_drafts"
    if space_id:
        p = base / str(space_id)
    else:
        p = base
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_draft_shots(school_code: str, shots: dict, space_id: str = "") -> None:
    """촬영 중인 사진들을 디스크에 백업 (새로고침 대비). 공간별 분리."""
    if not school_code:
        return
    d = _draft_dir(school_code, space_id)
    # 기존 파일 정리
    for f in d.glob("*.jpg"):
        try:
            f.unlink()
        except Exception:
            pass

    metadata: dict = {}
    for shot_key, photos in (shots or {}).items():
        if not photos:
            continue
        for idx, p in enumerate(photos):
            fname = f"{shot_key}__{idx:02d}.jpg"
            try:
                (d / fname).write_bytes(p.get("bytes", b""))
                metadata[fname] = {
                    "shot_key": shot_key,
                    "idx": idx,
                    "source": p.get("source", "camera"),
                    "name": p.get("name", fname),
                }
            except Exception:
                continue
    (d / "_meta.json").write_text(
        json.dumps({
            "updated_at": datetime.datetime.now().isoformat(),
            "files": metadata,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_draft_shots(school_code: str, space_id: str = "") -> dict:
    """저장된 드래프트를 shots 형식으로 복원. 공간별 분리."""
    if not school_code:
        return {}
    d = _draft_dir(school_code, space_id)
    meta_path = d / "_meta.json"
    if not meta_path.exists():
        return {}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    shots: dict = {}
    for fname, info in (meta.get("files") or {}).items():
        path = d / fname
        if not path.exists():
            continue
        shots.setdefault(info["shot_key"], []).append({
            "name": info.get("name", fname),
            "bytes": path.read_bytes(),
            "source": info.get("source", "camera"),
            "_idx": info.get("idx", 0),
        })
    for k in shots:
        shots[k].sort(key=lambda p: p.get("_idx", 0))
        for p in shots[k]:
            p.pop("_idx", None)
    return shots


def has_draft(school_code: str, space_id: str = "") -> bool:
    if not school_code:
        return False
    return (_draft_dir(school_code, space_id) / "_meta.json").exists()


def draft_summary(school_code: str, space_id: str = "") -> dict | None:
    if not has_draft(school_code, space_id):
        return None
    meta_path = _draft_dir(school_code, space_id) / "_meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    files = meta.get("files") or {}
    return {
        "updated_at": meta.get("updated_at"),
        "photo_count": len(files),
        "shot_keys": sorted({v.get("shot_key", "") for v in files.values()}),
    }


def clear_draft(school_code: str, space_id: str = "") -> None:
    if not school_code:
        return
    import shutil
    d = _draft_dir(school_code, space_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


# ─────────────────────────────────────────
# 학교별 영구 프로필 (결재라인·기본 설정)
# ─────────────────────────────────────────
def _profile_path(school_code: str) -> Path:
    p = STORAGE_DIR / str(school_code or "_unknown")
    p.mkdir(parents=True, exist_ok=True)
    return p / "_profile.json"


def save_school_profile(school_code: str, profile: dict) -> None:
    """학교별 영구 프로필 저장 (결재라인 등). 매 점검마다 재입력 안 하도록."""
    if not school_code:
        return
    try:
        existing = load_school_profile(school_code) or {}
    except Exception:
        existing = {}
    existing.update(profile)
    existing["updated_at"] = datetime.datetime.now().isoformat()
    _profile_path(school_code).write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_school_profile(school_code: str) -> dict:
    if not school_code:
        return {}
    p = _profile_path(school_code)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ─────────────────────────────────────────
# 학교별 결재 정책 — 단일 결재(에듀파인만) vs 이중 결재(에듀파인 + SafeLoop)
#
# 단일 결재 (기본, dual_approval_enabled=False):
# 에듀파인에서 결재 완료된 파일을 그대로 첨부해 발송. SafeLoop 안에서 추가
# 결재 입력 화면 자체가 나타나지 않음. 단순·빠른 흐름.
#
# 이중 결재 (학교 선택, dual_approval_enabled=True):
# 에듀파인 결재 + SafeLoop 안에서도 결재자 정보 기록. 학교가 자체 감사·
# 추적 이력을 추가로 남기고 싶을 때.
#
# 학교 담당자가 [설정] 페이지에서 한 번 정하면 그 학교는 일관되게 적용됨.
# ─────────────────────────────────────────
def get_school_dual_approval(school_code: str) -> bool:
    """학교의 이중 결재 정책 조회. 기본 False (단일 결재 — 에듀파인만)."""
    if not school_code:
        return False
    profile = load_school_profile(school_code)
    return bool(profile.get("dual_approval_enabled", False))


def set_school_dual_approval(school_code: str, enabled: bool) -> None:
    """학교의 이중 결재 정책 저장."""
    if not school_code:
        return
    save_school_profile(school_code, {"dual_approval_enabled": bool(enabled)})


# ─────────────────────────────────────────
# 디스크 사용량 + 캐시 정리
# ─────────────────────────────────────────
def _dir_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except Exception:
                pass
    return total


def storage_usage() -> dict:
    """학교 클라우드·캐시·교육청 수신함 디스크 사용량 (바이트)."""
    cache = STORAGE_DIR / "_ai_cache"
    return {
        "school_storage": _dir_size(STORAGE_DIR) - _dir_size(cache),
        "ai_cache": _dir_size(cache),
        "edu_receipt": _dir_size(EDU_RECEIPT_DIR),
        "total": _dir_size(STORAGE_DIR) + _dir_size(EDU_RECEIPT_DIR),
    }


def cleanup_old_cache(days: int = 30) -> tuple[int, int]:
    """`_ai_cache/` 안의 N일 이상 된 파일 삭제. (삭제 수, 회수 바이트)"""
    cache = STORAGE_DIR / "_ai_cache"
    if not cache.exists():
        return 0, 0
    cutoff = datetime.datetime.now().timestamp() - days * 86400
    removed = 0
    bytes_freed = 0
    for p in cache.rglob("*"):
        if p.is_file():
            try:
                if p.stat().st_mtime < cutoff:
                    bytes_freed += p.stat().st_size
                    p.unlink()
                    removed += 1
            except Exception:
                continue
    return removed, bytes_freed


def cleanup_school_storage(days: int = 90) -> tuple[int, int]:
    """8-6 수정: 학교 클라우드(`school_storage/{학교코드}/{세션ID}/`) 에서
    N일 이상 된 세션 폴더를 통째로 삭제.

    반환: (삭제된 세션 수, 회수된 바이트)

    **주의**: 이 함수는 실제 점검 이력을 삭제하므로 호출 측에서 반드시
    사용자 확인(confirm) 을 거쳐야 한다. `_ai_cache`, `_drafts` 등
    밑줄로 시작하는 시스템 디렉터리는 보호한다.
    """
    if not STORAGE_DIR.exists():
        return 0, 0
    cutoff = datetime.datetime.now().timestamp() - days * 86400
    removed_sessions = 0
    bytes_freed = 0
    for school_dir in STORAGE_DIR.iterdir():
        # `_ai_cache`, `_drafts` 등 시스템 디렉터리 보호
        if school_dir.name.startswith("_") or not school_dir.is_dir():
            continue
        for sess in list(school_dir.iterdir()):
            if not sess.is_dir() or sess.name.startswith("_"):
                continue
            try:
                mtime = sess.stat().st_mtime
                if mtime >= cutoff:
                    continue
                # 세션 폴더 크기 계산
                sess_size = _dir_size(sess)
                # 삭제
                import shutil
                shutil.rmtree(sess)
                bytes_freed += sess_size
                removed_sessions += 1
            except Exception:
                continue
    return removed_sessions, bytes_freed


def list_recent_sessions(limit: int = 20) -> list[dict]:
    items: list[dict] = []
    for school_dir in STORAGE_DIR.iterdir():
        if school_dir.name.startswith("_") or not school_dir.is_dir():
            continue
        for sess in school_dir.iterdir():
            if not sess.is_dir():
                continue
            if sess.name.startswith("_"): # _drafts 등 시스템 폴더 제외
                continue
            master_path = sess / "master.json"
            if not master_path.exists():
                continue
            try:
                data = json.loads(master_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            items.append({
                "session_id": sess.name,
                "school_code": school_dir.name,
                "school_name": (data.get("school") or {}).get("name"),
                "space_type": (data.get("space") or {}).get("type"),
                "space_nickname": (data.get("space") or {}).get("nickname"),
                "score": ((data.get("inspection") or {}).get("score_result") or {}).get("score"),
                "grade": ((data.get("inspection") or {}).get("score_result") or {}).get("grade"),
                "timestamp": data.get("timestamp"),
                "path": str(sess),
            })
    items.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return items[:limit]


# ─────────────────────────────────────────
# 수합·검토 (학교 담당자 전용) — Sprint 3
# ─────────────────────────────────────────
def list_school_submissions(
    school_code: str,
    status_filter: str | None = None,
) -> list[dict]:
    """한 학교의 모든 점검 세션 목록. 검토용 정보(status, submitter) 포함.

    Args:
        school_code: 학교 코드
        status_filter: 특정 상태만 (submitted/approved/returned/consolidated).
                       None 이면 전체.

    Returns: timestamp 역순 정렬 리스트. 옛 데이터(status 필드 없음)는
             "approved" 로 기본 처리 (스프린트 1 이전 호환).
    """
    items: list[dict] = []
    if not school_code:
        return items
    school_dir = STORAGE_DIR / school_code
    if not school_dir.exists() or not school_dir.is_dir():
        return items

    for sess in school_dir.iterdir():
        if not sess.is_dir() or sess.name.startswith("_"):
            continue
        master_path = sess / "master.json"
        if not master_path.exists():
            continue
        try:
            data = json.loads(master_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        status = data.get("status") or "approved" # 옛 호환
        if status_filter and status != status_filter:
            continue

        submitter = data.get("submitter") or {}
        items.append({
            "session_id": sess.name,
            "school_code": school_code,
            "school_name": (data.get("school") or {}).get("name"),
            "space_id": (data.get("space") or {}).get("id"),
            "space_type": (data.get("space") or {}).get("type"),
            "space_nickname": (data.get("space") or {}).get("nickname"),
            "score": ((data.get("inspection") or {}).get("score_result") or {}).get("score"),
            "grade": ((data.get("inspection") or {}).get("score_result") or {}).get("grade"),
            "timestamp": data.get("timestamp"),
            "status": status,
            "submitter_name": submitter.get("name") or "(미상)",
            "submitter_role": submitter.get("role", ""),
            "submitter_manager_id": submitter.get("manager_id"),
            "history_count": len(data.get("status_history") or []),
            "path": str(sess),
        })
    items.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return items


def load_master_record(school_code: str, session_id: str) -> dict | None:
    """특정 점검 세션의 master.json 로드. 파일 없거나 깨지면 None."""
    if not school_code or not session_id:
        return None
    master_path = session_dir(school_code, session_id) / "master.json"
    if not master_path.exists():
        return None
    try:
        return json.loads(master_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def update_submission_status(
    school_code: str,
    session_id: str,
    new_status: str,
    by: str,
    by_role: str = "학교",
    note: str = "",
) -> bool:
    """제출본 상태 변경 + status_history 항목 추가.

    Args:
        school_code: 학교 코드
        session_id: 점검 세션 ID
        new_status: 새 상태 ("approved"/"returned"/"submitted"/"consolidated")
        by: 처리자 식별자 (이름 또는 매니저 ID)
        by_role: 처리자 역할 (기본 "학교")
        note: 변경 사유 (반려 사유 등). 빈 문자열 허용.

    Returns: 성공 시 True. 파일 없거나 쓰기 실패 시 False.
    """
    if not school_code or not session_id or not new_status:
        return False
    data = load_master_record(school_code, session_id)
    if not data:
        return False

    history = list(data.get("status_history") or [])
    history.append({
        "status": new_status,
        "by": by or "(unknown)",
        "by_role": by_role,
        "at": datetime.datetime.now().isoformat(timespec="seconds"),
        "note": note or "",
    })
    data["status_history"] = history
    data["status"] = new_status

    try:
        master_path = session_dir(school_code, session_id) / "master.json"
        master_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def update_submission_scores(
    school_code: str,
    session_id: str,
    new_item_scores: dict,
    new_score_result: dict,
    by: str,
    note: str = "학교 담당자 직접 수정",
) -> bool:
    """학교 담당자가 제출본 점수를 직접 수정.

    item_scores + score_result 갱신 + status_history 에 수정 기록 추가.
    상태는 변경하지 않음 (호출 측에서 별도 update_submission_status 권장).
    """
    if not school_code or not session_id:
        return False
    data = load_master_record(school_code, session_id)
    if not data:
        return False
    data.setdefault("inspection", {})
    data["inspection"]["item_scores"] = new_item_scores
    data["inspection"]["score_result"] = new_score_result

    history = list(data.get("status_history") or [])
    history.append({
        "status": data.get("status"),
        "by": by or "(unknown)",
        "by_role": "학교",
        "at": datetime.datetime.now().isoformat(timespec="seconds"),
        "note": note or "학교 담당자 직접 수정",
    })
    data["status_history"] = history

    try:
        master_path = session_dir(school_code, session_id) / "master.json"
        master_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False
