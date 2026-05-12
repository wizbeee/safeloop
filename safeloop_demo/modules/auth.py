"""
SafeLoop 인증 모듈 — PIN 인증 + 30일 자동 로그인.

구조:
- 교육청 담당자 PIN: 상급기관(교육부/도교육청) 발급
- 학교 담당자 PIN: 학교별 6자리 인증번호 (issue_auth_code) — 별도 처리
- 자동 로그인: 쿠키에 PIN 해시를 저장 (30일 만료)
- 본인 지급 기기에서만 자동 로그인 권장

PIN 결정 우선순위:
1. 환경변수 `SAFELOOP_EDU_PIN` — 운영·교육청별 발급 흐름
2. SAFELOOP_DEMO_MODE=1 → 시연 PIN `EDU2026` 사용
3. 둘 다 없으면 시연 PIN `EDU2026` + 경고 (시연 환경 보호)

실 운영 시 GPKI(행정전자서명) 또는 KEIIS SSO 로 대체.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta
from typing import Literal

import streamlit as st

try:
    import extra_streamlit_components as stx
    _COOKIES_AVAILABLE = True
except ImportError:
    _COOKIES_AVAILABLE = False


RoleKey = Literal["edu"]

# 시연·콘테스트용 기본 PIN — 환경변수 미설정 시만 사용
_DEMO_EDU_PIN = "EDU2026"

# 잘못된 PIN 환경변수에 대한 1회 경고 (반복 노이즈 방지)
_pin_warning_emitted = False


def _resolve_edu_pin() -> str:
    """현재 교육청 담당자 PIN 결정.

    1. SAFELOOP_EDU_PIN 환경변수가 4자리 이상이면 그걸 사용
    2. 그 외에는 시연 PIN (`EDU2026`) + 1회 경고
    """
    global _pin_warning_emitted
    env_pin = os.environ.get("SAFELOOP_EDU_PIN", "").strip()
    if env_pin and len(env_pin) >= 4:
        return env_pin
    if not _pin_warning_emitted and os.environ.get("SAFELOOP_DEMO_MODE") != "1":
        _pin_warning_emitted = True
        try:
            st.warning(
                "⚠ SAFELOOP_EDU_PIN 환경변수 미설정 — 시연 기본 PIN 사용. "
                "운영 환경에서는 반드시 SAFELOOP_EDU_PIN 을 설정하세요."
            )
        except Exception:
            import sys
            print("[SafeLoop auth] SAFELOOP_EDU_PIN 미설정 — 시연 기본 PIN 사용",
                  file=sys.stderr)
    return _DEMO_EDU_PIN


# 동적 PIN 조회 — 매 호출마다 환경변수 확인 (테스트·핫리로드 호환)
def _pin_codes() -> dict[str, str]:
    return {"edu": _resolve_edu_pin()}


# 호환성 — 이전 코드가 import 하는 PIN_CODES (지연 초기화는 함수 사용 권장)
PIN_CODES: dict[str, str] = {"edu": _DEMO_EDU_PIN}

ROLE_LABEL: dict[str, str] = {
    "edu": "교육청 담당자",
}

ROLE_TO_SESSION_VALUE: dict[str, str] = {
    "edu": "교육청",
}

COOKIE_NAME = "safeloop_auth_token"
SCHOOL_COOKIE_NAME = "safeloop_school_remember"
MANAGER_COOKIE_NAME = "safeloop_manager_remember"
COOKIE_MGR_KEY = "safeloop_cookie_manager_v1"
AUTOLOGIN_DAYS = 30


def _hash_pin(role_key: str, pin: str) -> str:
    """PIN의 해시 (쿠키에 저장될 토큰)."""
    return hashlib.sha256(f"safeloop|{role_key}|{pin}".encode("utf-8")).hexdigest()[:32]


_SESSION_CM_KEY = "_safeloop_cookie_mgr"


def get_cookie_manager():
    """페이지 간 공유되는 단일 CookieManager 인스턴스.

    CookieManager는 widget 컴포넌트라 같은 key 로 두 번 생성하면 충돌한다.
    같은 페이지 안에서 여러 함수가 호출되어도 단일 인스턴스를 재사용하도록
    session_state에 캐시한다.
    """
    if not _COOKIES_AVAILABLE:
        return None
    if _SESSION_CM_KEY not in st.session_state:
        st.session_state[_SESSION_CM_KEY] = stx.CookieManager(key=COOKIE_MGR_KEY)
    return st.session_state[_SESSION_CM_KEY]


def verify_pin(role_key: str, pin: str) -> bool:
    """입력된 PIN이 해당 역할에 일치하는지 검증.

    PIN 은 환경변수 우선 — 매 호출 시 _pin_codes() 로 재조회하므로
    런타임 환경변수 변경에도 즉시 반영된다.
    """
    expected = _pin_codes().get(role_key, "")
    return bool(pin) and pin.strip() == expected


def is_authenticated_session(role_key: str) -> bool:
    """세션만 검사 (쿠키 호출 X — 가벼움). 보호 페이지에서 사용.

    페이지 진입 시마다 쿠키 IFrame 로드를 피하기 위함. 자동 로그인은 홈 또는
    인증 시점에 1회만 처리되고, 그 결과는 세션에 저장됨.
    """
    return bool(st.session_state.get(f"_auth_{role_key}", False))


def is_authenticated(role_key: str) -> bool:
    """세션 + 쿠키 검사 (자동 로그인 시도). 홈 또는 인증 시점에서만 사용 권장.

    cookie_manager 호출이 일어나므로 보호 페이지에서 매번 호출하면 깜빡임 발생.
    """
    if is_authenticated_session(role_key):
        return True
    cm = get_cookie_manager()
    if cm is None:
        return False
    try:
        token = cm.get(COOKIE_NAME)
    except Exception:
        token = None
    if not token:
        return False
    expected_token = _hash_pin(role_key, PIN_CODES[role_key])
    if token == expected_token:
        st.session_state[f"_auth_{role_key}"] = True
        return True
    return False


def set_authenticated(role_key: str, remember: bool = False) -> None:
    """인증 성공 시 호출. remember=True 면 30일 자동 로그인 쿠키 발급."""
    sess_key = f"_auth_{role_key}"
    st.session_state[sess_key] = True
    st.session_state["role"] = ROLE_TO_SESSION_VALUE[role_key]
    if remember:
        cm = get_cookie_manager()
        if cm is not None:
            try:
                cm.set(
                    COOKIE_NAME,
                    _hash_pin(role_key, PIN_CODES[role_key]),
                    expires_at=datetime.now() + timedelta(days=AUTOLOGIN_DAYS),
                    key=f"set_cookie_{role_key}",
                )
            except Exception:
                pass


def clear_authentication(role_key: str | None = None) -> None:
    """로그아웃. role_key=None 이면 모든 역할 인증 해제."""
    keys = [role_key] if role_key else list(PIN_CODES.keys())
    for k in keys:
        st.session_state[f"_auth_{k}"] = False
    cm = get_cookie_manager()
    if cm is not None:
        try:
            cm.delete(COOKIE_NAME, key=f"clear_cookie")
        except Exception:
            pass


# ─────────────────────────────────────────
# 학교 담당자 자동 로그인 — 학교 코드 + 6자리 인증번호 조합
# (학교별 인증은 modules.storage.issue_auth_code/verify_auth_code 가 담당)
# ─────────────────────────────────────────

def _hash_school(school_code: str, auth_code: str) -> str:
    """학교 코드 + 인증번호 해시 (쿠키에 저장될 토큰)."""
    return hashlib.sha256(
        f"safeloop|school|{school_code}|{auth_code}".encode("utf-8")
    ).hexdigest()[:32]


def remember_school(school_code: str, auth_code: str) -> None:
    """학교 인증 통과 후, 30일간 자동 로그인 토큰을 쿠키에 저장."""
    cm = get_cookie_manager()
    if cm is None:
        return
    try:
        token = _hash_school(school_code, auth_code)
        cm.set(
            SCHOOL_COOKIE_NAME,
            f"{school_code}|{token}",
            expires_at=datetime.now() + timedelta(days=AUTOLOGIN_DAYS),
            key=f"set_cookie_school",
        )
    except Exception:
        pass


def get_remembered_school() -> str | None:
    """쿠키에 저장된 자동 로그인 학교 코드를 반환 (없으면 None).

    토큰 검증은 호출 측에서 verify_school_token 으로 수행.
    """
    cm = get_cookie_manager()
    if cm is None:
        return None
    try:
        raw = cm.get(SCHOOL_COOKIE_NAME)
    except Exception:
        return None
    if not raw or "|" not in raw:
        return None
    school_code, _ = raw.split("|", 1)
    return school_code or None


def verify_school_token(school_code: str, auth_code: str) -> bool:
    """저장된 쿠키 토큰이 (학교 코드 + 인증번호) 와 일치하는지 검증."""
    cm = get_cookie_manager()
    if cm is None:
        return False
    try:
        raw = cm.get(SCHOOL_COOKIE_NAME)
    except Exception:
        return False
    if not raw or "|" not in raw:
        return False
    saved_code, saved_token = raw.split("|", 1)
    if saved_code != school_code:
        return False
    return saved_token == _hash_school(school_code, auth_code)


def forget_school() -> None:
    """학교 자동 로그인 해제."""
    cm = get_cookie_manager()
    if cm is None:
        return
    try:
        cm.delete(SCHOOL_COOKIE_NAME, key=f"clear_school_cookie")
    except Exception:
        pass


# ─────────────────────────────────────────
# 실 담당자(space manager) 자동 로그인 — 학교코드 + manager_id + PIN 조합
# (매니저 명부·PIN 검증은 modules.managers 가 담당)
# ─────────────────────────────────────────

def _hash_manager(school_code: str, manager_id: str, pin: str) -> str:
    """실 담당자 (학교코드 + manager_id + PIN) 해시 — 쿠키 저장용 토큰."""
    return hashlib.sha256(
        f"safeloop|manager|{school_code}|{manager_id}|{pin}".encode("utf-8")
    ).hexdigest()[:32]


def remember_manager(school_code: str, manager_id: str, pin: str) -> None:
    """매니저 인증 통과 후, 30일간 자동 로그인 토큰을 쿠키에 저장.

    본인 지급 기기에서만 호출 (공용 PC 에서는 호출하지 말 것).
    """
    cm = get_cookie_manager()
    if cm is None:
        return
    try:
        token = _hash_manager(school_code, manager_id, pin)
        cm.set(
            MANAGER_COOKIE_NAME,
            f"{school_code}|{manager_id}|{token}",
            expires_at=datetime.now() + timedelta(days=AUTOLOGIN_DAYS),
            key=f"set_cookie_manager",
        )
    except Exception:
        pass


def get_remembered_manager() -> tuple[str, str] | None:
    """쿠키에 저장된 자동 로그인 (school_code, manager_id) 반환.

    토큰 검증은 호출 측에서 verify_manager_token 으로 별도 수행.
    """
    cm = get_cookie_manager()
    if cm is None:
        return None
    try:
        raw = cm.get(MANAGER_COOKIE_NAME)
    except Exception:
        return None
    if not raw or raw.count("|") < 2:
        return None
    school_code, manager_id, _ = raw.split("|", 2)
    if not school_code or not manager_id:
        return None
    return (school_code, manager_id)


def verify_manager_token(school_code: str, manager_id: str, pin: str) -> bool:
    """저장된 쿠키 토큰이 (학교코드 + manager_id + PIN) 과 일치하는지 검증."""
    cm = get_cookie_manager()
    if cm is None:
        return False
    try:
        raw = cm.get(MANAGER_COOKIE_NAME)
    except Exception:
        return False
    if not raw or raw.count("|") < 2:
        return False
    saved_school, saved_mid, saved_token = raw.split("|", 2)
    if saved_school != school_code or saved_mid != manager_id:
        return False
    return saved_token == _hash_manager(school_code, manager_id, pin)


def forget_manager() -> None:
    """실 담당자 자동 로그인 해제."""
    cm = get_cookie_manager()
    if cm is None:
        return
    try:
        cm.delete(MANAGER_COOKIE_NAME, key=f"clear_manager_cookie")
    except Exception:
        pass


def render_pin_gate(
    role_key: str,
    on_success_redirect: str | None = None,
    cancel_label: str = "취소",
    cancel_redirect: str | None = "app.py",
) -> bool:
    """PIN 입력 박스 렌더. 인증 성공 시 True 반환 (호출 측에서 화면 분기).

    이미 인증된 경우 자동으로 True 반환 — 호출 측에서 별도 분기 없이 사용 가능.
    """
    if is_authenticated(role_key):
        return True

    role_label = ROLE_LABEL[role_key]

    st.markdown(
        f"<div style='padding:24px;border:1px solid #E5E5E8;border-radius:8px;"
        f"background:#FAFAFA;max-width:480px;margin:24px auto;'>"
        f"<div style='font-size:11px;letter-spacing:0.28em;color:#D50000;"
        f"font-weight:700;margin-bottom:8px;'>AUTHENTICATION</div>"
        f"<div style='font-size:18px;font-weight:700;color:#0A0A0B;margin-bottom:14px;'>"
        f"{role_label} 인증</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    pin_input = st.text_input(
        f"{role_label} 인증번호",
        type="password",
        key=f"_pin_input_{role_key}",
        placeholder="인증번호 입력",
    )
    remember = st.checkbox(
        f"✅ 이 기기에서 {AUTOLOGIN_DAYS}일 자동 로그인 (본인 지급 기기 권장)",
        value=False,
        key=f"_remember_{role_key}",
        help="본인 지급 기기에서만 체크하세요. 공용 PC·외부 기기에서는 해제. "
              f"체크 시 다음 접속부터 {AUTOLOGIN_DAYS}일간 PIN 재입력 없이 자동 진입.",
    )
    st.caption(
        "💡 상급기관(교육부/도교육청 또는 교육청)으로부터 발급받은 인증번호를 입력하세요."
    )
    if st.session_state.get("demo_mode", True):
        st.info(
            f"🎬 **시연용 인증번호**: `{PIN_CODES[role_key]}`  \n"
            f"실 출시 시 GPKI(행정전자서명) 또는 KEIIS SSO 로 대체됩니다."
        )

    col_a, col_b = st.columns(2)
    if col_a.button("진입", type="primary", key=f"_submit_{role_key}",
                     width="stretch"):
        if verify_pin(role_key, pin_input):
            set_authenticated(role_key, remember=remember)
            st.session_state[f"_show_pin_{role_key}"] = False
            st.toast(f"{role_label}로 인증되었습니다", icon="✅")
            if on_success_redirect:
                st.switch_page(on_success_redirect)
            st.rerun()
        else:
            st.error("⚠ 유효하지 않은 인증번호입니다")
    if col_b.button(cancel_label, key=f"_cancel_{role_key}",
                     width="stretch"):
        st.session_state[f"_show_pin_{role_key}"] = False
        if cancel_redirect:
            st.switch_page(cancel_redirect)
        else:
            st.rerun()

    return False
