"""
공공데이터 환원 export · 이력 · 롤백 — 교육청 담당자 전용 기능.

흐름:
1. 교육청 수신함의 학교 점검 데이터를 익명화·집계해 CSV 한 파일로 export
2. 환원 파일은 사용자 지정 공유 폴더에 timestamp 파일명으로 저장
3. 대시보드(safeloop-dashboard)가 같은 폴더를 자동 읽어 합산
4. 잘못 환원한 경우 롤백 가능 — `_rolled_back/` 하위로 이동 (삭제 X, 감사 추적성)

설계 원칙:
- storage.py 의 기존 함수(list_edu_inbox, EDU_RECEIPT_DIR)만 사용. storage.py 수정 X
- 익명화는 data_loader.anonymize_code 재사용
- 한 번의 환원 = 한 개의 CSV (롤백 단위)
- 활성 환원: 공유 폴더의 `opendata_*.csv`
- 롤백된 환원: 공유 폴더의 `_rolled_back/opendata_*.csv`
"""
from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path

import pandas as pd

from modules.data_loader import anonymize_code
from modules.storage import EDU_RECEIPT_DIR, list_edu_inbox


# 한국 표준시
KST = datetime.timezone(datetime.timedelta(hours=9))


def _now_kst() -> datetime.datetime:
    return datetime.datetime.now(KST)


def _stamp_for_filename() -> str:
    """파일명용 timestamp (예: 20260517_193045)."""
    return _now_kst().strftime("%Y%m%d_%H%M%S")


# ─────────────────────────────────────────
# 수신함 데이터 → 환원 가능 항목 목록
# ─────────────────────────────────────────
def _read_inbox_payload(file_path: Path) -> dict | None:
    """수신함 파일(.safeloop / .json)에서 master record 추출.

    .safeloop 는 AES 암호화 — 평문 .json 만 우선 지원.
    .safeloop 는 storage.py 의 save_uploaded_edu_inbox 가 풀어 저장한
    옆의 .json 을 사용 (시연 환경에서는 평문 .json 도 함께 있음).
    """
    if not file_path.exists():
        return None
    try:
        if file_path.suffix == ".json":
            return json.loads(file_path.read_text(encoding="utf-8"))
        # .safeloop 는 시연 환경에서 평문 .json 짝을 우선 사용
        sibling_json = file_path.with_suffix(".json")
        if sibling_json.exists():
            return json.loads(sibling_json.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def list_inbox_for_export() -> list[dict]:
    """환원 가능한 수신함 항목 목록 — 교육청 수신함의 모든 학교 점검.

    storage.list_edu_inbox 가 이미 (school, school_code, sido, score, grade,
    space_type, record_type, path) 등을 제공하므로 그것을 1차로 사용하고,
    학교급·설립구분 같은 추가 메타는 master json 에서 보충.

    Returns: 각 항목 = {
        sido, file, path, school_anonymous_id, school_name_display,
        school_level, establishment, space_type, safety_score, grade,
        received_at, record_type
    }
    """
    items: list[dict] = []
    rows = list_edu_inbox()  # storage.py 의 기본 목록 (이미 .json 만)
    for row in rows:
        path_str = row.get("path") or ""
        if not path_str:
            continue
        payload = _read_inbox_payload(Path(path_str))
        # master 양식 두 가지: "school" 또는 "school_identified"
        master = payload or {}
        school_meta = master.get("school_identified") or master.get("school") or {}
        school_level = school_meta.get("level") or school_meta.get("학교급") or ""
        establishment = school_meta.get("establishment") or school_meta.get("설립구분") or ""

        school_code = row.get("school_code") or school_meta.get("code") \
            or school_meta.get("정보공시 학교코드") or ""

        items.append({
            "sido": row.get("sido") or row.get("school_sido") or "",
            "file": row.get("file") or "",
            "path": path_str,
            "school_anonymous_id": anonymize_code(school_code),
            "school_name_display": (row.get("school") or "")[:1] + "○○" if row.get("school") else "",
            "school_level": school_level,
            "establishment": establishment,
            "space_type": row.get("space_type") or "",
            "safety_score": row.get("score"),
            "grade": row.get("grade") or "",
            "received_at": row.get("received_at") or "",
            "record_type": row.get("record_type") or "",
        })
    # 받은 시각 역순
    items.sort(key=lambda x: x.get("received_at") or "", reverse=True)
    return items


# ─────────────────────────────────────────
# 환원 실행
# ─────────────────────────────────────────
def export_opendata_csv(
    selected_items: list[dict],
    output_dir: Path | str,
) -> dict:
    """선택된 수신함 항목을 익명화·집계해 한 개의 CSV 로 export.

    Args:
        selected_items: list_inbox_for_export() 결과 중 사용자가 고른 항목 dict 들
        output_dir: 공유 폴더 (대시보드도 같은 폴더를 읽음)

    Returns: {
        "ok": True,
        "file_path": str,
        "file_name": str,
        "count": int,
        "sido_distribution": {시도: 개수, ...},
        "exported_at": iso str,
    }
    """
    # output_dir 검증 — 사용자 입력이므로 안전성 확인
    try:
        output_dir = Path(output_dir).expanduser().resolve(strict=False)
    except Exception as e:
        return {"ok": False, "error": f"잘못된 output_dir: {e}"}
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"ok": False, "error": f"output_dir 생성 실패: {e}"}
    # 파일명은 시스템이 생성한 stamp 만 사용 — 외부 입력 직접 사용 안 함
    stamp = _stamp_for_filename()
    file_name = f"opendata_{stamp}.csv"
    file_path = output_dir / file_name
    # 최종 경로가 output_dir 내부인지 재확인 (스탬프는 안전하지만 방어적)
    try:
        if output_dir not in file_path.resolve(strict=False).parents:
            return {"ok": False, "error": "잘못된 파일 경로 (경로 이탈 차단)"}
    except Exception:
        pass

    rows: list[dict] = []
    sido_dist: dict[str, int] = {}
    for it in selected_items:
        master = _read_inbox_payload(Path(it.get("path") or ""))
        sido = it.get("sido") or ""
        sido_dist[sido] = sido_dist.get(sido, 0) + 1
        # master 가 None 이라도 list 항목 자체에 있는 정보로 환원 가능
        school = (master or {}).get("school_identified") or (master or {}).get("school") or {}
        s2 = (((master or {}).get("ai_pipeline") or {}).get("stage2_confirmed") or {})
        rows.append({
            "school_anonymous_id": it.get("school_anonymous_id") or "",
            "sido": sido,
            "school_level": it.get("school_level") or "",
            "establishment": it.get("establishment") or "",
            "space_type": it.get("space_type") or "",
            "safety_score": it.get("safety_score"),
            "grade": it.get("grade") or "",
            "detected_count": len(s2.get("detected_equipment") or []),
            "absent_count": len(s2.get("likely_absent_equipment") or []),
            "record_type": it.get("record_type") or "",
            "released_at": _now_kst().isoformat(),
        })

    if not rows:
        return {
            "ok": False, "file_path": "", "file_name": "",
            "count": 0, "sido_distribution": {},
            "error": "환원 가능한 항목이 없습니다(읽기 실패 또는 빈 선택).",
        }

    # CSV 저장 (UTF-8 BOM — Excel 호환)
    df = pd.DataFrame(rows)
    df.to_csv(file_path, index=False, encoding="utf-8-sig")

    # 메타 사이드카 — 이력 표시용 (file_name 옆 .meta.json)
    meta = {
        "file_name": file_name,
        "exported_at": _now_kst().isoformat(),
        "count": len(rows),
        "sido_distribution": sido_dist,
        "selected_file_names": [it.get("file") for it in selected_items],
    }
    (output_dir / f"{file_name}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 감사 로그 — 환원은 민감 행위 (외부 공개 데이터 생성)
    try:
        from modules.audit import log as _audit
        _audit("opendata.export",
               actor_role="교육청",
               target=file_name,
               meta={"count": len(rows),
                     "sido_distribution": sido_dist})
    except Exception:
        pass

    return {
        "ok": True,
        "file_path": str(file_path),
        "file_name": file_name,
        "count": len(rows),
        "sido_distribution": sido_dist,
        "exported_at": meta["exported_at"],
    }


# ─────────────────────────────────────────
# 환원 이력
# ─────────────────────────────────────────
def list_export_history(output_dir: Path | str) -> list[dict]:
    """공유 폴더의 환원 이력 — 활성 + 롤백된 항목 모두.

    Returns: 각 항목 = {
        file_name, file_path, status (active|rolled_back),
        exported_at, count, sido_distribution
    }
    timestamp 역순.
    """
    output_dir = Path(output_dir).expanduser()
    if not output_dir.exists():
        return []

    history: list[dict] = []

    # 활성
    for csv_path in sorted(output_dir.glob("opendata_*.csv"), reverse=True):
        meta = _read_meta_for(csv_path)
        history.append({
            "file_name": csv_path.name,
            "file_path": str(csv_path),
            "status": "active",
            "exported_at": meta.get("exported_at", ""),
            "count": meta.get("count", _count_rows(csv_path)),
            "sido_distribution": meta.get("sido_distribution", {}),
        })

    # 롤백된
    rb_dir = output_dir / "_rolled_back"
    if rb_dir.exists():
        for csv_path in sorted(rb_dir.glob("opendata_*.csv"), reverse=True):
            meta = _read_meta_for(csv_path)
            history.append({
                "file_name": csv_path.name,
                "file_path": str(csv_path),
                "status": "rolled_back",
                "exported_at": meta.get("exported_at", ""),
                "count": meta.get("count", _count_rows(csv_path)),
                "sido_distribution": meta.get("sido_distribution", {}),
            })

    history.sort(key=lambda x: x.get("exported_at") or x.get("file_name"), reverse=True)
    return history


def _read_meta_for(csv_path: Path) -> dict:
    meta_path = csv_path.with_suffix(csv_path.suffix + ".meta.json")
    if not meta_path.exists():
        # 옛 호환 — 일부 옛 형태도 시도
        alt = csv_path.parent / f"{csv_path.name}.meta.json"
        if alt.exists():
            meta_path = alt
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _count_rows(csv_path: Path) -> int:
    try:
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            return max(0, sum(1 for _ in reader) - 1)
    except Exception:
        return 0


# ─────────────────────────────────────────
# 롤백 — 활성 환원을 `_rolled_back/` 으로 이동
# ─────────────────────────────────────────
def rollback_export(file_path: Path | str) -> dict:
    """특정 환원 파일을 _rolled_back/ 으로 이동 (삭제 X).

    Returns: {"ok": bool, "new_path": str | "", "message": str}
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return {"ok": False, "new_path": "", "message": "파일이 없습니다."}
    if file_path.parent.name == "_rolled_back":
        return {"ok": False, "new_path": str(file_path),
                "message": "이미 롤백된 항목입니다."}

    rb_dir = file_path.parent / "_rolled_back"
    rb_dir.mkdir(exist_ok=True)
    new_path = rb_dir / file_path.name
    try:
        file_path.rename(new_path)
        # 메타 파일도 함께 이동
        meta_path = file_path.with_suffix(file_path.suffix + ".meta.json")
        if meta_path.exists():
            meta_path.rename(rb_dir / meta_path.name)
        # 감사 로그 — 롤백도 민감 행위
        try:
            from modules.audit import log as _audit
            _audit("opendata.rollback",
                   actor_role="교육청",
                   target=file_path.name)
        except Exception:
            pass
        return {"ok": True, "new_path": str(new_path),
                "message": "롤백 완료 — 대시보드 새로고침 시 반영에서 제외됩니다."}
    except Exception as e:
        return {"ok": False, "new_path": "",
                "message": f"롤백 실패: {type(e).__name__}: {e}"}


def restore_export(rolled_back_file_path: Path | str) -> dict:
    """롤백된 환원 파일을 다시 활성으로 복구 (선택 기능).

    Returns: {"ok": bool, "new_path": str | "", "message": str}
    """
    file_path = Path(rolled_back_file_path)
    if not file_path.exists() or file_path.parent.name != "_rolled_back":
        return {"ok": False, "new_path": "", "message": "롤백된 파일이 아닙니다."}

    target_dir = file_path.parent.parent
    new_path = target_dir / file_path.name
    try:
        file_path.rename(new_path)
        meta_path = file_path.with_suffix(file_path.suffix + ".meta.json")
        if meta_path.exists():
            meta_path.rename(target_dir / meta_path.name)
        return {"ok": True, "new_path": str(new_path),
                "message": "복구 완료 — 다시 활성으로 표시됩니다."}
    except Exception as e:
        return {"ok": False, "new_path": "",
                "message": f"복구 실패: {type(e).__name__}: {e}"}


# ─────────────────────────────────────────
# 기본 공유 폴더 경로 (사용자가 override 가능)
# ─────────────────────────────────────────
def default_shared_dir() -> Path:
    """대시보드도 같은 위치를 기본값으로 사용해야 자동 연결됨."""
    return Path.home() / "Desktop" / "공공데이터 공모전" / "03_분석_데이터" / "점검_환원"
