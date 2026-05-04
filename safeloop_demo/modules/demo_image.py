"""
시연용 더미 이미지 생성 — PIL 로 즉석 생성.

시연(데모)에서 실제 학교 사진을 사용하지 않고, "DEMO" 워터마크와 공간/위치
정보가 텍스트로 박힌 회색 카드 이미지를 생성한다.

장점:
- 사용자가 학교 사진을 촬영해 제공할 필요 없음
- 시연용 가공 데이터임이 화면에 명시됨 (저작권·프라이버시 우려 없음)
- 9개 공간 × 7컷 = 63장을 즉석 생성 가능
- AI 분석 결과는 캐시된 진짜 결과(또는 실제 호출)이므로 흐름은 100% 진짜
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SHOT_LABELS: dict[str, str] = {
    "entrance_diag": "01 — 입구 대각선",
    "front_view": "02 — 교탁 앞 정면",
    "center_window": "03 — 중앙 → 창문",
    "center_corridor": "04 — 중앙 → 복도",
    "center_front_door": "05 — 중앙 → 앞문",
    "center_back_door": "06 — 중앙 → 뒷문",
    "ceiling": "07 — 천장",
    "back_door_diag": "08 — 뒷문 대각선",
    "close_supplement": "09 — 보완 촬영",
}

REQUIRED_KEYS: list[str] = [
    "entrance_diag", "front_view", "center_window", "center_corridor",
    "center_front_door", "center_back_door", "ceiling",
]

# 공간별 색상 톤 (시각 구분)
SPACE_TONE: dict[str, str] = {
    "화학실": "#E3F2FD",
    "물리실": "#E8F5E9",
    "생명과학실": "#F3E5F5",
    "지구과학실": "#FFF3E0",
    "기술실": "#FCE4EC",
    "가정실": "#FFFDE7",
    "음악실": "#E0F7FA",
    "미술실": "#F1F8E9",
    "디자인실": "#EDE7F6",
    "일반교실": "#F5F5F5",
}


def _load_font(size: int) -> ImageFont.ImageFont:
    """한글 지원 폰트 로드 — 윈도우 맑은 고딕 우선, 폴백 경로들 시도."""
    candidates = [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/System/Library/Fonts/Apple SD Gothic Neo.ttc",
    ]
    for path in candidates:
        try:
            if Path(path).exists():
                return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_demo_image(
    space_type: str,
    shot_key: str,
    width: int = 1024,
    height: int = 768,
) -> bytes:
    """시연용 가공 이미지 한 장을 JPEG 바이트로 반환."""
    bg = SPACE_TONE.get(space_type, "#F5F5F5")
    img = Image.new("RGB", (width, height), color=bg)
    draw = ImageDraw.Draw(img)

    # 빨강 테두리
    draw.rectangle([0, 0, width - 1, height - 1], outline="#D50000", width=6)

    # 폰트
    font_xl = _load_font(64)
    font_lg = _load_font(40)
    font_md = _load_font(28)
    font_sm = _load_font(18)

    # 좌상단 DEMO 라벨
    draw.text((40, 30), "DEMO", fill="#D50000", font=font_xl)
    draw.text((40, 110), "시연용 가공 이미지", fill="#9A9A9F", font=font_sm)

    # 중앙: 공간 + 컷 정보
    label = SHOT_LABELS.get(shot_key, shot_key)
    cx, cy = width // 2, height // 2

    # 공간 유형 (중앙 큰 글씨)
    space_text = space_type
    space_bbox = draw.textbbox((0, 0), space_text, font=font_xl)
    space_w = space_bbox[2] - space_bbox[0]
    draw.text(
        (cx - space_w // 2, cy - 80),
        space_text, fill="#0A0A0B", font=font_xl,
    )

    # 컷 라벨 (중앙 작은 글씨)
    cut_bbox = draw.textbbox((0, 0), label, font=font_lg)
    cut_w = cut_bbox[2] - cut_bbox[0]
    draw.text(
        (cx - cut_w // 2, cy + 10),
        label, fill="#6B6B70", font=font_lg,
    )

    # 하단: 면책 안내
    footer = "실제 학교 사진 아님 · AI 분석 흐름만 시연합니다"
    foot_bbox = draw.textbbox((0, 0), footer, font=font_sm)
    foot_w = foot_bbox[2] - foot_bbox[0]
    draw.text(
        (cx - foot_w // 2, height - 50),
        footer, fill="#9A9A9F", font=font_sm,
    )

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()


def make_all_demo_shots(space_type: str) -> dict[str, list[dict]]:
    """7컷 모두에 대한 더미 이미지를 생성.

    반환 형식: {shot_key: [{name, bytes, source}], ...} (선택 슬롯도 빈 리스트로 포함).
    """
    result: dict[str, list[dict]] = {
        k: [] for k in REQUIRED_KEYS + ["back_door_diag", "close_supplement"]
    }
    for key in REQUIRED_KEYS:
        result[key].append({
            "name": f"demo_{space_type}_{key}.jpg",
            "bytes": make_demo_image(space_type, key),
            "source": "demo_synth",
        })
    return result
