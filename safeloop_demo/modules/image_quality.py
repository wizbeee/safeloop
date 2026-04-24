"""
이미지 품질 사전 검사 + 자동 최적화.

목적:
  1) 사용자가 흐리거나 어두운 사진을 그대로 AI에 넘기지 않도록 사전 차단
  2) Claude/GPT Vision 입력 한계(긴 변 1568px)에 맞춰 자동 리사이즈
  3) EXIF 회전 정보 적용 (특히 iPhone 가로/세로)

알고리즘:
  - 블러: Pillow 내장 가우시안 차이 → 고주파 분산
  - 밝기: 그레이스케일 평균
  - 채도: HSV 채널 표준편차
  - 해상도: 최소 600x400
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageOps


MAX_LONG_EDGE = 1568   # Claude Vision 권장 최대 긴 변
JPEG_QUALITY = 85
MIN_WIDTH = 600
MIN_HEIGHT = 400
BLUR_VARIANCE_OK = 15.0      # 그 미만이면 흐림 의심
BRIGHTNESS_DARK = 60         # 0~255, 그 미만이면 어두움
BRIGHTNESS_BRIGHT = 220      # 그 초과면 과노출


@dataclass
class QualityReport:
    ok: bool
    width: int
    height: int
    brightness: float
    blur_score: float        # 클수록 선명
    issues: list[str]
    warnings: list[str]
    optimized_bytes: bytes   # 회전·리사이즈 적용 후 JPEG

    def summary(self) -> str:
        if self.ok and not self.warnings:
            return "양호"
        if self.issues:
            return "재촬영 권장"
        return "사용 가능 (주의)"


def _laplacian_like_variance(img: Image.Image) -> float:
    """Pillow 만으로 라플라시안 분산 근사: 원본 ↔ 가우시안 블러 차이의 분산.
    OpenCV 의존 회피."""
    gray = img.convert("L")
    blurred = gray.filter(ImageFilter.GaussianBlur(radius=2))
    # 픽셀 차이를 분산으로
    px_o = list(gray.getdata())
    px_b = list(blurred.getdata())
    diffs = [abs(o - b) for o, b in zip(px_o, px_b)]
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / n
    return var


def analyze_and_optimize(image_bytes: bytes) -> QualityReport:
    """원본 바이트를 받아 품질 리포트 + 최적화된 JPEG 바이트 반환."""
    issues: list[str] = []
    warnings: list[str] = []

    try:
        img = Image.open(io.BytesIO(image_bytes))
        # EXIF 회전 적용 (iPhone 등)
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        return QualityReport(
            ok=False, width=0, height=0, brightness=0, blur_score=0,
            issues=[f"이미지 로딩 실패: {e}"], warnings=[],
            optimized_bytes=image_bytes,
        )

    if img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size

    # 해상도 검사
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        issues.append(f"해상도 부족 ({w}×{h}, 최소 {MIN_WIDTH}×{MIN_HEIGHT})")

    # 밝기 검사
    grey = img.convert("L")
    pixels = list(grey.getdata())
    brightness = sum(pixels) / len(pixels)
    if brightness < BRIGHTNESS_DARK:
        issues.append(f"너무 어두움 (평균 밝기 {brightness:.0f}/255) — 조명 추가 또는 재촬영")
    elif brightness > BRIGHTNESS_BRIGHT:
        warnings.append(f"과노출 가능 (평균 밝기 {brightness:.0f}/255)")

    # 흐림 검사 (썸네일에서 측정해 속도 확보)
    sample = img.copy()
    sample.thumbnail((640, 640))
    blur_score = _laplacian_like_variance(sample)
    if blur_score < BLUR_VARIANCE_OK:
        issues.append(f"흔들림·초점 문제 의심 (선명도 {blur_score:.1f}) — 다시 또박또박 촬영")
    elif blur_score < BLUR_VARIANCE_OK * 1.5:
        warnings.append(f"선명도 낮은 편 (점수 {blur_score:.1f})")

    # 리사이즈 — 긴 변 1568px 이내
    if max(w, h) > MAX_LONG_EDGE:
        ratio = MAX_LONG_EDGE / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # JPEG 인코딩
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    optimized = buf.getvalue()

    ok = len(issues) == 0

    return QualityReport(
        ok=ok,
        width=img.size[0], height=img.size[1],
        brightness=brightness,
        blur_score=blur_score,
        issues=issues,
        warnings=warnings,
        optimized_bytes=optimized,
    )


def optimize_only(image_bytes: bytes) -> bytes:
    """품질 검사 없이 최적화만 (회전+리사이즈+JPEG)."""
    return analyze_and_optimize(image_bytes).optimized_bytes
