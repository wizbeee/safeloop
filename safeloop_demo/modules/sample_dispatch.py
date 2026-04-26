"""
시연용 샘플 사진을 7컷 위치 슬롯에 의미 기반으로 분배하는 헬퍼.

파일명에 담긴 키워드(흄후드/싱크/완강기 등)를 보고 적절한 위치 슬롯에 배치한다.
홈의 '시연 자동 재생' 과 AI 점검 페이지의 '샘플 불러와서 7컷에 분배' 두 곳에서 공유.
"""
from __future__ import annotations

from pathlib import Path


# 파일명 키워드 → SHOT 키 매핑 (의미 기반).
# 우선순위 순서로 매칭 — 첫 일치 키워드의 슬롯에 배치.
KEYWORD_MAP: list[tuple[str, str]] = [
    ("fire_alarm", "ceiling"),                  # 화재경보기/감지기 → 천장
    ("hood", "center_back_door"),                # 흄후드 → 뒷벽
    ("safety_poster", "center_back_door"),
    ("emergency_shower", "center_front_door"),   # 안전샤워 → 앞문 쪽
    ("ppe", "center_front_door"),                # PPE 보관함 → 앞문 쪽
    ("fire_extinguisher", "center_corridor"),    # 소화기 → 복도쪽
    ("sinks_line", "center_window"),             # 싱크 라인 → 창가
    ("sinks_storage", "center_window"),          # 싱크+수납 → 창가
    ("wide_full", "entrance_diag"),              # 전체 와이드 → 입구 시야
    ("wide_equipment", "front_view"),            # 설비 와이드 → 교탁 앞
    ("wide_alt", "front_view"),
]

# 7컷 필수 슬롯 (분배 대상)
TARGET_ORDER: list[str] = [
    "entrance_diag", "front_view", "center_window", "center_corridor",
    "center_front_door", "center_back_door", "ceiling",
]

# 선택 슬롯 (분배 대상은 아니지만 빈 dict 키로 함께 반환)
OPTIONAL_KEYS: list[str] = ["back_door_diag", "close_supplement"]


def dispatch_samples_to_shots(paths: list[Path]) -> dict[str, list[dict]]:
    """파일명 의미 기반으로 샘플 사진들을 7컷 슬롯에 분배.

    반환: {shot_key: [{name, bytes, source}], ...} — 9개 키 모두 포함 (값은 빈 리스트일 수 있음).

    분배 규칙:
    1) 파일명 키워드가 KEYWORD_MAP 에 일치 → 해당 슬롯에 배치
    2) 매칭 못 한 파일은 비어 있는 필수 슬롯(TARGET_ORDER)에 순서대로 배치
    3) 중복 슬롯에는 1장만 (먼저 매칭된 파일이 우선)
    """
    shots: dict[str, list[dict]] = {k: [] for k in TARGET_ORDER + OPTIONAL_KEYS}
    used_keys: set[str] = set()
    unmatched: list[Path] = []

    # 1차: 키워드 매핑
    for p in paths:
        name_lower = p.name.lower()
        target_key = None
        for keyword, key in KEYWORD_MAP:
            if keyword in name_lower and key not in used_keys:
                target_key = key
                break
        if target_key:
            shots[target_key].append({
                "name": p.name,
                "bytes": p.read_bytes(),
                "source": "sample",
            })
            used_keys.add(target_key)
        else:
            unmatched.append(p)

    # 2차: 매칭 안 된 파일은 비어 있는 필수 슬롯에 순서대로
    for p in unmatched:
        for key in TARGET_ORDER:
            if key not in used_keys:
                shots[key].append({
                    "name": p.name,
                    "bytes": p.read_bytes(),
                    "source": "sample",
                })
                used_keys.add(key)
                break

    return shots


def resolve_sample_folder(
    sample_root: Path, primary: str, fallback: str = "chemistry_lab",
) -> tuple[Path, bool]:
    """샘플 폴더를 결정. 비어 있으면 폴백 사용.

    반환: (해석된 폴더 경로, 폴백 사용 여부)
    """
    primary_path = sample_root / primary
    if primary_path.exists() and any(primary_path.glob("*.jpg")):
        return primary_path, False
    return sample_root / fallback, True
