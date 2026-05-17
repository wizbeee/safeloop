"""
SQLite 인덱스 — master.json 파일 위에 검색·집계용 빠른 인덱스.

설계 원칙:
- **master.json 이 단일 진실(source of truth)**. SQLite 는 인덱스 / 캐시 역할만.
- 인덱스가 깨져도 `rebuild_index()` 로 모든 master.json 재스캔해 재구축 가능.
- 학교별·세션별 row 1개. 통합 record 는 별도 테이블.
- 동시 쓰기 안전 — SQLite WAL 모드 사용.
- 외부 의존성 없음 — Python 표준 라이브러리 sqlite3 만.

테이블:
- inspections: 단일 점검 메타 (학교/공간/점수/상태/제출자/타임스탬프)
- consolidated_records: 통합 보고서 메타
- index_meta: 마지막 재구축 시각 등

운영:
- 새 점검 저장 시 `upsert_inspection_index()` 호출 — master.json + 인덱스 동시 갱신.
- 검색은 `query_inspections()` — SQL WHERE 절로 빠름.
- 인덱스 파일 손상·삭제 시 `rebuild_index()` 가 디스크 master.json 들 스캔해 복구.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


# 인덱스 파일 위치 — _ai_cache 처럼 시스템 디렉터리 prefix
_DB_DIR = Path(__file__).resolve().parent.parent / "school_storage" / "_index"
_DB_PATH = _DB_DIR / "safeloop_index.db"
_DB_LOCK = threading.Lock()  # 멀티스레드 쓰기 안전 (Streamlit rerun 동시성 보호)

KST = datetime.timezone(datetime.timedelta(hours=9))


def _now_iso() -> str:
    return datetime.datetime.now(KST).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    """SQLite 연결 — WAL 모드 + foreign keys."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=10.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """테이블·인덱스 초기 생성 (idempotent)."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS inspections (
        school_code     TEXT NOT NULL,
        session_id      TEXT NOT NULL,
        school_name     TEXT,
        sido            TEXT,
        space_id        TEXT,
        space_type      TEXT,
        space_nickname  TEXT,
        score           REAL,
        grade           TEXT,
        status          TEXT,
        submitter_name  TEXT,
        submitter_role  TEXT,
        submitter_manager_id TEXT,
        timestamp       TEXT,
        history_count   INTEGER DEFAULT 0,
        master_path     TEXT,
        updated_at      TEXT NOT NULL,
        PRIMARY KEY (school_code, session_id)
    );

    CREATE INDEX IF NOT EXISTS idx_insp_school ON inspections(school_code);
    CREATE INDEX IF NOT EXISTS idx_insp_status ON inspections(status);
    CREATE INDEX IF NOT EXISTS idx_insp_submitter ON inspections(submitter_manager_id);
    CREATE INDEX IF NOT EXISTS idx_insp_timestamp ON inspections(timestamp DESC);

    CREATE TABLE IF NOT EXISTS consolidated_records (
        school_code     TEXT NOT NULL,
        file_name       TEXT NOT NULL,
        sido            TEXT,
        spaces_count    INTEGER,
        average_score   REAL,
        submission_ts   TEXT,
        receipt_path    TEXT,
        updated_at      TEXT NOT NULL,
        PRIMARY KEY (school_code, file_name)
    );

    CREATE TABLE IF NOT EXISTS index_meta (
        key   TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT NOT NULL
    );
    """)


def init_db() -> None:
    """첫 호출 시 DB·스키마 보장. 멱등."""
    with _DB_LOCK:
        conn = _connect()
        try:
            _ensure_schema(conn)
        finally:
            conn.close()


def _row_from_master(school_code: str, session_id: str,
                      master: dict, master_path: Path) -> dict:
    """master.json 한 건에서 인덱스 컬럼 추출."""
    school = master.get("school") or {}
    space = master.get("space") or {}
    score_result = ((master.get("inspection") or {}).get("score_result") or {})
    submitter = master.get("submitter") or {}
    history = master.get("status_history") or []
    return {
        "school_code": school_code,
        "session_id": session_id,
        "school_name": school.get("name"),
        "sido": school.get("sido"),
        "space_id": space.get("id"),
        "space_type": space.get("type"),
        "space_nickname": space.get("nickname"),
        "score": score_result.get("score"),
        "grade": score_result.get("grade"),
        "status": master.get("status") or "approved",
        "submitter_name": submitter.get("name"),
        "submitter_role": submitter.get("role"),
        "submitter_manager_id": submitter.get("manager_id"),
        "timestamp": master.get("timestamp"),
        "history_count": len(history),
        "master_path": str(master_path),
        "updated_at": _now_iso(),
    }


def upsert_inspection_index(school_code: str, session_id: str,
                              master: dict, master_path: Path) -> None:
    """master.json 저장·갱신 직후 호출. 인덱스 행 upsert."""
    if not school_code or not session_id:
        return
    row = _row_from_master(school_code, session_id, master, master_path)
    cols = list(row.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)
    update_list = ", ".join([f"{c}=excluded.{c}" for c in cols
                              if c not in ("school_code", "session_id")])
    sql = (
        f"INSERT INTO inspections ({col_list}) VALUES ({placeholders}) "
        f"ON CONFLICT(school_code, session_id) DO UPDATE SET {update_list}"
    )
    with _DB_LOCK:
        conn = _connect()
        try:
            _ensure_schema(conn)
            conn.execute(sql, [row[c] for c in cols])
        finally:
            conn.close()


def delete_inspection_index(school_code: str, session_id: str) -> None:
    """점검 삭제 시 인덱스 행도 삭제."""
    with _DB_LOCK:
        conn = _connect()
        try:
            _ensure_schema(conn)
            conn.execute(
                "DELETE FROM inspections WHERE school_code=? AND session_id=?",
                (school_code, session_id),
            )
        finally:
            conn.close()


def query_inspections(
    school_code: str | None = None,
    status: str | None = None,
    submitter_manager_id: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """인덱스에서 빠른 검색. 결과는 timestamp 내림차순.

    인덱스 미존재 시 빈 리스트 반환 — 호출 측이 디스크 fallback 가능.
    """
    where, params = [], []
    if school_code:
        where.append("school_code = ?")
        params.append(school_code)
    if status:
        where.append("status = ?")
        params.append(status)
    if submitter_manager_id:
        where.append("submitter_manager_id = ?")
        params.append(submitter_manager_id)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (
        f"SELECT * FROM inspections{where_sql} "
        f"ORDER BY timestamp DESC LIMIT ?"
    )
    params.append(limit)
    with _DB_LOCK:
        conn = _connect()
        try:
            _ensure_schema(conn)
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def count_inspections(school_code: str, status: str | None = None) -> int:
    """학교 단위 카운트. 사이드바 배지 등에 빠른 호출용."""
    where = ["school_code = ?"]
    params: list[Any] = [school_code]
    if status:
        where.append("status = ?")
        params.append(status)
    sql = f"SELECT COUNT(*) AS c FROM inspections WHERE {' AND '.join(where)}"
    with _DB_LOCK:
        conn = _connect()
        try:
            _ensure_schema(conn)
            row = conn.execute(sql, params).fetchone()
            return int(row["c"]) if row else 0
        finally:
            conn.close()


def rebuild_index(storage_dir: Path) -> dict:
    """디스크의 모든 master.json 을 스캔해 인덱스 전체 재구축.

    인덱스 파일이 손상되거나 외부 도구로 master.json 직접 추가한 경우 호출.
    Returns: {"inspections": N, "errors": [...]}
    """
    errors: list[str] = []
    n = 0
    with _DB_LOCK:
        conn = _connect()
        try:
            _ensure_schema(conn)
            conn.execute("DELETE FROM inspections")
            if storage_dir.exists():
                for school_dir in storage_dir.iterdir():
                    if not school_dir.is_dir() or school_dir.name.startswith("_"):
                        continue
                    school_code = school_dir.name
                    for sess in school_dir.iterdir():
                        if not sess.is_dir() or sess.name.startswith("_"):
                            continue
                        master_path = sess / "master.json"
                        if not master_path.exists():
                            continue
                        try:
                            master = json.loads(
                                master_path.read_text(encoding="utf-8")
                            )
                        except Exception as e:
                            errors.append(f"{master_path}: {e}")
                            continue
                        row = _row_from_master(
                            school_code, sess.name, master, master_path,
                        )
                        cols = list(row.keys())
                        placeholders = ", ".join(["?"] * len(cols))
                        conn.execute(
                            f"INSERT INTO inspections ({', '.join(cols)}) "
                            f"VALUES ({placeholders})",
                            [row[c] for c in cols],
                        )
                        n += 1
            conn.execute(
                "INSERT OR REPLACE INTO index_meta (key, value, updated_at) "
                "VALUES ('last_rebuild', ?, ?)",
                (str(n), _now_iso()),
            )
        finally:
            conn.close()
    return {"inspections": n, "errors": errors}


def get_index_stats() -> dict:
    """인덱스 상태 — 행 수·마지막 재구축 시각. 설정 페이지 표시용."""
    with _DB_LOCK:
        conn = _connect()
        try:
            _ensure_schema(conn)
            n_insp = conn.execute(
                "SELECT COUNT(*) AS c FROM inspections"
            ).fetchone()["c"]
            meta = conn.execute(
                "SELECT value, updated_at FROM index_meta WHERE key='last_rebuild'"
            ).fetchone()
            return {
                "inspections": int(n_insp),
                "last_rebuild": meta["updated_at"] if meta else None,
                "db_path": str(_DB_PATH),
            }
        finally:
            conn.close()
