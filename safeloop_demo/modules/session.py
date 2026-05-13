"""
Streamlit 세션 상태 헬퍼.

단계별(Step 1~7) 데이터를 세션 상태에 누적 저장하고,
페이지 간에 일관되게 전달한다.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

DEFAULT_STATE = {
    # 학교 식별 (Step 1)
    "school": None,          # {"정보공시 학교코드": ..., "학교명": ..., ...}
    # 학교 인증번호(6자리) 통과 여부 — 학교 담당자(role="학교") 흐름에서 사용.
    # 실 담당자(role="실")의 인증 통과는 space_manager 객체 존재로 판단한다
    # (별도 플래그 없음). is_authenticated_for_role() 헬퍼로 통합 검사 권장.
    "school_auth_verified": False,

    # 공간 (Step 2)
    "active_space": None,    # {"space_id": "...", "type": "화학실", "nickname": "3층 A"}
    "registered_spaces": [], # 학교별 공간 목록

    # 촬영 (Step 3) — 실제 사진 저장은 `shots` dict 사용 (페이지 단계에서 초기화).
    # 이전 captured_images 필드는 사용되지 않아 제거됨 (2026-04-26).

    # AI 파이프라인 (Step 4)
    "stage1_result": None,
    "stage2_result": None,
    "stage2_confirmed": None,   # 사용자 확정 결과
    "stage3_result": None,

    # 현장 점검 (Step 5)
    "item_scores": {},          # {항목: 0/0.5/1}
    "score_result": None,

    # AI 추천 (Step 6)
    "recommendations": None,

    # 저장 (Step 7)
    "saved_session_id": None,
    "eduline": None,                    # 결재라인 (PDF 표시용 — 학교마다 양식 다르므로 참고용)
    "edu_package_ready": False,         # 통합 PDF 다운로드 준비 플래그
    "internal_approval_confirmed": False,  # 학교 내부 결재 완료 확인 (교육청 발송 활성화 조건)
    "my_email": "",                     # 본인 이메일 (학교 또는 교육청 담당자)
    "edu_office_email": "",             # 교육청 담당자 이메일 (학교가 등록 — 발송 대상)

    # 모드 — 환경변수 또는 URL 파라미터로 결정 (ensure_state 에서 처리)
    # 기본 False (실 사용). SAFELOOP_DEMO_MODE=1 또는 ?demo=1 시 True.
    "demo_mode": False,
    "role": "학교",             # "실" | "학교" | "교육청"

    # 실 담당자 정보 — role="실" 인증 통과 시 저장
    # {"manager_id": "M001", "name": "홍길동", "email": ..., "phone": ...,
    #  "assigned_space_ids": ["sp_chem_3a", ...], "active": True, ...}
    "space_manager": None,

    # 전국 대시보드
    "filter_sido": None,

    # AI 공급자
    "ai_provider": None,        # None=자동, "anthropic" | "openai" 등
    "api_key_anthropic": "",
    "api_key_openai": "",
    "image_quality_check": True,

    # UX
    "_auth_prefill": "",        # 인증번호 자동 입력 버퍼
    "_seen_auth_help": False,
}


def ensure_state() -> None:
    for k, v in DEFAULT_STATE.items():
        if k not in st.session_state:
            st.session_state[k] = v if not isinstance(v, (list, dict)) else type(v)(v)
    # demo_mode 결정 — 환경변수 / URL 파라미터로 활성화
    # 1. SAFELOOP_DEMO_MODE=1 (콘테스트·시연 환경)
    # 2. URL ?demo=1 (사용자가 의도적으로 시연 진입)
    # 둘 중 하나면 True 로 강제. 명시적 활성화 외엔 실 사용 모드(False).
    import os
    if not st.session_state.get("_demo_mode_resolved"):
        env_demo = os.environ.get("SAFELOOP_DEMO_MODE") == "1"
        url_demo = False
        try:
            qp = st.query_params
            url_demo = str(qp.get("demo", "0")) in ("1", "true", "True")
        except Exception:
            pass
        if env_demo or url_demo:
            st.session_state["demo_mode"] = True
        st.session_state["_demo_mode_resolved"] = True


def has_unsaved_inspection_work() -> bool:
    """현재 세션에 저장되지 않은 점검 작업이 있는지 검사.

    True 면 다른 공간으로 전환하거나 페이지 떠날 때 사용자에게 경고해야 함.
    저장 직후엔 saved_session_id 가 채워지므로 False 가 됨.
    """
    saved = st.session_state.get("saved_session_id")
    has_progress = bool(
        st.session_state.get("stage2_result")
        or st.session_state.get("stage2_confirmed")
        or st.session_state.get("stage3_result")
        or st.session_state.get("score_result")
        or (st.session_state.get("item_scores") or {})
    )
    has_shots = any(
        len(v) > 0
        for v in (st.session_state.get("shots") or {}).values()
    )
    return (has_progress or has_shots) and not saved


def reset_inspection() -> None:
    """한 공간 점검 세션 초기화 (다른 공간 이어서 점검 시).
    학교 선택과 인증 상태, 등록된 공간 목록, 직전 저장 ID 이력은 유지."""
    # 직전 저장된 세션 ID는 별도 보관 → 결과 페이지에서 이력 추적 가능
    last_saved = st.session_state.get("saved_session_id")
    if last_saved:
        st.session_state.setdefault("_recent_saved_ids", [])
        if last_saved not in st.session_state["_recent_saved_ids"]:
            st.session_state["_recent_saved_ids"].insert(0, last_saved)
            st.session_state["_recent_saved_ids"] = st.session_state["_recent_saved_ids"][:10]

    for k in [
        "active_space",
        "stage1_result", "stage2_result",
        "stage2_confirmed", "stage3_result",
        "item_scores", "score_result", "recommendations",
        "saved_session_id", "edu_package_ready", "internal_approval_confirmed",
    ]:
        # DEFAULT_STATE 에 없는 키도 안전하게 처리 (KeyError 방지)
        default_v = DEFAULT_STATE.get(k)
        if isinstance(default_v, (list, dict)):
            st.session_state[k] = type(default_v)(default_v)
        else:
            st.session_state[k] = default_v
    # 샷 카운터·드래프트 복원 플래그도 정리
    st.session_state["shots"] = {}
    st.session_state["_draft_restored"] = False
    st.session_state["wizard_step"] = "shoot_1"
    if "_approval_demo_stage" in st.session_state:
        st.session_state["_approval_demo_stage"] = 0
    # 검토 B-1: cam_ctr 카운터 모두 회전 (사진 잔상 방지)
    for k in list(st.session_state.keys()):
        if k.startswith("cam_ctr_"):
            st.session_state[k] += 1


def reset_all() -> None:
    for k in DEFAULT_STATE:
        st.session_state[k] = DEFAULT_STATE[k] if not isinstance(DEFAULT_STATE[k], (list, dict)) \
            else type(DEFAULT_STATE[k])(DEFAULT_STATE[k])


def get(key: str, default: Any = None) -> Any:
    ensure_state()
    return st.session_state.get(key, default)


def stamp_activity() -> None:
    """페이지 진입마다 호출. 마지막 활동 시각 기록."""
    import datetime
    st.session_state["_last_activity"] = datetime.datetime.now().isoformat()


def session_age_minutes() -> float:
    """마지막 활동 이후 경과 분 (분)."""
    import datetime
    last = st.session_state.get("_last_activity")
    if not last:
        return 0.0
    try:
        delta = datetime.datetime.now() - datetime.datetime.fromisoformat(last)
        return delta.total_seconds() / 60.0
    except Exception:
        return 0.0


def set_(key: str, value: Any) -> None:
    ensure_state()
    st.session_state[key] = value


def is_authenticated_for_role() -> bool:
    """현재 역할에 맞는 인증이 통과되었는지 통합 검사.

    - role="실"   → space_manager 객체 존재 여부 (매니저 PIN 통과 시 set)
    - role="학교"/그 외 → school_auth_verified (학교 인증번호 통과 시 True)
    """
    role = st.session_state.get("role", "학교")
    if role == "실":
        mgr = st.session_state.get("space_manager")
        return bool(mgr and isinstance(mgr, dict) and mgr.get("manager_id"))
    return bool(st.session_state.get("school_auth_verified"))


def require_school() -> dict | None:
    """학교 선택·인증 완료 여부 확인. 미완료면 경고 표시 + None 반환.

    역할별 인증 방식이 달라 is_authenticated_for_role() 로 통합 검사한다.
    """
    ensure_state()
    school = st.session_state.get("school")
    if not school or not is_authenticated_for_role():
        st.warning("먼저 **학교 찾기** 페이지에서 학교를 선택하고 인증하세요.")
        return None
    return school


def require_active_space() -> dict | None:
    """공간 선택 여부 확인."""
    ensure_state()
    sp = st.session_state.get("active_space")
    if not sp or not isinstance(sp, dict) or not sp.get("type"):
        st.warning("점검할 **공간이 선택되지 않았습니다**. 점검 시작 페이지에서 공간을 선택하세요.")
        return None
    return sp


def require_space_manager() -> dict | None:
    """실 담당자 인증 완료 여부 확인. 미완료면 경고 + None 반환.

    role="실" 일 때만 의미가 있음. 호출 측에서 role 확인 후 사용.
    """
    ensure_state()
    mgr = st.session_state.get("space_manager")
    if not mgr or not isinstance(mgr, dict) or not mgr.get("manager_id"):
        st.warning("먼저 **실 담당자 인증**을 완료하세요.")
        return None
    return mgr


def is_space_manager_authenticated() -> bool:
    """실 담당자가 인증된 상태인지 (gate 없이 단순 검사)."""
    mgr = st.session_state.get("space_manager")
    return bool(mgr and isinstance(mgr, dict) and mgr.get("manager_id"))


def manager_can_access_space(space_id: str) -> bool:
    """현재 인증된 실 담당자가 해당 공간을 담당하는지 검사.

    학교/교육청 역할에서는 항상 True (권한 분리는 호출 측 role 분기로).
    """
    role = st.session_state.get("role", "학교")
    if role != "실":
        return True
    mgr = st.session_state.get("space_manager")
    if not mgr or not isinstance(mgr, dict):
        return False
    return space_id in (mgr.get("assigned_space_ids") or [])


def require_score_result() -> dict | None:
    """안전 점수 산출 여부 확인."""
    ensure_state()
    sr = st.session_state.get("score_result")
    if not sr or not isinstance(sr, dict) or "score" not in sr:
        st.warning("**점검 결과가 아직 산출되지 않았습니다**. AI 점검에서 점수 계산을 마치세요.")
        return None
    return sr
