"""실 담당자 관리 — 학교별 명부 + PIN 발급·검증.

학교 담당자가 실 담당자(화학실·물리실·디자인실 등 공간 담당 교사)를 등록하고
PIN을 발급한다. **발급 직후 1회만 평문이 반환**되며, 이후 저장소엔 SHA-256
해시만 남는다. PIN을 잊어버리면 `reissue_pin` 으로 새로 발급.

설계 원칙:
- 학교별 격리: `school_storage/<school_code>/_managers.json` — 다른 학교 매니저
  정보 노출 불가
- 1:N 다대다 허용: 실 담당자 1명이 여러 공간 담당 가능 (한 교사가 화학실 +
  물리실 둘 다 담당하는 현실 반영)
- soft delete: `active=False` 로 비활성화. 데이터는 보존 (감사 이력 보존)
- PIN 평문 미저장: `pin_hash` 만 저장. 평문 분실 시 reissue 만이 복구 경로

데이터 스키마 (_managers.json):
{
  "school_code": "S010000856",
  "managers": [
    {
      "manager_id": "M001",
      "name": "홍길동",
      "email": "hong@example.com",
      "phone": "010-1234-5678",
      "assigned_space_ids": ["sp_chem_3a", "sp_phys_2b"],
      "pin_hash": "<sha256-hex>",
      "active": true,
      "created_at": "2026-05-12T...",
      "last_login_at": null,
      "updated_at": "2026-05-12T..."
    }
  ]
}
"""
from __future__ import annotations

import datetime

KST = datetime.timezone(datetime.timedelta(hours=9))
import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = ROOT / "school_storage"

_PIN_HASH_SALT = "SAFELOOP-MANAGER-PIN-v1"
_PIN_LENGTH = 6
_MAX_REISSUE_ATTEMPTS = 10 # 충돌 회피 (실제로는 1회 안에 거의 다 성공)


# ─────────────────────────────────────────
# 내부 헬퍼
# ─────────────────────────────────────────
def _managers_path(school_code: str) -> Path:
    """학교별 매니저 명부 파일 경로."""
    p = STORAGE_DIR / str(school_code or "_unknown")
    p.mkdir(parents=True, exist_ok=True)
    return p / "_managers.json"


def _hash_pin(pin: str) -> str:
    """PIN SHA-256 해시 (16진수 64자)."""
    return hashlib.sha256(
        f"{_PIN_HASH_SALT}|{pin}".encode("utf-8")
    ).hexdigest()


def _generate_pin() -> str:
    """6자리 무작위 숫자 PIN. 앞자리 0 허용."""
    return f"{secrets.randbelow(10 ** _PIN_LENGTH):0{_PIN_LENGTH}d}"


def _now_iso() -> str:
    return datetime.datetime.now(KST).isoformat(timespec="seconds")


def _empty_record(school_code: str) -> dict:
    return {"school_code": str(school_code), "managers": []}


def _load_raw(school_code: str) -> dict:
    """디스크에서 매니저 명부 raw dict 로드. 없으면 빈 레코드."""
    if not school_code:
        return _empty_record("")
    p = _managers_path(school_code)
    if not p.exists():
        return _empty_record(school_code)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "managers" not in data:
            return _empty_record(school_code)
        data.setdefault("school_code", str(school_code))
        if not isinstance(data["managers"], list):
            data["managers"] = []
        return data
    except Exception:
        return _empty_record(school_code)


def _save_raw(school_code: str, data: dict) -> None:
    """매니저 명부를 디스크에 저장."""
    p = _managers_path(school_code)
    p.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _next_manager_id(managers: list[dict]) -> str:
    """다음 manager_id 자동 생성. M001 M002 ..."""
    max_num = 0
    for m in managers:
        mid = str(m.get("manager_id", ""))
        if mid.startswith("M") and mid[1:].isdigit():
            max_num = max(max_num, int(mid[1:]))
    return f"M{max_num + 1:03d}"


def _public_view(m: dict) -> dict:
    """매니저 dict 에서 pin_hash 를 제외한 공개 안전 사본."""
    return {k: v for k, v in m.items() if k != "pin_hash"}


# ─────────────────────────────────────────
# 공개 API — 조회
# ─────────────────────────────────────────
def list_managers(school_code: str, include_inactive: bool = False) -> list[dict]:
    """학교 매니저 명부. pin_hash 는 빠진 공개 사본 반환.

    Args:
        school_code: 학교 코드
        include_inactive: True 면 비활성 매니저도 포함 (감사용)
    """
    data = _load_raw(school_code)
    out = []
    for m in data.get("managers", []):
        if not include_inactive and not m.get("active", True):
            continue
        out.append(_public_view(m))
    return out


def get_manager(school_code: str, manager_id: str) -> dict | None:
    """특정 매니저 단건 조회 (pin_hash 제외 공개 사본). 없거나 비활성이면 None."""
    if not school_code or not manager_id:
        return None
    data = _load_raw(school_code)
    for m in data.get("managers", []):
        if m.get("manager_id") == manager_id and m.get("active", True):
            return _public_view(m)
    return None


def get_managers_for_space(school_code: str, space_id: str) -> list[dict]:
    """특정 공간을 담당하는 활성 매니저 목록 (1:N 가능)."""
    if not school_code or not space_id:
        return []
    return [
        m for m in list_managers(school_code)
        if space_id in (m.get("assigned_space_ids") or [])
    ]


# ─────────────────────────────────────────
# 공개 API — 등록·수정·비활성화
# ─────────────────────────────────────────
def add_manager(
    school_code: str,
    name: str,
    email: str = "",
    phone: str = "",
    assigned_space_ids: list[str] | None = None,
) -> tuple[dict, str]:
    """새 실 담당자 등록. 반환: (공개 사본 dict, 평문 PIN — 1회만 노출).

    Raises:
        ValueError: school_code 또는 name 누락
    """
    if not school_code:
        raise ValueError("school_code 가 필요합니다")
    if not name or not str(name).strip():
        raise ValueError("실 담당자 이름이 필요합니다")

    data = _load_raw(school_code)
    managers = data.get("managers", [])
    pin = _generate_pin()
    now = _now_iso()
    new_record = {
        "manager_id": _next_manager_id(managers),
        "name": str(name).strip(),
        "email": str(email or "").strip(),
        "phone": str(phone or "").strip(),
        "assigned_space_ids": list(assigned_space_ids or []),
        "pin_hash": _hash_pin(pin),
        "active": True,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
    }
    managers.append(new_record)
    data["managers"] = managers
    _save_raw(school_code, data)
    return _public_view(new_record), pin


def update_manager(
    school_code: str,
    manager_id: str,
    *,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    assigned_space_ids: list[str] | None = None,
) -> dict | None:
    """매니저 정보 수정. None 인 인자는 변경하지 않음. 공개 사본 반환."""
    if not school_code or not manager_id:
        return None
    data = _load_raw(school_code)
    for m in data.get("managers", []):
        if m.get("manager_id") != manager_id:
            continue
        if name is not None and str(name).strip():
            m["name"] = str(name).strip()
        if email is not None:
            m["email"] = str(email or "").strip()
        if phone is not None:
            m["phone"] = str(phone or "").strip()
        if assigned_space_ids is not None:
            m["assigned_space_ids"] = list(assigned_space_ids)
        m["updated_at"] = _now_iso()
        _save_raw(school_code, data)
        return _public_view(m)
    return None


def deactivate_manager(school_code: str, manager_id: str) -> bool:
    """soft delete — active=False. 데이터는 보존 (감사 이력)."""
    if not school_code or not manager_id:
        return False
    data = _load_raw(school_code)
    for m in data.get("managers", []):
        if m.get("manager_id") == manager_id and m.get("active", True):
            m["active"] = False
            m["updated_at"] = _now_iso()
            _save_raw(school_code, data)
            return True
    return False


def reactivate_manager(school_code: str, manager_id: str) -> bool:
    """비활성 매니저를 다시 활성화 (감사 이력 보존됨)."""
    if not school_code or not manager_id:
        return False
    data = _load_raw(school_code)
    for m in data.get("managers", []):
        if m.get("manager_id") == manager_id and not m.get("active", True):
            m["active"] = True
            m["updated_at"] = _now_iso()
            _save_raw(school_code, data)
            return True
    return False


# ─────────────────────────────────────────
# 공개 API — PIN 발급·검증
# ─────────────────────────────────────────
def reissue_pin(school_code: str, manager_id: str) -> str | None:
    """매니저 PIN 재발급. 새 평문 PIN 반환 (1회 노출).

    잊어버린 경우의 유일한 복구 경로. 학교 담당자만 호출해야 함 (UI 권한).
    """
    if not school_code or not manager_id:
        return None
    data = _load_raw(school_code)
    for m in data.get("managers", []):
        if m.get("manager_id") == manager_id and m.get("active", True):
            new_pin = _generate_pin()
            m["pin_hash"] = _hash_pin(new_pin)
            m["updated_at"] = _now_iso()
            _save_raw(school_code, data)
            return new_pin
    return None


def verify_manager_pin(school_code: str, manager_id: str, pin: str) -> bool:
    """매니저 PIN 검증. 비활성 매니저는 항상 False."""
    if not school_code or not manager_id or not pin:
        return False
    data = _load_raw(school_code)
    for m in data.get("managers", []):
        if m.get("manager_id") != manager_id:
            continue
        if not m.get("active", True):
            return False
        return m.get("pin_hash") == _hash_pin(str(pin).strip())
    return False


def authenticate_manager(
    school_code: str, manager_id: str, pin: str,
) -> dict | None:
    """검증 통과 시 매니저 공개 사본 반환 + last_login_at 갱신. 실패는 None."""
    if not verify_manager_pin(school_code, manager_id, pin):
        return None
    data = _load_raw(school_code)
    for m in data.get("managers", []):
        if m.get("manager_id") == manager_id:
            m["last_login_at"] = _now_iso()
            _save_raw(school_code, data)
            return _public_view(m)
    return None


# ─────────────────────────────────────────
# 시연·테스트 보조 — SAFELOOP_DEMO_MODE 환경에서만 사용 권장
# ─────────────────────────────────────────
# 시연 모드 고정 PIN — 사용자가 화면에서 보고 바로 입력 가능
DEMO_PIN = "000000"


def ensure_demo_manager(
    school_code: str,
    name: str = "데모 담당교사",
    assigned_space_ids: list[str] | None = None,
) -> dict:
    """시연·테스트용 매니저가 학교에 1명 이상 있도록 보장.

    - 이미 활성 매니저가 있으면 첫 매니저 정보 반환 (assigned_space_ids 만 갱신)
    - 없으면 새로 추가하되 PIN 을 DEMO_PIN("000000") 으로 고정 (시연 편의)
      사용자가 화면에서 PIN 입력 시 헷갈리지 않도록

    운영 보안: 시연 모드(SAFELOOP_DEMO_MODE=1 또는 session.demo_mode=True) 가
    아닌 환경에서 호출되면 RuntimeError 를 발생시켜 운영 데이터에 알려진
    데모 PIN(000000) 매니저가 생성되는 사고를 방지.

    Returns: 공개 사본 dict (pin_hash 미포함)
    """
    if not school_code:
        raise ValueError("school_code 가 필요합니다")

    # 운영 모드 방어 가드 — 데모 PIN 매니저가 운영 데이터에 섞이는 사고 차단
    import os as _os
    _demo_env = _os.environ.get("SAFELOOP_DEMO_MODE") == "1"
    _demo_session = False
    try:
        import streamlit as _st
        _demo_session = bool(_st.session_state.get("demo_mode"))
    except Exception:
        pass
    if not (_demo_env or _demo_session):
        raise RuntimeError(
            "ensure_demo_manager 는 시연 모드에서만 호출 가능합니다 "
            "(SAFELOOP_DEMO_MODE=1 또는 session demo_mode=True). "
            "운영 환경에서 데모 PIN(000000) 매니저 생성 차단."
        )
    spaces = list(assigned_space_ids or [])

    data = _load_raw(school_code)
    actives = [m for m in data.get("managers", []) if m.get("active", True)]
    if actives:
        first = actives[0]
        # 시연 흐름에서 새 공간이 추가됐다면 합집합으로 갱신
        cur = set(first.get("assigned_space_ids") or [])
        merged = sorted(cur | set(spaces))
        if merged != sorted(cur):
            first["assigned_space_ids"] = merged
            first["updated_at"] = _now_iso()
            _save_raw(school_code, data)
        return _public_view(first)

    # 새 데모 매니저 — PIN 고정 (시연 화면에서 안내 노출)
    now = _now_iso()
    new_record = {
        "manager_id": _next_manager_id(data.get("managers", [])),
        "name": str(name).strip() or "데모 담당교사",
        "email": "demo@safeloop.test",
        "phone": "",
        "assigned_space_ids": spaces,
        "pin_hash": _hash_pin(DEMO_PIN),
        "active": True,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
        "_demo": True, # 시연용 매니저임을 표시 (운영 데이터와 구분)
    }
    data.setdefault("managers", []).append(new_record)
    _save_raw(school_code, data)
    return _public_view(new_record)


def is_demo_manager(manager: dict) -> bool:
    """매니저 공개 사본이 시연용으로 자동 생성된 것인지 검사."""
    return bool(manager and manager.get("_demo"))
