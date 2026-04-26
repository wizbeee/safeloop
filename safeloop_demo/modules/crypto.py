"""
SafeLoop 데이터 자동 암호화 모듈 — AES-256-GCM.

목적:
- JSON 데이터를 그대로 평문 노출하지 않도록 자동 암호화
- 같은 SafeLoop 앱 사용자끼리만 복호화 가능
- 사용자는 비밀번호 입력 없이 자동 처리
- 평문 JSON 도 자동 인식 (이전 데이터 호환)

키 우선순위:
1. 환경변수 `SAFELOOP_KEY` (32바이트 hex) — 운영 환경 표준
2. 환경변수 `SAFELOOP_DEMO_MODE=1` 일 때 내장 데모 키 사용 — 시연·콘테스트용
3. SAFELOOP_KEY 가 잘못된 값(32바이트 hex 아님) → RuntimeError (조용한 fallback 차단)
4. 둘 다 없으면 데모 키 + 강한 경고 (시연 환경 보호)

보호 가능:
- 잘못된 사람에게 메일/카톡 발송 시 평문 노출 방지
- 클라우드 드라이브 공개 설정 실수
- 기기 분실 후 텍스트 에디터로 열어보기

보호 불가:
- 앱 코드 자체를 분석한 키 추출 (전문 해커)
- → 운영 시에는 환경변수 키 + 학교별 페어링 으로 강화
"""
from __future__ import annotations

import json
import os
from typing import Any

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _CRYPTO_AVAILABLE = True
except Exception:
    _CRYPTO_AVAILABLE = False


# 시연·콘테스트용 내장 키 — `SAFELOOP_DEMO_MODE=1` 일 때만 활성화
# 운영 환경에서는 반드시 `SAFELOOP_KEY` 환경변수로 별도 키 주입.
# 32바이트 (AES-256).
_DEMO_KEY: bytes = b"SafeLoop_v1_demo_key_2026__APRX!"
assert len(_DEMO_KEY) == 32, "AES-256 requires exactly 32 bytes"

# 매직 헤더 — 암호화된 파일임을 식별
MAGIC = b"SLOOP1\x00"  # 7 bytes
NONCE_LEN = 12  # AES-GCM 표준

# 잘못된 환경변수 사용 1회 경고 (반복 노이즈 방지)
_warned_invalid_env_key = False
_warned_demo_fallback = False


def _key() -> bytes:
    """현재 사용 키 결정.

    우선순위:
    1. SAFELOOP_KEY 환경변수가 32바이트 hex 로 유효 → 그걸 사용
    2. SAFELOOP_KEY 가 있지만 잘못된 값 → 한 번 경고 + DEMO_MODE 로 fallback
       (잘못된 값을 조용히 무시하지 않음)
    3. SAFELOOP_DEMO_MODE=1 → 내장 데모 키 사용 (한 번 경고)
    4. 그 외 → RuntimeError (운영 환경 안전장치)
    """
    global _warned_invalid_env_key, _warned_demo_fallback
    env_key = os.environ.get("SAFELOOP_KEY")
    demo_mode = os.environ.get("SAFELOOP_DEMO_MODE") == "1"

    if env_key:
        try:
            k = bytes.fromhex(env_key)
            if len(k) == 32:
                return k
            raise ValueError(f"SAFELOOP_KEY must be 32 bytes (got {len(k)})")
        except Exception as e:
            if not _warned_invalid_env_key:
                _warned_invalid_env_key = True
                # Streamlit 환경이면 화면 경고, 아니면 stderr
                _emit_warning(
                    f"⚠ SAFELOOP_KEY 환경변수가 유효하지 않습니다 ({e}). "
                    f"32바이트 hex 64자 문자열이어야 합니다."
                )
            if not demo_mode:
                raise RuntimeError(
                    "SAFELOOP_KEY 환경변수가 잘못 설정되었고, "
                    "SAFELOOP_DEMO_MODE=1 도 설정되지 않았습니다. "
                    "올바른 키를 설정하거나 SAFELOOP_DEMO_MODE=1 을 설정하세요."
                ) from e
            # demo_mode 켜져 있으면 fallback 허용

    if demo_mode:
        if not _warned_demo_fallback:
            _warned_demo_fallback = True
            _emit_warning(
                "🎬 SAFELOOP_DEMO_MODE=1 — 내장 데모 키 사용 중. "
                "운영 환경에서는 반드시 SAFELOOP_KEY 환경변수를 설정하세요."
            )
        return _DEMO_KEY

    # 환경변수가 둘 다 없음 — 시연 환경 보호 차원에서 데모 키 fallback + 경고
    if not _warned_demo_fallback:
        _warned_demo_fallback = True
        _emit_warning(
            "⚠ 암호화 키 환경변수 미설정 — 내장 데모 키로 자동 fallback. "
            "운영 환경에서는 SAFELOOP_KEY (32바이트 hex) 또는 "
            "SAFELOOP_DEMO_MODE=1 을 명시적으로 설정하세요."
        )
    return _DEMO_KEY


def _emit_warning(msg: str) -> None:
    """Streamlit 환경이면 st.warning, 아니면 stderr 로 출력."""
    try:
        import streamlit as st  # noqa
        st.warning(msg)
        return
    except Exception:
        pass
    import sys
    print(f"[SafeLoop crypto] {msg}", file=sys.stderr)


def encrypt_payload(data: Any) -> bytes:
    """dict 또는 JSON 호환 객체를 암호화된 바이트로 변환.

    포맷: MAGIC(7) + NONCE(12) + CIPHERTEXT+TAG
    """
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    if not _CRYPTO_AVAILABLE:
        # cryptography 라이브러리 없으면 평문 fallback (개발 환경 대비)
        return payload

    aes = AESGCM(_key())
    nonce = os.urandom(NONCE_LEN)
    ciphertext = aes.encrypt(nonce, payload, None)
    return MAGIC + nonce + ciphertext


def is_encrypted(blob: bytes) -> bool:
    """매직 헤더로 암호화 여부 판별."""
    return isinstance(blob, (bytes, bytearray)) and bytes(blob[:len(MAGIC)]) == MAGIC


def decrypt_payload(blob: bytes) -> dict:
    """암호화된 바이트 또는 평문 JSON 을 dict 로 변환.

    - 매직 헤더가 있으면 복호화 시도
    - 헤더 없으면 평문 JSON 으로 파싱 (이전 호환)
    """
    blob = bytes(blob)
    if is_encrypted(blob):
        if not _CRYPTO_AVAILABLE:
            raise RuntimeError(
                "이 파일은 암호화되어 있지만 현재 환경에 cryptography 라이브러리가 없어 "
                "복호화할 수 없습니다."
            )
        nonce = blob[len(MAGIC):len(MAGIC) + NONCE_LEN]
        ciphertext = blob[len(MAGIC) + NONCE_LEN:]
        aes = AESGCM(_key())
        plaintext = aes.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode("utf-8"))
    # 평문 JSON 폴백
    return json.loads(blob.decode("utf-8"))


def encrypt_to_file_bytes(data: Any) -> bytes:
    """다운로드용. 암호화된 바이트 반환 (확장자 .safeloop 권장)."""
    return encrypt_payload(data)


def safe_filename(base: str, encrypted: bool = True) -> str:
    """확장자 결정. 암호화 시 .safeloop, 평문 시 .json"""
    if encrypted:
        return f"{base}.safeloop"
    return f"{base}.json"
