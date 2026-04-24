"""
AI 비전·텍스트 공급자 어댑터.

동일 인터페이스로 Anthropic Claude / OpenAI GPT-4o 를 투명 교체한다.
공급자 선택 우선순위:
  세션 상태 > 환경 변수 SAFELOOP_PROVIDER > 자동(사용 가능한 첫 공급자)

향후 Google Gemini · NAVER HyperCLOVA X 등 확장 시 같은 패턴으로 추가.
"""
from __future__ import annotations

import base64
import os
import random
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional


# ─────────────────────────────────────────
# 자동 재시도 (지수 백오프 + jitter)
# ─────────────────────────────────────────
_RETRY_MARKERS = (
    "timeout", "timed out", "connection", "503", "502", "504",
    "429", "rate limit", "rate_limit", "overloaded", "temporarily",
    "service unavailable", "internal server error",
)


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(m in msg for m in _RETRY_MARKERS)


def _with_retry(fn: Callable[[], str], max_attempts: int = 3,
                base_delay: float = 1.5) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last_error = e
            if attempt >= max_attempts - 1 or not _is_retryable(e):
                raise
            wait = (2 ** attempt) * base_delay + random.uniform(0, 1)
            time.sleep(wait)
    if last_error:
        raise last_error
    return ""


class VisionProvider(ABC):
    """비전·텍스트 동시 지원 추상 공급자."""
    id: str = ""
    label: str = ""

    @abstractmethod
    def available(self) -> bool:
        """API 키가 설정되어 호출 가능한지."""

    @abstractmethod
    def call(self, system: str, text: str, images: list[bytes],
             tier: str = "vision") -> str:
        """공통 호출 — 이미지가 비어도 텍스트 응답 반환.

        tier: "vision" (사진 분석) | "text" (빠른 텍스트 생성)
        """


# ─────────────────────────────────────────
# Anthropic Claude
# ─────────────────────────────────────────
class AnthropicProvider(VisionProvider):
    id = "anthropic"
    label = "Anthropic Claude (Opus 4.5 · Haiku 4.5)"
    MODELS = {
        "vision": "claude-opus-4-5",
        "text": "claude-haiku-4-5-20251001",
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    def available(self) -> bool:
        return bool(self.api_key)

    def call(self, system: str, text: str, images: list[bytes],
             tier: str = "vision") -> str:
        from anthropic import Anthropic
        import httpx
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        # 명시적 timeout: 전체 90초, 연결 10초
        if proxy:
            client = Anthropic(
                api_key=self.api_key,
                http_client=httpx.Client(proxy=proxy,
                                         timeout=httpx.Timeout(90.0, connect=10.0)),
                timeout=90.0,
            )
        else:
            client = Anthropic(api_key=self.api_key, timeout=90.0)

        content: list = [{"type": "text", "text": text}]
        for b in images:
            data = base64.standard_b64encode(b).decode("utf-8")
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": data},
            })

        def _do() -> str:
            resp = client.messages.create(
                model=self.MODELS[tier],
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": content}],
            )
            return resp.content[0].text

        return _with_retry(_do, max_attempts=3, base_delay=2.0)


# ─────────────────────────────────────────
# OpenAI GPT-4o
# ─────────────────────────────────────────
class OpenAIProvider(VisionProvider):
    id = "openai"
    label = "OpenAI GPT-4o"
    MODELS = {
        "vision": "gpt-4o",
        "text": "gpt-4o-mini",
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def available(self) -> bool:
        return bool(self.api_key)

    def call(self, system: str, text: str, images: list[bytes],
             tier: str = "vision") -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, timeout=90.0)

        content: list = [{"type": "text", "text": text}]
        for b in images:
            data = base64.standard_b64encode(b).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{data}"},
            })

        def _do() -> str:
            resp = client.chat.completions.create(
                model=self.MODELS[tier],
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
            )
            return resp.choices[0].message.content or ""

        return _with_retry(_do, max_attempts=3, base_delay=2.0)


# ─────────────────────────────────────────
# 레지스트리
# ─────────────────────────────────────────
_PROVIDER_CLASSES: dict[str, type[VisionProvider]] = {
    AnthropicProvider.id: AnthropicProvider,
    OpenAIProvider.id: OpenAIProvider,
}

ALL_PROVIDERS: list[dict] = [
    {"id": AnthropicProvider.id, "label": AnthropicProvider.label,
     "env_var": "ANTHROPIC_API_KEY"},
    {"id": OpenAIProvider.id, "label": OpenAIProvider.label,
     "env_var": "OPENAI_API_KEY"},
]


def _key_from_session(provider_id: str) -> Optional[str]:
    """우선순위: 세션 입력 > Streamlit Secrets > None"""
    try:
        import streamlit as st
        sess_key = st.session_state.get(f"api_key_{provider_id}")
        if sess_key:
            return sess_key
        # Streamlit Cloud Secrets fallback
        secret_key = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
        }.get(provider_id)
        if secret_key:
            try:
                v = st.secrets.get(secret_key)
                if v:
                    return v
            except Exception:
                pass
    except Exception:
        pass
    return None


def get_provider(name: Optional[str] = None) -> VisionProvider:
    """현재 유효한 공급자 인스턴스 반환."""
    try:
        import streamlit as st
        chosen = name or st.session_state.get("ai_provider")
    except Exception:
        chosen = name
    chosen = chosen or os.environ.get("SAFELOOP_PROVIDER")

    if chosen and chosen in _PROVIDER_CLASSES:
        return _PROVIDER_CLASSES[chosen](api_key=_key_from_session(chosen))

    # 자동 — 첫 번째로 사용 가능한 공급자
    for p in ALL_PROVIDERS:
        inst = _PROVIDER_CLASSES[p["id"]](api_key=_key_from_session(p["id"]))
        if inst.available():
            return inst

    # 그래도 없으면 Anthropic(사용 불가 상태) 반환
    return AnthropicProvider()


def test_provider_connection(provider_id: str, api_key: Optional[str] = None,
                              timeout: float = 15.0) -> tuple[bool, str]:
    """공급자 연결 테스트 — 최소 토큰 호출 1회.

    Returns: (성공 여부, 사용자 표시 메시지)
    """
    cls = _PROVIDER_CLASSES.get(provider_id)
    if not cls:
        return False, f"알 수 없는 공급자: {provider_id}"
    inst = cls(api_key=api_key or _key_from_session(provider_id))
    if not inst.available():
        return False, "API 키가 없습니다. 위에서 키를 입력하고 저장하세요."

    try:
        # 가장 가벼운 호출 (텍스트 모델, max_tokens=5)
        resp = inst.call(
            system="You respond with exactly the word: ok",
            text="ping",
            images=[],
            tier="text",
        )
        if resp:
            return True, f"연결 정상 — 응답 받음 ({len(resp)} chars)"
        return False, "응답이 비어있습니다."
    except Exception as e:
        msg = str(e).lower()
        if "auth" in msg or "401" in msg or "403" in msg or "invalid" in msg:
            return False, "키가 잘못되었거나 권한이 없습니다."
        if "rate" in msg or "429" in msg:
            return False, "호출 한도 초과 — 잠시 후 다시 시도하세요."
        if "timeout" in msg or "connection" in msg:
            return False, "네트워크 또는 공급자 응답 지연."
        return False, f"오류: {type(e).__name__} — {str(e)[:80]}"


def providers_status() -> list[dict]:
    """설정 UI용 — 전체 공급자의 사용 가능 여부 + 현재 키 출처."""
    out = []
    for p in ALL_PROVIDERS:
        session_key = _key_from_session(p["id"])
        env_key = os.environ.get(p["env_var"])
        inst = _PROVIDER_CLASSES[p["id"]](api_key=session_key or env_key)
        out.append({
            "id": p["id"],
            "label": p["label"],
            "env_var": p["env_var"],
            "available": inst.available(),
            "key_source": ("세션" if session_key else ("환경변수" if env_key else None)),
        })
    return out
