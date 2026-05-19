"""
AI 비전 파이프라인 — 단계 1(공간 식별) · 단계 2(설비 탐지) · 단계 3(맞춤 점검표).

modules.ai_providers 의 Adapter(Anthropic · OpenAI · …)를 투명 교체하며 호출.
해시 기반 디스크 캐싱으로 동일 입력 재분석 시 API 호출 생략.
사진에 샷 메타데이터(03-1 식 라벨)를 주입해 설비사진 매핑 품질 향상.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Optional

from modules.ai_providers import _PROVIDER_CLASSES, get_provider
from modules.image_quality import optimize_only
from modules.prompts import (
    STAGE1_SYSTEM, STAGE2_SYSTEM, STAGE3_SYSTEM,
    stage2_system_for, stage3_system_for,
)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "school_storage" / "_ai_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────
# 캐시
# ─────────────────────────────────────────
def _hash_images(images: list[bytes]) -> str:
    h = hashlib.sha256()
    for b in images:
        h.update(hashlib.sha256(b).digest())
    return h.hexdigest()[:16]


def _cache_path(stage: str, key: str, provider_id: str) -> Path:
    return CACHE_DIR / f"{stage}_{provider_id}_{key}.json"


def _read_cache(stage: str, key: str, provider_id: str) -> Optional[dict]:
    p = _cache_path(stage, key, provider_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _write_cache(stage: str, key: str, provider_id: str, payload: dict) -> None:
    _cache_path(stage, key, provider_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _parse_json(raw: str) -> dict:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        # 응답이 max_tokens 로 잘린 경우: 마지막 완성된 item 까지 부분 복구
        try:
            return _recover_truncated_json(cleaned)
        except Exception:
            pass
        return {"raw": raw, "parse_error": True}


def _recover_truncated_json(text: str) -> dict:
    """응답이 도중에 잘렸을 때(예: Stage 3 체크리스트) 완성된 부분만 복구.

    전략: 마지막으로 닫힌 `}` 바로 앞까지 잘라내고 `]` + `}` 를 덧붙여
    JSON 전체 구조를 완성. `items` 배열이 있는 응답에 특화.
    """
    # `"items": [` 블록 찾기
    items_start = text.find('"items"')
    if items_start < 0:
        raise ValueError("no items array")
    bracket = text.find('[', items_start)
    if bracket < 0:
        raise ValueError("no opening bracket")

    # items 내부에서 완성된 `}` 의 마지막 인덱스 찾기 (균형 추적)
    depth_curly = 0
    last_complete = -1
    i = bracket + 1
    while i < len(text):
        ch = text[i]
        if ch == '{':
            depth_curly += 1
        elif ch == '}':
            depth_curly -= 1
            if depth_curly == 0:
                last_complete = i
        # 문자열 안이면 건너뛰기
        elif ch == '"':
            i += 1
            while i < len(text) and text[i] != '"':
                if text[i] == '\\':
                    i += 1
                i += 1
        i += 1

    if last_complete < 0:
        raise ValueError("no complete item")

    # 복구된 JSON 조립: 앞부분(items 앞) + [완성 아이템들] + 닫는 }
    # 뒤쪽 rationale 등이 없으므로 items 만 살려 최소 JSON 구성
    head = text[:items_start] # 예: {"space_type": "...", "checklist_name": "...",
    recovered = head.rstrip().rstrip(',') + f' "items": {text[bracket:last_complete+1]}]' + ', "rationale": "(응답이 길어 일부 복구됨)"}}'
    # 다만 recovered 의 끝이 너무 많은 }}} 이 붙을 수 있으므로 단순화된 복구:
    # head + "items": [...] 만 감싸서 반환
    safe = head.rstrip().rstrip(',')
    if not safe.endswith('{'):
        safe = safe.rstrip() + ('' if safe.endswith(',') else ',') + ' '
    # 마지막으로 깔끔하게 파싱 가능한 최소 JSON:
    simple = '{' + f'"items": {text[bracket:last_complete+1]}]' + ', "rationale": "(응답이 길어 일부 복구됨)"' + '}'
    parsed = json.loads(simple)
    parsed["_truncated_recovered"] = True
    return parsed


# ─────────────────────────────────────────
# 파이프라인
# ─────────────────────────────────────────
def _optimize_batch(images: list[bytes]) -> list[bytes]:
    """모든 입력 이미지를 자동 회전·리사이즈 (API 비용·전송시간 절감)."""
    return [optimize_only(b) for b in images]


def run_stage1(images: list[bytes], use_cache: bool = True,
               image_labels: Optional[list[str]] = None,
               wide_only: bool = True) -> dict:
    """단계 1 — 공간 유형 식별.

    wide_only: True면 첫 3장(광각)만 사용해 캐시 키 안정화 (보완 사진 추가해도
               stage1 결과 재사용 가능 비용 절감).
    """
    images = _optimize_batch(images)
    cache_inputs = images[:3] if wide_only and len(images) >= 3 else images
    provider = get_provider()
    cache_key = _hash_images(cache_inputs)
    if use_cache:
        cached = _read_cache("stage1", cache_key, provider.id)
        if cached:
            cached["_cached"] = True
            return cached

    labels_hint = ""
    if image_labels:
        labels_hint = "\n첨부된 이미지 라벨(순서대로): " + ", ".join(image_labels)

    # stage1은 광각 3장만으로도 충분 — 보완 사진은 무시 (비용 절감)
    api_input_images = cache_inputs
    text = f"{len(api_input_images)}장의 사진을 보고 공간 유형을 판정하세요.{labels_hint}"
    t0 = time.time()
    raw = provider.call(STAGE1_SYSTEM, text, api_input_images, tier="vision")
    elapsed = time.time() - t0

    parsed = _parse_json(raw)
    parsed["_elapsed_sec"] = round(elapsed, 2)
    parsed["_provider"] = provider.label
    parsed["_cached"] = False

    if use_cache and not parsed.get("parse_error"):
        _write_cache("stage1", cache_key, provider.id, parsed)
    return parsed


def run_stage2(images: list[bytes], space_type: str, use_cache: bool = True,
               image_labels: Optional[list[str]] = None) -> dict:
    """단계 2 — 안전 설비 탐지."""
    images = _optimize_batch(images)
    provider = get_provider()
    cache_key = f"{_hash_images(images)}_{space_type}"
    if use_cache:
        cached = _read_cache("stage2", cache_key, provider.id)
        if cached:
            cached["_cached"] = True
            return cached

    labels_hint = ""
    if image_labels:
        labels_hint = (
            "\n\n첨부 사진의 라벨(순서대로): " + ", ".join(image_labels) +
            "\n각 설비의 `image_ref` 필드에는 위 라벨 중 하나를 그대로 써 주세요."
        )

    text = (
        f"이 공간은 '{space_type}'으로 식별되었습니다. 해당 공간 유형에서 필요한 안전설비와 그 위치를 탐지해주세요."
        + labels_hint
    )
    # 공간 유형별 카테고리 우선순위가 반영된 시스템 프롬프트 사용
    sys_prompt = stage2_system_for(space_type)
    t0 = time.time()
    raw = provider.call(sys_prompt, text, images, tier="vision")
    elapsed = time.time() - t0

    parsed = _parse_json(raw)
    parsed["_elapsed_sec"] = round(elapsed, 2)
    parsed["_provider"] = provider.label
    parsed["_cached"] = False

    if use_cache and not parsed.get("parse_error"):
        _write_cache("stage2", cache_key, provider.id, parsed)
    return parsed


def run_stage3(stage1_result: dict, stage2_result: dict, use_cache: bool = True) -> dict:
    """단계 3 — 맞춤형 점검표 생성."""
    provider = get_provider()
    clean1 = {k: v for k, v in stage1_result.items() if not k.startswith("_")}
    clean2 = {k: v for k, v in stage2_result.items() if not k.startswith("_")}
    payload = json.dumps({"stage1": clean1, "stage2": clean2}, ensure_ascii=False, sort_keys=True)
    cache_key = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    if use_cache:
        cached = _read_cache("stage3", cache_key, provider.id)
        if cached:
            cached["_cached"] = True
            return cached

    text = (
        f"단계 1 결과:\n{json.dumps(clean1, ensure_ascii=False, indent=2)}\n\n"
        f"단계 2 결과:\n{json.dumps(clean2, ensure_ascii=False, indent=2)}\n\n"
        "위 결과를 근거로 이 공간만을 위한 맞춤형 점검표를 생성하세요. "
        "각 항목의 location 필드에 Stage 2 의 위치 정보를 활용해주세요."
    )
    # 공간 유형별 우선순위가 반영된 Stage 3 시스템 프롬프트
    space_type = (clean1 or {}).get("space_type_primary")
    sys_prompt = stage3_system_for(space_type)
    t0 = time.time()
    raw = provider.call(sys_prompt, text, [], tier="text")
    elapsed = time.time() - t0

    parsed = _parse_json(raw)
    parsed["_elapsed_sec"] = round(elapsed, 2)
    parsed["_provider"] = provider.label
    parsed["_cached"] = False

    if use_cache and not parsed.get("parse_error"):
        _write_cache("stage3", cache_key, provider.id, parsed)
    return parsed


def load_image_bytes(path: Path) -> bytes:
    return Path(path).read_bytes()


def api_key_available() -> bool:
    return get_provider().available()


def current_provider_label() -> str:
    return get_provider().label


def has_cached_demo_results() -> bool:
    """샘플 사진(13장) 결과가 캐시에 있는지 — 시연 폴백 가능성."""
    try:
        return any(CACHE_DIR.glob("stage*_*.json"))
    except Exception:
        return False


def samples_hit_cache(images: list[bytes],
                       space_type: Optional[str] = None) -> bool:
    """현재 업로드된 사진 + 공간 유형 조합이 Stage 2 캐시와 일치하면 True.

    Stage 1 호출이 제거되었으므로 stage2 캐시 키(`{img_hash}_{space_type}`)
    기준으로 검사한다. space_type 미지정 시는 주어진 사진 해시 prefix 만으로
    매칭 (어떤 공간이든 일치하면 True).
    """
    if not images:
        return False
    try:
        img_hash = _hash_images(images)
        for provider_id in ("anthropic", "openai", "gemini"):
            if space_type:
                if (CACHE_DIR / f"stage2_{provider_id}_{img_hash}_{space_type}.json").exists():
                    return True
            else:
                # space_type 미지정 — prefix 매칭 (어느 공간이든 캐시 있으면 True)
                if any(CACHE_DIR.glob(f"stage2_{provider_id}_{img_hash}_*.json")):
                    return True
        return False
    except Exception:
        return False


def load_demo_pipeline_for_samples(images: list[bytes],
                                     space_type: Optional[str] = None) -> Optional[dict]:
    """샘플 사진 + 공간 유형에 매칭되는 Stage 2/3 캐시가 있으면 한꺼번에 반환.

    Stage 1 은 호출하지 않고 사용자 등록 정보로 합성한다.
    Stage 2 캐시 키: `{img_hash}_{space_type}`
    Stage 3 캐시 키: hash(stage1_synth + stage2)
    """
    if not images:
        return None
    img_hash = _hash_images(images)
    for provider_id in ("anthropic", "openai", "gemini"):
        # space_type 지정 — 정확 매칭, 미지정 — 어느 캐시든
        if space_type:
            candidates = [(CACHE_DIR / f"stage2_{provider_id}_{img_hash}_{space_type}.json", space_type)]
        else:
            candidates = []
            for p in CACHE_DIR.glob(f"stage2_{provider_id}_{img_hash}_*.json"):
                # 파일명에서 space_type 추출
                stem = p.stem # stage2_anthropic_{hash}_{space_type}
                parts = stem.split("_")
                if len(parts) >= 4:
                    sp_type = "_".join(parts[3:])
                    candidates.append((p, sp_type))
        for s2_path, sp_type in candidates:
            if not s2_path.exists():
                continue
            try:
                s2 = json.loads(s2_path.read_text(encoding="utf-8"))
                # Stage 1 합성 (사용자 등록 정보 기반)
                s1 = {
                    "space_type_primary": sp_type,
                    "confidence": 1.0,
                    "evidence": ["담당자 등록 정보"],
                    "secondary_hypothesis": None,
                    "notes": "사용자 등록 정보 (Stage 1 생략)",
                    "_elapsed_sec": 0.0,
                    "_provider": "user-input",
                    "_cached": True,
                    "_skipped": True,
                }
                # Stage 3 캐시 키
                clean1 = {k: v for k, v in s1.items() if not k.startswith("_")}
                clean2 = {k: v for k, v in s2.items() if not k.startswith("_")}
                payload = json.dumps({"stage1": clean1, "stage2": clean2},
                                      ensure_ascii=False, sort_keys=True)
                s3_key = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
                s3_path = CACHE_DIR / f"stage3_{provider_id}_{s3_key}.json"
                if not s3_path.exists():
                    continue
                s3 = json.loads(s3_path.read_text(encoding="utf-8"))
                s2["_cached"] = True
                s3["_cached"] = True
                return {"stage1": s1, "stage2": s2, "stage3": s3}
            except Exception:
                continue
    return None


def ensure_demo_cache_for_shots(shots: dict, space_type: str,
                                 provider_id: str = "anthropic") -> bool:
    """시연 시작 시 더미 이미지 7컷에 대한 Stage 2/3 캐시를 자동 보장.

    더미 이미지의 SHA 해시는 sample_images/ 의 실 사진 해시와 다르므로
    기존 캐시가 적중하지 않는다. 이 함수는 더미 이미지 hash 를 키로 한
    Stage 2/3 캐시 파일이 없으면 `modules.demo_responses` 의 합성 응답을
    이용해 자동 생성한다.

    Returns True 면 캐시 보장 완료 (기존 또는 신규 생성), False 면 실패.
    """
    try:
        from .demo_responses import synth_stage2_for_space, synth_stage3_for_space
    except Exception:
        return False

    # 7컷 optimized bytes 추출
    try:
        from .image_quality import analyze_and_optimize
    except Exception:
        analyze_and_optimize = None # type: ignore

    # 더미 이미지를 shots dict 에서 추출 — REQUIRED_KEYS 순서대로
    required_keys = [
        "entrance_diag", "front_view", "center_window", "center_corridor",
        "center_front_door", "center_back_door", "ceiling",
    ]
    images: list[bytes] = []
    for k in required_keys:
        items = shots.get(k, [])
        if items:
            b = items[0].get("bytes")
            if b:
                if analyze_and_optimize is not None:
                    try:
                        images.append(analyze_and_optimize(b).optimized_bytes)
                    except Exception:
                        images.append(b)
                else:
                    images.append(b)
    if not images:
        return False

    img_hash = _hash_images(images)
    s2_path = CACHE_DIR / f"stage2_{provider_id}_{img_hash}_{space_type}.json"

    # 이미 캐시가 있으면 그대로 사용 (실 AI 결과 우선)
    s2_existing = s2_path.exists()
    if not s2_existing:
        # 합성 응답 생성·저장
        try:
            s2 = synth_stage2_for_space(space_type)
            s2_path.write_text(
                json.dumps(s2, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            return False
    else:
        try:
            s2 = json.loads(s2_path.read_text(encoding="utf-8"))
        except Exception:
            return False

    # Stage 3 캐시 키 = hash(stage1_synth + stage2 정제본)
    s1_clean = {
        "space_type_primary": space_type,
        "confidence": 1.0,
        "evidence": ["담당자 등록 정보"],
        "secondary_hypothesis": None,
        "notes": "사용자 등록 정보 (Stage 1 생략)",
    }
    clean2 = {k: v for k, v in s2.items() if not k.startswith("_")}
    payload = json.dumps({"stage1": s1_clean, "stage2": clean2},
                          ensure_ascii=False, sort_keys=True)
    s3_key = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    s3_path = CACHE_DIR / f"stage3_{provider_id}_{s3_key}.json"
    # 캐시 재생성 판정 — 합성 응답 버전이 다르면(또는 미존재) 새로 생성.
    # 실 API 응답은 _synth_demo 마커가 없으므로 그대로 보존됨.
    need_regen = True
    if s3_path.exists():
        try:
            from .demo_responses import SYNTH_VERSION as _SYNTH_VER
            cached = json.loads(s3_path.read_text(encoding="utf-8"))
            if not cached.get("_synth_demo"):
                # 실 API 응답 → 그대로 사용
                need_regen = False
            elif cached.get("_synth_version") == _SYNTH_VER:
                # 같은 버전의 합성 응답 → 그대로 사용
                need_regen = False
        except Exception:
            need_regen = True
    if need_regen:
        try:
            s3 = synth_stage3_for_space(space_type, s2)
            s3_path.write_text(
                json.dumps(s3, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            return False
    return True
