"""
SMTP 메일 발송 — 학교 → 교육청 통합 보고서 자동 첨부 발송.

환경 변수 (`.env`):
- SMTP_HOST: 기본 smtp.gmail.com
- SMTP_PORT: 기본 587 (STARTTLS)
- SMTP_USER: 발신자 이메일 (보통 학교 계정)
- SMTP_PASS: 앱 비밀번호 (Gmail 의 경우 2FA + 앱 비밀번호 발급 필요)
- SMTP_FROM_NAME: 표시 이름 (기본 "SafeLoop")

Gmail 앱 비밀번호 발급 방법:
1. Google 계정 → 보안 → 2단계 인증 활성화
2. 앱 비밀번호 생성 → "기타(맞춤 이름)" → "SafeLoop" 입력 → 16자리 비밀번호 복사
3. `.env` 에 `SMTP_PASS=발급된16자리` 저장

시연 모드 보호:
`SAFELOOP_DEMO_MODE=1` 또는 session_state.demo_mode=True 일 때는 호출자가
실제 발송을 차단하고 "시연 — 발송 모의" 로 표시해야 함. 본 모듈 자체는
시연 가드를 두지 않는다 (호출자 책임).
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path


class MailerConfigError(Exception):
    """SMTP 설정 누락·잘못된 값."""


class MailerSendError(Exception):
    """발송 실패."""


def smtp_configured() -> bool:
    """SMTP 환경 변수가 충분히 설정되어 있는지 검사."""
    return bool(
        os.environ.get("SMTP_USER", "").strip()
        and os.environ.get("SMTP_PASS", "").strip()
    )


def _config() -> dict:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    port_str = os.environ.get("SMTP_PORT", "587").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    pwd = os.environ.get("SMTP_PASS", "").strip()
    from_name = os.environ.get("SMTP_FROM_NAME", "SafeLoop").strip()
    if not user or not pwd:
        raise MailerConfigError(
            "SMTP_USER / SMTP_PASS 환경변수가 비어 있습니다. "
            ".env 파일에 Gmail 계정 + 앱 비밀번호를 등록하세요."
        )
    try:
        port = int(port_str)
    except ValueError:
        raise MailerConfigError(f"SMTP_PORT 가 정수가 아닙니다: {port_str!r}")
    return {
        "host": host,
        "port": port,
        "user": user,
        "pwd": pwd,
        "from_name": from_name,
    }


def send_inspection_email(
    to_email: str,
    subject: str,
    body_text: str,
    attachments: list[tuple[str, bytes, str]] | None = None,
    cc: list[str] | None = None,
) -> dict:
    """점검 보고서 메일 발송.

    Args:
        to_email: 수신자 (교육청 담당자 이메일)
        subject: 제목 — 학교명·발송일 포함 권장
        body_text: 본문 (plain text). HTML 미지원 — 단순·신뢰성 우선.
        attachments: (filename, bytes, mime_type) 리스트. PDF/Excel/JSON 첨부.
        cc: 참조 수신자 (예: 학교 본인 이메일 — 발송 기록 보관용)

    Returns:
        {"ok": bool, "message_id": str | None, "error": str | None}
    """
    if not to_email or "@" not in to_email:
        return {"ok": False, "message_id": None,
                "error": f"수신자 이메일이 올바르지 않습니다: {to_email!r}"}

    try:
        cfg = _config()
    except MailerConfigError as e:
        return {"ok": False, "message_id": None, "error": str(e)}

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((cfg["from_name"], cfg["user"]))
    msg["To"] = to_email
    if cc:
        msg["Cc"] = ", ".join([c for c in cc if c and "@" in c])
    msg.set_content(body_text)

    for fname, data, mime in (attachments or []):
        if "/" not in mime:
            mime = "application/octet-stream"
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype,
                            filename=fname)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
            server.starttls()
            server.login(cfg["user"], cfg["pwd"])
            server.send_message(msg)
        return {"ok": True, "message_id": msg.get("Message-ID"), "error": None}
    except smtplib.SMTPAuthenticationError as e:
        return {"ok": False, "message_id": None,
                "error": f"SMTP 인증 실패 — 앱 비밀번호 확인: {e}"}
    except smtplib.SMTPException as e:
        return {"ok": False, "message_id": None,
                "error": f"SMTP 발송 실패: {e}"}
    except OSError as e:
        return {"ok": False, "message_id": None,
                "error": f"네트워크 연결 실패: {e}"}


def test_smtp_connection() -> dict:
    """SMTP 서버 연결·인증만 시험 (메일 미발송).

    Returns: {"ok": bool, "host": str, "error": str | None}
    """
    try:
        cfg = _config()
    except MailerConfigError as e:
        return {"ok": False, "host": "", "error": str(e)}
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.starttls()
            server.login(cfg["user"], cfg["pwd"])
        return {"ok": True, "host": cfg["host"], "error": None}
    except smtplib.SMTPAuthenticationError as e:
        return {"ok": False, "host": cfg["host"],
                "error": f"인증 실패 — 앱 비밀번호 확인: {e}"}
    except Exception as e:
        return {"ok": False, "host": cfg["host"],
                "error": f"연결 실패: {e}"}
