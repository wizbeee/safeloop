"""감사 로그 (audit log) — 누가 언제 어떤 데이터에 접근했는지 JSONL 기록.

목적:
- 민감 행위(점검 제출·승인·반려·통합 발송·환원·삭제) 의 누구·언제·무엇 기록
- 운영 사고 추적 기반 (예: "이 환원 데이터 누가 export 했나?")
- 시연 모드 잔여 정리 시 함께 정리 (system 디렉토리)

저장 위치:
    school_storage/_audit/audit_YYYYMMDD.jsonl
    하루 단위 파일 · append-only · JSONL (한 줄 = 한 이벤트)

기록 형식 (예):
    {"ts": "2026-05-21T14:23:45+09:00", "actor_role": "교육청",
     "actor_id": "EDU-OFFICE", "action": "edu.inbox.delete",
     "target": "충청남도교육청/single_화학실_240520.json",
     "meta": {"reason": "테스트 정리"}}

설계 원칙:
- 민감 정보(PIN, 평문 파일 내용) 미기록
- 실패 시 silent — 로그 실패가 본 작업을 막으면 안 됨
- 시연 모드도 기록 (동작 검증용)
- JSONL 단순 형식 — pandas 로 바로 분석 가능
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any


# storage.py 와 동일한 ROOT 사용 (순환 import 피하려 직접 계산)
_ROOT = Path(__file__).resolve().parent.parent
_AUDIT_DIR = _ROOT / "school_storage" / "_audit"

# KST 일관성
_KST = datetime.timezone(datetime.timedelta(hours=9))


def _audit_file_for_today() -> Path:
    """오늘 날짜 audit 파일 경로 (KST 기준)."""
    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.datetime.now(_KST).strftime("%Y%m%d")
    return _AUDIT_DIR / f"audit_{today}.jsonl"


def log(
    action: str,
    actor_role: str | None = None,
    actor_id: str | None = None,
    target: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """감사 로그 1건 append.

    action: dot.separated.identifier 형식 권장
        예: "edu.inbox.delete", "school.submit", "school.consolidate",
            "school.dispatch", "opendata.export", "opendata.rollback",
            "manager.create", "manager.deactivate", "auth.login.success",
            "auth.login.fail"
    actor_role: "실" / "학교" / "교육청" / None (시스템)
    actor_id: 매니저 ID 또는 학교 코드 등 (PII 가 아닌 식별자)
    target: 영향받은 자원 (파일명·세션 ID 등)
    meta: 추가 컨텍스트 (PII·평문 금지)

    실패해도 예외 발생 안 함 (본 작업 흐름 보호).
    """
    try:
        event = {
            "ts": datetime.datetime.now(_KST).isoformat(timespec="seconds"),
            "action": str(action or "unknown")[:80],
            "actor_role": str(actor_role) if actor_role else None,
            "actor_id": str(actor_id) if actor_id else None,
            "target": str(target)[:200] if target else None,
            "meta": meta if isinstance(meta, dict) else None,
        }
        # PII·평문 방지 — meta 안의 흔한 위험 키 제거
        if isinstance(event.get("meta"), dict):
            for risky in ("pin", "password", "email", "phone",
                           "raw_content", "raw_text", "ssn"):
                event["meta"].pop(risky, None)
        line = json.dumps(event, ensure_ascii=False) + "\n"
        with _audit_file_for_today().open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # silent — 로그 실패가 본 작업 흐름을 막으면 안 됨
        pass


def recent_events(limit: int = 50, action_prefix: str | None = None) -> list[dict]:
    """최근 audit 이벤트 N건 반환 (오늘 + 어제 파일).

    action_prefix 가 있으면 그것으로 시작하는 action 만 필터.
    """
    out: list[dict] = []
    if not _AUDIT_DIR.exists():
        return out
    files = sorted(_AUDIT_DIR.glob("audit_*.jsonl"), reverse=True)[:5]
    for f in files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for ln in reversed(lines):
            ln = ln.strip()
            if not ln:
                continue
            try:
                ev = json.loads(ln)
            except Exception:
                continue
            if action_prefix and not str(ev.get("action", "")).startswith(action_prefix):
                continue
            out.append(ev)
            if len(out) >= limit:
                return out
    return out


def summary_by_action(days: int = 7) -> dict[str, int]:
    """최근 N일 audit 이벤트의 action 별 카운트 (운영 모니터링용)."""
    counts: dict[str, int] = {}
    if not _AUDIT_DIR.exists():
        return counts
    cutoff = datetime.datetime.now(_KST) - datetime.timedelta(days=days)
    cutoff_iso = cutoff.isoformat(timespec="seconds")
    for f in sorted(_AUDIT_DIR.glob("audit_*.jsonl")):
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                ev = json.loads(ln)
            except Exception:
                continue
            if str(ev.get("ts", "")) < cutoff_iso:
                continue
            act = str(ev.get("action") or "unknown")
            counts[act] = counts.get(act, 0) + 1
    return counts
