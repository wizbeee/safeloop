"""
시연용 이미지 생성/로드.

전략:
- 충남삼성고 본교 촬영 사진이 있는 5공간(화학실·물리실·음악실·미술실·디자인실)
  은 sample_images/ 의 실 사진을 사용 — 시연 가치 ↑, 캐시 적중률 ↑.
- 나머지 공간은 PIL 로 "DEMO" 워터마크가 박힌 가공 이미지를 즉석 생성.

장점:
- 사진 35장으로 실 사용 톤의 시연 가능 (음악실·미술실·디자인실 풍부)
- 사진 없는 공간도 PIL 폴백으로 흐름은 막힘 없음
- 사이드바 DEMO 인디케이터 + 시연 안내 카피로 시연임은 항상 명시
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SHOT_LABELS: dict[str, str] = {
    "entrance_diag": "01 — 입구 대각선",
    "front_view": "02 — 교탁 앞 정면",
    "center_window": "03 — 중앙 창문",
    "center_corridor": "04 — 중앙 복도",
    "center_front_door": "05 — 중앙 앞문",
    "center_back_door": "06 — 중앙 뒷문",
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


# 실 사진 보유 공간 → sample_images/ 하위 폴더명 매핑.
# 충남삼성고 본교 촬영본 5공간 × 6~10장 = 35장.
_SPACE_TO_SAMPLE_DIR: dict[str, str] = {
    "화학실": "chemistry_lab",
    "물리실": "physics_lab",
    "음악실": "music_room",
    "미술실": "art_room",
    "디자인실": "design_room",
}


def make_all_demo_shots(space_type: str) -> dict[str, list[dict]]:
    """7컷 시연 이미지 묶음을 반환.

    실 사진 보유 5공간(화학실·물리실·음악실·미술실·디자인실)은 sample_images
    의 실제 사진을 sample_dispatch 의 키워드 매핑(흄후드→뒷벽, 싱크→창가 등)
    으로 의미 기반 분배. 나머지 공간은 PIL "DEMO" 카드 즉석 생성.

    반환 형식: {shot_key: [{name, bytes, source}], ...} (선택 슬롯도 포함).
    """
    folder_name = _SPACE_TO_SAMPLE_DIR.get(space_type)
    if folder_name:
        base = (
            Path(__file__).resolve().parent.parent / "sample_images" / folder_name
        )
        if base.exists():
            files = sorted(base.glob("*.jpg"))
            if files:
                try:
                    from .sample_dispatch import dispatch_samples_to_shots
                    dispatched = dispatch_samples_to_shots(files)
                    # 실 사진이 키워드 매칭 실패로 비어 둔 필수 슬롯이 있으면
                    # PIL 폴백으로 보충 — 항상 필수 7컷 모두 채워진 상태로 반환.
                    for key in REQUIRED_KEYS:
                        if not dispatched.get(key):
                            dispatched[key] = [{
                                "name": f"demo_{space_type}_{key}.jpg",
                                "bytes": make_demo_image(space_type, key),
                                "source": "demo_synth",
                            }]
                    # 선택 슬롯 키도 존재 보장
                    for key in ("back_door_diag", "close_supplement"):
                        dispatched.setdefault(key, [])
                    return dispatched
                except Exception:
                    pass  # 디스패치 실패 시 PIL 폴백

    # PIL 합성 카드 (실 사진 없는 공간 또는 로드/디스패치 실패)
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
